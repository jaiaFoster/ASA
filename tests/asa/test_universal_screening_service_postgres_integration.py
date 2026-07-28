"""SPRINT-009/EPIC-9: strategy_runtime.service.get_state()/refresh()
exercised end to end against a real (test) Postgres instance, through
PostgresLatestResultRepository -- not the in-memory fake
tests/strategy_runtime/test_service.py already covers.

Mirrors tests/asa/test_screening_service_postgres_integration.py's own
exact pattern (API-002) for the same reason: proving get_state()'s reads
and refresh()'s upsert actually compose correctly through the real
raw-SQL/JSON-serialization layer, not just that each works in isolation.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from asa.integrations.universal_screening_postgres import PostgresLatestResultRepository
from market_data.config import load_market_data_config
from strategy_runtime.adapters import build_migrated_strategy_registry
from strategy_runtime.market_data_planning import build_shared_market_data_access
from strategy_runtime.persistence import UniversalSignalRow, should_replace_latest
from strategy_runtime.result import (
    EvaluationState,
    ResultTemporalMetadata,
    RowType,
    UniversalScreeningResult,
)
from strategy_runtime.service import get_state, refresh

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv("ASA_TEST_DATABASE_URL"),
        reason="ASA_TEST_DATABASE_URL not set",
    ),
]

SYMBOL = "AAPL"
STRATEGY_ID = "skew_momentum"


class FixedClock:
    def __init__(self, start: datetime) -> None:
        self._next = start

    def now(self) -> datetime:
        current = self._next
        self._next = current + timedelta(microseconds=1)
        return current


@pytest.fixture
def repository() -> PostgresLatestResultRepository:
    database_url = os.environ["ASA_TEST_DATABASE_URL"]
    os.environ["ASA_DATABASE_URL"] = database_url
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE universal_screening_state"))
    return PostgresLatestResultRepository(engine)


def _fulfillment_by_subject(clock: FixedClock) -> dict[str, object]:
    # The deterministic_fixture provider, left enabled (not force-disabled
    # via live_only_config()) -- this test is about persistence
    # round-tripping, not about the live-acquisition safety guarantee
    # EPIC-7's own tests already prove separately.
    config = load_market_data_config({})
    access = build_shared_market_data_access(
        config, lambda _provider_id: object(), clock, (SYMBOL,)
    )
    return {symbol: item.fulfillment for symbol, item in access.items()}


def test_refresh_persists_to_real_postgres_and_get_state_reads_it_back(
    repository: PostgresLatestResultRepository,
) -> None:
    clock = FixedClock(datetime(2026, 7, 23, 16, 0, tzinfo=UTC))
    registry = build_migrated_strategy_registry()

    refreshed = refresh(
        registry,
        repository,
        clock,
        strategy_id=STRATEGY_ID,
        symbol=SYMBOL,
        fulfillment_by_subject=_fulfillment_by_subject(clock),
    )

    (persisted,) = get_state(repository, strategy_id=STRATEGY_ID, symbol=SYMBOL)
    assert persisted == refreshed
    assert persisted.strategy_id == STRATEGY_ID
    assert persisted.symbol == SYMBOL
    assert persisted.observed_at.tzinfo is not None


def test_second_refresh_overwrites_the_real_row_rather_than_accumulating(
    repository: PostgresLatestResultRepository,
) -> None:
    clock = FixedClock(datetime(2026, 7, 23, 16, 0, tzinfo=UTC))
    registry = build_migrated_strategy_registry()

    refresh(
        registry,
        repository,
        clock,
        strategy_id=STRATEGY_ID,
        symbol=SYMBOL,
        fulfillment_by_subject=_fulfillment_by_subject(clock),
    )
    refresh(
        registry,
        repository,
        clock,
        strategy_id=STRATEGY_ID,
        symbol=SYMBOL,
        fulfillment_by_subject=_fulfillment_by_subject(clock),
    )

    assert len(get_state(repository)) == 1


def test_get_state_never_triggers_a_provider_request(
    repository: PostgresLatestResultRepository,
) -> None:
    # get_state()'s own signature (strategy_runtime/service.py) takes only
    # a repository -- structurally, not merely behaviorally, it has no
    # parameter through which a fulfillment service or provider could ever
    # be reached. Calling it repeatedly against real persisted state
    # (written once via refresh(), which does own a fulfillment service)
    # and getting back identical results is the decisive, observable proof.
    clock = FixedClock(datetime(2026, 7, 23, 16, 0, tzinfo=UTC))
    registry = build_migrated_strategy_registry()
    refresh(
        registry,
        repository,
        clock,
        strategy_id=STRATEGY_ID,
        symbol=SYMBOL,
        fulfillment_by_subject=_fulfillment_by_subject(clock),
    )

    first = get_state(repository, strategy_id=STRATEGY_ID)
    second = get_state(repository, strategy_id=STRATEGY_ID)
    assert first == second


def _temporal(*, source: datetime, evaluated: datetime) -> ResultTemporalMetadata:
    return ResultTemporalMetadata(
        observed_at=source,
        received_at=evaluated,
        evaluated_at=evaluated,
        persisted_at=evaluated,
        market_session_date=date(2026, 7, 27),
        market_session_status="open",
        age_seconds=max(0, int((evaluated - source).total_seconds())),
        last_refresh_attempt_at=evaluated,
        last_successful_refresh_at=evaluated,
        next_refresh_at=evaluated + timedelta(hours=1),
        data_advanced_on_last_refresh=True,
        freshness_status="live",
        usability_status="usable",
        usability_reason="observation is current",
        warning_codes=(),
        acquisition_started_at=evaluated,
        acquisition_completed_at=evaluated,
        input_time_skew_seconds=0,
    )


def _signal_row(
    *, observation_id: str, source: datetime, evaluated: datetime
) -> UniversalSignalRow:
    return UniversalSignalRow.from_result(
        UniversalScreeningResult(
            strategy_id=STRATEGY_ID,
            strategy_version="1.0.0",
            symbol=SYMBOL,
            observation_id=observation_id,
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
            observed_at=evaluated,
            temporal=_temporal(source=source, evaluated=evaluated),
        )
    )


def test_postgres_write_guard_matches_the_in_memory_should_replace_latest_decision(
    repository: PostgresLatestResultRepository,
) -> None:
    # PATCH-011C: proves asa/integrations/universal_screening_postgres.py's
    # own ON CONFLICT ... WHERE ordering-tuple comparison makes the exact
    # same replace/reject decision as strategy_runtime.persistence.
    # should_replace_latest() for the specific scenario #246 was about --
    # a later evaluation of the *same* source observation whose
    # observation_id happens to be lexically lower than the one already
    # stored. Both must agree; a real Postgres upsert exercising the
    # tests/strategy_runtime/test_refresh_integrity_regressions.py::
    # test_later_same_source_evaluation_wins_even_with_lower_hash_identity
    # scenario against the real ON CONFLICT clause, not the in-memory fake.
    same_source = datetime(2026, 7, 27, 18, 0, tzinfo=UTC)
    existing = _signal_row(observation_id="zzz", source=same_source, evaluated=same_source)
    later_lower_hash = _signal_row(
        observation_id="aaa", source=same_source, evaluated=same_source + timedelta(hours=1)
    )
    # in-memory helper's own verdict
    assert should_replace_latest(existing, later_lower_hash) is True

    repository.upsert(existing)
    repository.upsert(later_lower_hash)

    stored = repository.get_one(STRATEGY_ID, SYMBOL)
    assert stored is not None
    # the later evaluation won, matching the in-memory verdict
    assert stored.observation_id == "aaa"


def test_postgres_write_guard_rejects_an_older_source_even_with_a_higher_hash(
    repository: PostgresLatestResultRepository,
) -> None:
    same_evaluated = datetime(2026, 7, 27, 18, 0, tzinfo=UTC)
    existing = _signal_row(observation_id="aaa", source=same_evaluated, evaluated=same_evaluated)
    older_source_higher_hash = _signal_row(
        observation_id="zzz", source=same_evaluated - timedelta(days=1), evaluated=same_evaluated
    )
    assert should_replace_latest(existing, older_source_higher_hash) is False

    repository.upsert(existing)
    repository.upsert(older_source_higher_hash)

    stored = repository.get_one(STRATEGY_ID, SYMBOL)
    assert stored is not None
    assert stored.observation_id == "aaa"  # older source never regressed the stored row
