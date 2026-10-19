from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from strategy_runtime.lifecycle import OpportunityObservation, RecommendedAction
from strategy_runtime.persistence import (
    FamilyPublication,
    FamilyPublicationConflictError,
    FamilyPublicationOrderingError,
    StagedFamilyResultRepository,
    StagedObservationHistoryRepository,
    UniversalSignalRow,
)
from strategy_runtime.result import EvaluationState, RowType, UniversalScreeningResult
from tests.asa.fakes import (
    InMemoryLatestResultRepository,
    InMemoryObservationHistoryRepository,
)

NOW = datetime(2026, 1, 2, tzinfo=UTC)


def _row(signal_id: str, symbol: str, *, seconds: int = 0) -> UniversalSignalRow:
    observed_at = NOW + timedelta(seconds=seconds)
    return UniversalSignalRow.from_result(
        UniversalScreeningResult(
            strategy_id=signal_id,
            strategy_version="1.0.0",
            symbol=symbol,
            observation_id=f"{signal_id}-{symbol}-{seconds}",
            opportunity_id=None,
            row_type=RowType.RESULT,
            verdict="pass",
            evaluation_state=EvaluationState.PASS,
            lifecycle_stage=None,
            recommendation_state=None,
            data_quality="fresh",
            metrics={},
            economics={},
            blockers=(),
            warnings=(),
            provenance=(),
            observed_at=observed_at,
        )
    )


def _publication(*rows: UniversalSignalRow) -> FamilyPublication:
    ordered = tuple(sorted(rows, key=lambda row: (row.signal_id, row.symbol)))
    return FamilyPublication(
        "synthetic-family",
        date(2026, 1, 2),
        tuple((row.signal_id, row.symbol) for row in ordered),
        ordered,
    )


def test_atomic_repository_rejects_stale_member_without_partial_write() -> None:
    repository = InMemoryLatestResultRepository()
    repository.upsert(_row("alpha", "AAPL", seconds=10))

    with pytest.raises(FamilyPublicationOrderingError):
        repository.publish_family(
            _publication(_row("alpha", "AAPL"), _row("alpha", "MSFT"))
        )

    assert repository.get_one("alpha", "MSFT") is None
    assert repository.get_one("alpha", "AAPL") == _row("alpha", "AAPL", seconds=10)


def test_identical_retry_is_success_but_same_identity_changed_manifest_conflicts() -> None:
    repository = InMemoryLatestResultRepository()
    publication = _publication(_row("alpha", "AAPL"))
    repository.publish_family(publication)
    repository.publish_family(publication)

    changed = replace(
        publication,
        rows=(replace(publication.rows[0], observation_id="different"),),
    )
    with pytest.raises(FamilyPublicationConflictError):
        repository.publish_family(changed)
    assert repository.get_family_publication(publication.publication_id) is not None


def test_history_is_invisible_until_family_commit_then_flush_is_idempotent() -> None:
    latest = InMemoryLatestResultRepository()
    history = InMemoryObservationHistoryRepository()
    staged_latest = StagedFamilyResultRepository(latest)
    staged_history = StagedObservationHistoryRepository(history)
    observation = OpportunityObservation(
        "opportunity-1",
        "alpha",
        "AAPL",
        "monitor",
        "pass",
        RecommendedAction.MONITOR,
        NOW,
    )
    staged_latest.upsert(_row("alpha", "AAPL"))
    staged_history.append(observation)

    assert history.history_for("opportunity-1") is None
    staged_latest.publish(
        family_id="synthetic-family",
        formation_date=date(2026, 1, 2),
        expected_members=(("alpha", "AAPL"),),
    )
    staged_history.flush()
    staged_history.append(observation)
    staged_history.flush()

    assert history.history_for("opportunity-1").observations == (observation,)  # type: ignore[union-attr]
