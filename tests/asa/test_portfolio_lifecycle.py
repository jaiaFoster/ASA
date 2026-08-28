from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from asa.application.portfolio_lifecycle import (
    CandidateNotFoundError,
    PortfolioReconciliationService,
    TrackCandidateService,
)
from asa.application.portfolio_use_cases import RunPortfolioIntelligence
from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from asa.contracts.portfolio_lifecycle import (
    PositionLifecycleState,
    ReconciliationState,
)
from asa.integrations.providers.deterministic_fake_broker import (
    DeterministicFakeBrokerPortfolioProvider,
)
from strategy_runtime.persistence import UniversalSignalRow
from strategy_runtime.values import TypedValue
from tests.asa.fakes import InMemoryLatestResultRepository, InMemoryObservationRepository

NOW = datetime(2026, 8, 28, 12, tzinfo=UTC)


class MemoryLifecycleRepository:
    def __init__(self) -> None:
        self.values = {}
        self.associations = []
        self.observations = []

    def add_candidate(self, candidate):
        self.values.setdefault(candidate.id, candidate)
        return self.values[candidate.id]

    def candidates(self):
        return tuple(self.values.values())

    def candidate(self, candidate_id):
        return self.values.get(candidate_id)

    def append_association(self, association):
        self.associations.append(association)

    def append_lifecycle_observation(self, observation):
        if observation not in self.observations:
            self.observations.append(observation)

    def lifecycle_observations(self, candidate_id):
        return tuple(
            item for item in self.observations if item.tracked_candidate_id == candidate_id
        )


def _row(observation_id: str = "observation-1") -> UniversalSignalRow:
    return UniversalSignalRow(
        signal_id="earnings_calendar",
        signal_version="1.2.0",
        symbol="AAPL",
        observation_id=observation_id,
        opportunity_id="opportunity-1",
        row_type="result",
        verdict="PASS",
        evaluation_state="pass",
        lifecycle_stage="candidate",
        recommendation_state="monitor",
        data_quality="complete",
        metrics={
            "decision.option_symbols": TypedValue.of_structured(
                ["AAPL260918C00200000", "AAPL260918C00210000"]
            )
        },
        economics={},
        blockers=(),
        warnings=(),
        provenance=("snapshot-1",),
        observed_at=NOW,
    )


def test_track_this_is_idempotent_and_bound_to_exact_latest_observation() -> None:
    results = InMemoryLatestResultRepository()
    results.upsert(_row())
    lifecycle = MemoryLifecycleRepository()
    service = TrackCandidateService(results, lifecycle)

    first = service.track("earnings_calendar", "aapl", "observation-1", NOW)
    second = service.track("earnings_calendar", "AAPL", "observation-1", NOW)

    assert first == second
    assert first.originating_observation_id == "observation-1"
    assert first.opportunity_id == "opportunity-1"
    assert first.exact_option_symbols == (
        "AAPL260918C00200000",
        "AAPL260918C00210000",
    )
    assert first.evidence_observed_at == NOW


def test_track_this_rejects_stale_or_invented_observation_identity() -> None:
    results = InMemoryLatestResultRepository()
    results.upsert(_row())

    with pytest.raises(CandidateNotFoundError):
        TrackCandidateService(results, MemoryLifecycleRepository()).track(
            "earnings_calendar", "AAPL", "different-observation", NOW
        )


def test_exact_option_evidence_uniquely_associates_held_position() -> None:
    results = InMemoryLatestResultRepository()
    results.upsert(_row())
    lifecycle = MemoryLifecycleRepository()
    candidate = TrackCandidateService(results, lifecycle).track(
        "earnings_calendar", "AAPL", "observation-1", NOW
    )
    provider = DeterministicFakeBrokerPortfolioProvider()
    snapshot = RunPortfolioIntelligence._normalize(
        provider.fetch_accounts(), provider.fetch_positions()
    )

    associations = PortfolioReconciliationService().reconcile(snapshot, (candidate,))

    assert len(associations) == 1
    assert associations[0].tracked_candidate_id == candidate.id
    assert associations[0].state is ReconciliationState.MATCHED
    assert associations[0].is_associated is True


