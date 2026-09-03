import json
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
    ExecutionReadinessArtifact,
    PositionLifecycleState,
    ReconciliationState,
    TrackedCandidate,
)
from asa.integrations.portfolio_lifecycle_postgres import _candidate_params
from asa.integrations.providers.deterministic_fake_broker import (
    DeterministicFakeBrokerPortfolioProvider,
)
from strategy_runtime.persistence import UniversalSignalRow
from strategy_runtime.values import TypedValue
from tests.asa.fakes import InMemoryLatestResultRepository, InMemoryObservationRepository

NOW = datetime(2026, 8, 28, 12, tzinfo=UTC)


def test_postgres_candidate_params_encode_exact_symbols_as_jsonb_text() -> None:
    candidate = TrackedCandidate(
        id=uuid4(),
        originating_observation_id="observation-1",
        opportunity_id=None,
        strategy_id="forward_factor",
        strategy_version="1.3.0",
        symbol="BKNG",
        tracked_at=NOW,
        originating_observed_at=NOW,
        evidence_observed_at=NOW,
        exact_option_symbols=("BKNG261120C00200000", "BKNG261218C00200000"),
    )

    encoded = _candidate_params(candidate)["exact_option_symbols"]

    assert isinstance(encoded, str)
    assert json.loads(encoded) == list(candidate.exact_option_symbols)


class MemoryLifecycleRepository:
    def __init__(self) -> None:
        self.values = {}
        self.associations_values = []
        self.observations = []
        self.readiness = {}

    def put_execution_readiness(self, artifact):
        self.readiness[(artifact.strategy_id, artifact.symbol)] = artifact

    def execution_readiness(self, strategy_id, symbol):
        return self.readiness.get((strategy_id, symbol))

    def add_candidate(self, candidate):
        self.values.setdefault(candidate.id, candidate)
        return self.values[candidate.id]

    def candidates(self):
        return tuple(self.values.values())

    def candidate(self, candidate_id):
        return self.values.get(candidate_id)

    def append_association(self, association):
        self.associations_values.append(association)

    def append_lifecycle_observation(self, observation):
        if observation not in self.observations:
            self.observations.append(observation)

    def lifecycle_observations(self, candidate_id):
        return tuple(
            item for item in self.observations if item.tracked_candidate_id == candidate_id
        )

    def associations(self, candidate_id):
        return tuple(
            item for item in self.associations_values if item.tracked_candidate_id == candidate_id
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


def test_track_this_freezes_resolved_proposal_across_later_chain_refresh() -> None:
    results = InMemoryLatestResultRepository()
    results.upsert(_row())
    lifecycle = MemoryLifecycleRepository()
    original = ExecutionReadinessArtifact(
        "observation-1",
        "earnings_calendar",
        "AAPL",
        "assessment-1",
        '{"status":"constructible_as_intended"}',
        '{"internal":"assessment-1"}',
        NOW,
    )
    lifecycle.put_execution_readiness(original)

    tracked = TrackCandidateService(results, lifecycle).track(
        "earnings_calendar", "AAPL", "observation-1", NOW
    )
    lifecycle.put_execution_readiness(
        replace(
            original,
            assessment_identity="assessment-2",
            canonical_json='{"status":"not_constructible"}',
            assessed_at=NOW + timedelta(minutes=10),
        )
    )

    assert lifecycle.candidate(tracked.id) == tracked
    assert tracked.resolved_proposal_identity == "assessment-1"
    assert tracked.resolved_proposal_json == '{"status":"constructible_as_intended"}'


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

    listing = client.get(
        "/api/v1/portfolio/tracked-candidates",
        headers={"Authorization": "Bearer test-token"},
    )
    detail = client.get(
        f"/api/v1/portfolio/tracked-candidates/{response.json()['id']}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert len(listing.json()) == 1
    assert detail.json()["candidate"]["originating_observation_id"] == "observation-1"
    assert detail.json()["exit_policy_status"] == "not_defined"


def test_execution_readiness_api_and_tracking_share_immutable_artifact() -> None:
    results = InMemoryLatestResultRepository()
    results.upsert(_row())
    lifecycle = MemoryLifecycleRepository()
    payload = {
        "assessment_identity": "assessment-1",
        "originating_result_identity": "observation-1",
        "subject": "AAPL",
        "intended_structure_kind": "calendar",
        "status": "not_constructible",
        "available_structure_kind": None,
        "exact_legs": [],
        "selection_diagnostics": [],
        "modeled_entry": None,
        "evidence_snapshot_identity": "snapshot-1",
        "assessed_at": NOW.isoformat().replace("+00:00", "Z"),
        "reason_code": "no_compatible_contract",
    }
    import json

    lifecycle.put_execution_readiness(
        ExecutionReadinessArtifact(
            "observation-1",
            "earnings_calendar",
            "AAPL",
            "assessment-1",
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            '{"internal":"assessment-1"}',
            NOW,
        )
    )
    app = build_application(
        Settings(agent_api_token="test-token", _env_file=None),
        DependencyOverrides(
            repository=InMemoryObservationRepository(),
            latest_result_repository=results,
            portfolio_lifecycle_repository=lifecycle,
        ),
    )
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-token"}

    readiness = client.get(
        "/api/v1/screening/earnings_calendar/AAPL/execution-readiness",
        headers=headers,
    )
    tracked = client.post(
        "/api/v1/portfolio/tracked-candidates",
        headers=headers,
        json={
            "strategy_id": "earnings_calendar",
            "symbol": "AAPL",
            "observation_id": "observation-1",
        },
    )

    assert readiness.status_code == 200
    assert readiness.json()["signal"]["observation_id"] == "observation-1"
    assert readiness.json()["execution_assessment"]["status"] == "not_constructible"
    assert tracked.json()["resolved_proposal_identity"] == "assessment-1"
    assert tracked.json()["resolved_proposal"]["reason_code"] == "no_compatible_contract"


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