def test_duplicate_exact_candidates_remain_ambiguous_and_unassociated() -> None:
    results = InMemoryLatestResultRepository()
    results.upsert(_row())
    lifecycle = MemoryLifecycleRepository()
    first = TrackCandidateService(results, lifecycle).track(
        "earnings_calendar", "AAPL", "observation-1", NOW
    )
    second = replace(
        first,
        id=uuid4(),
        originating_observation_id="observation-2",
    )
    provider = DeterministicFakeBrokerPortfolioProvider()
    snapshot = RunPortfolioIntelligence._normalize(
        provider.fetch_accounts(), provider.fetch_positions()
    )

    findings = PortfolioReconciliationService().reconcile(snapshot, (first, second))

    assert len(findings) == 2
    assert {item.state for item in findings} == {ReconciliationState.AMBIGUOUS}
    assert not any(item.is_associated for item in findings)


def test_equity_symbol_alone_never_manufactures_provenance() -> None:
    candidate = replace(_row(), metrics={})
    results = InMemoryLatestResultRepository()
    results.upsert(candidate)
    lifecycle = MemoryLifecycleRepository()
    tracked = TrackCandidateService(results, lifecycle).track(
        "earnings_calendar", "AAPL", "observation-1", NOW
    )
    provider = DeterministicFakeBrokerPortfolioProvider()
    snapshot = RunPortfolioIntelligence._normalize(
        provider.fetch_accounts(), provider.fetch_positions()
    )

    before = snapshot
    assert PortfolioReconciliationService().reconcile(snapshot, (tracked,)) == ()
    assert snapshot == before
    assert snapshot.equity_positions[0].symbol == "AAPL"


def test_track_this_api_uses_exact_persisted_observation() -> None:
    results = InMemoryLatestResultRepository()
    results.upsert(_row())
    lifecycle = MemoryLifecycleRepository()
    app = build_application(
        Settings(agent_api_token="test-token", _env_file=None),
        DependencyOverrides(
            repository=InMemoryObservationRepository(),
            latest_result_repository=results,
            portfolio_lifecycle_repository=lifecycle,
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/portfolio/tracked-candidates",
        headers={"Authorization": "Bearer test-token"},
        json={
            "strategy_id": "earnings_calendar",
            "symbol": "AAPL",
            "observation_id": "observation-1",
        },
    )

    assert response.status_code == 200
    assert response.json()["originating_observation_id"] == "observation-1"
    assert response.json()["opportunity_id"] == "opportunity-1"


def test_lifecycle_observations_append_open_then_closed_with_separate_clocks() -> None:
    results = InMemoryLatestResultRepository()
    results.upsert(_row())
    lifecycle = MemoryLifecycleRepository()
    candidate = TrackCandidateService(results, lifecycle).track(
        "earnings_calendar", "AAPL", "observation-1", NOW
    )
    candidate = replace(candidate, evidence_observed_at=NOW - timedelta(minutes=5))
    lifecycle.values[candidate.id] = candidate
    provider = DeterministicFakeBrokerPortfolioProvider()
    open_snapshot = RunPortfolioIntelligence._normalize(
        provider.fetch_accounts(), provider.fetch_positions()
    )
    service = PortfolioReconciliationService()

    service.reconcile_and_record(open_snapshot, lifecycle)
    closed_snapshot = replace(
        open_snapshot,
        observed_at=open_snapshot.observed_at + timedelta(hours=1),
        option_legs=(),
    )
    service.reconcile_and_record(closed_snapshot, lifecycle)

    observations = lifecycle.lifecycle_observations(candidate.id)
    assert [item.state for item in observations] == [
        PositionLifecycleState.OPEN,
        PositionLifecycleState.CLOSED,
    ]
    assert observations[0].broker_observed_at == open_snapshot.observed_at
    assert observations[0].strategy_result_observed_at == NOW
    assert observations[0].evidence_observed_at == NOW - timedelta(minutes=5)
    assert lifecycle.candidate(candidate.id) == candidate
