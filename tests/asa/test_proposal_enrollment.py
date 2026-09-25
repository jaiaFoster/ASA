"""ND-01: system-actionable proposal enrollment into forward outcomes.

Covers the eleven tests the Architect decision requires
(project/reports/OUTCOME-INTELLIGENCE-001-ND-01-ARCHITECT-DECISION.md §7).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from asa.application.forward_outcomes import ForwardOutcomeCollector
from asa.application.portfolio_lifecycle import (
    PortfolioReconciliationService,
    TrackCandidateService,
)
from asa.application.ports.forward_outcomes import ForwardOutcomeConflictError
from asa.application.proposal_enrollment import ProposalEnrollmentService
from asa.application.proposal_freezing import freeze_proposal
from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from asa.contracts.forward_outcome import ForwardOutcomeObservation
from asa.contracts.portfolio import PortfolioSnapshot
from asa.contracts.portfolio_lifecycle import ExecutionReadinessArtifact
from asa.contracts.proposal_enrollment import (
    ENROLLMENT_POLICY_VERSION,
    SYSTEM_ACTIONABLE,
    ProposalEnrollment,
    enrollment_id,
)
from strategy_runtime.executable_structures import serialize_execution_assessment
from strategy_runtime.forward_outcome import OutcomeStatus
from tests.asa.fakes import InMemoryLatestResultRepository, InMemoryObservationRepository
from tests.asa.test_forward_outcomes import (
    ANCHOR,
    D1,
    PROPOSAL,
    FakeEvidence,
    MemoryOutcomes,
    _candidate,
)
from tests.asa.test_modeled_pnl import _assessment
from tests.asa.test_portfolio_lifecycle import NOW, MemoryLifecycleRepository, _row

HEADERS = {"Authorization": "Bearer test-token"}


class MemoryEnrollments:
    def __init__(self) -> None:
        self.values: dict[UUID, ProposalEnrollment] = {}
        self.outcome_rows = MemoryOutcomes()

    def add(self, enrollment: ProposalEnrollment, maximum_per_session: int = 8) -> str:
        slot = (
            enrollment.signal_id,
            enrollment.signal_version,
            enrollment.symbol,
            enrollment.session_date,
        )
        taken = {
            (item.signal_id, item.signal_version, item.symbol, item.session_date)
            for item in self.values.values()
        }
        if enrollment.id in self.values or slot in taken:
            return "already_enrolled"
        if self.count_for_session(enrollment.session_date) >= maximum_per_session:
            return "enrollment_deferred_by_cap"
        self.values[enrollment.id] = enrollment
        return "enrolled"

    def slot_taken(
        self, signal_id: str, signal_version: str, symbol: str, session_date: date
    ) -> bool:
        return any(
            (item.signal_id, item.signal_version, item.symbol, item.session_date)
            == (signal_id, signal_version, symbol, session_date)
            for item in self.values.values()
        )

    def count_for_session(self, session_date: date) -> int:
        return sum(item.session_date == session_date for item in self.values.values())

    def enrollments(self) -> tuple[ProposalEnrollment, ...]:
        return tuple(self.values.values())

    def enrollment(self, value: UUID) -> ProposalEnrollment | None:
        return self.values.get(value)

    def append_outcome(self, observation: ForwardOutcomeObservation) -> ForwardOutcomeObservation:
        return self.outcome_rows.append(observation)

    def outcomes_for(self, value: UUID) -> tuple[ForwardOutcomeObservation, ...]:
        return self.outcome_rows.for_candidate(value)


def _artifact(observation_id: str = "observation-1", symbol: str = "AAPL"):  # type: ignore[no-untyped-def]
    assessment = replace(_assessment(), originating_result_identity=observation_id)
    return ExecutionReadinessArtifact(
        observation_id,
        "earnings_calendar",
        symbol,
        assessment.identity,
        "{}",
        serialize_execution_assessment(assessment),
        NOW,
    )


def _world(*rows):  # type: ignore[no-untyped-def]
    results = InMemoryLatestResultRepository()
    lifecycle = MemoryLifecycleRepository()
    for row in rows or (_row(),):
        results.upsert(row)
        lifecycle.put_execution_readiness(_artifact(row.observation_id, row.symbol))
    return results, lifecycle, MemoryEnrollments()


def test_system_enrollments_never_appear_in_tracking_or_reconciliation() -> None:
    results, lifecycle, enrollments = _world()
    summary = ProposalEnrollmentService(results, lifecycle, enrollments).enroll(
        [("earnings_calendar", "AAPL", "observation-1")], NOW
    )
    assert summary.enrolled == 1
    assert lifecycle.candidates() == ()
    snapshot = PortfolioSnapshot(
        observed_at=NOW,
        provider="fake",
        provider_request_id="r",
        accounts=(),
        equity_positions=(),
        option_legs=(),
    )
    assert PortfolioReconciliationService().reconcile_and_record(snapshot, lifecycle) == ()
    assert lifecycle.observations == []

    client = TestClient(
        build_application(
            Settings(agent_api_token="test-token", _env_file=None),
            DependencyOverrides(
                repository=InMemoryObservationRepository(),
                latest_result_repository=results,
                portfolio_lifecycle_repository=lifecycle,
                forward_outcome_repository=MemoryOutcomes(),
                proposal_enrollment_repository=enrollments,
            ),
        )
    )
    assert client.get("/api/v1/portfolio/tracked-candidates", headers=HEADERS).json() == []
    system = client.get("/api/v1/forward-outcomes/system-enrollments", headers=HEADERS).json()
    assert len(system) == 1
    assert system[0]["enrollment_source"] == SYSTEM_ACTIONABLE
    assert system[0]["also_tracked_by_user"] is False
    assert system[0]["exact_leg_set"] and system[0]["exact_leg_set"] == sorted(
        system[0]["exact_leg_set"]
    )
    assert system[0]["basis"].startswith("paper_modeled_not_brokerage_fill")
    assert {item["status"] for item in system[0]["outcomes"]} == {"pending"}


def test_user_tracking_an_enrolled_proposal_gets_its_own_record_and_clock() -> None:
    results, lifecycle, enrollments = _world()
    ProposalEnrollmentService(results, lifecycle, enrollments).enroll(
        [("earnings_calendar", "AAPL", "observation-1")], NOW
    )
    tracked_at = NOW + timedelta(hours=2)
    candidate = TrackCandidateService(results, lifecycle).track(
        "earnings_calendar", "AAPL", "observation-1", tracked_at
    )
    (enrolled,) = enrollments.enrollments()
    assert candidate.tracked_at == tracked_at
    assert enrolled.enrolled_at == NOW
    assert candidate.id != enrolled.id
    assert candidate.resolved_proposal_identity == enrolled.resolved_proposal_identity


def test_freezing_is_byte_identical_across_sources() -> None:
    results, lifecycle, enrollments = _world()
    ProposalEnrollmentService(results, lifecycle, enrollments).enroll(
        [("earnings_calendar", "AAPL", "observation-1")], NOW
    )
    candidate = TrackCandidateService(results, lifecycle).track(
        "earnings_calendar", "AAPL", "observation-1", NOW
    )
    (enrolled,) = enrollments.enrollments()
    assert enrolled.resolved_proposal_json == candidate.resolved_proposal_json
    assert json.loads(enrolled.resolved_proposal_json)["status"] == "available"


def test_stale_and_non_canonical_artifacts_are_never_enrolled() -> None:
    results, lifecycle, enrollments = _world()
    lifecycle.put_execution_readiness(_artifact("an-older-observation"))
    stale = ProposalEnrollmentService(results, lifecycle, enrollments).enroll(
        [("earnings_calendar", "AAPL", "observation-1"), ("earnings_calendar", "MISSING", "x")], NOW
    )
    assert stale.stale_or_missing_artifact == 2 and stale.enrolled == 0

    legacy = replace(_artifact(), assessment_json="{}")
    lifecycle.put_execution_readiness(legacy)
    frozen = freeze_proposal(_row(), legacy)
    assert frozen is not None and not frozen.is_canonical_trade_proposal
    summary = ProposalEnrollmentService(results, lifecycle, enrollments).enroll(
        [("earnings_calendar", "AAPL", "observation-1")], NOW
    )
    assert summary.not_actionable == 1 and enrollments.enrollments() == ()


def test_only_this_ticks_passing_observation_is_enrolled() -> None:
    results, lifecycle, enrollments = _world()
    service = ProposalEnrollmentService(results, lifecycle, enrollments)
    # The tick produced a different observation than the authoritative row.
    assert (
        service.enroll([("earnings_calendar", "AAPL", "tick-obs")], NOW).stale_or_missing_artifact
        == 1
    )
    results.upsert(replace(_row(), evaluation_state="no_signal"))
    assert (
        service.enroll(
            [("earnings_calendar", "AAPL", "observation-1")], NOW
        ).stale_or_missing_artifact
        == 1
    )
    assert enrollments.enrollments() == ()


def test_one_failing_pair_never_aborts_the_tick_and_clock_skew_is_skipped() -> None:
    rows = [replace(_row(f"obs-{symbol}"), symbol=symbol) for symbol in ("AAA", "BBB")]
    results, lifecycle, enrollments = _world(*rows)
    lifecycle.put_execution_readiness(
        replace(_artifact("obs-AAA", "AAA"), canonical_json="{broken")
    )
    summary = ProposalEnrollmentService(results, lifecycle, enrollments).enroll(
        [("earnings_calendar", "AAA", "obs-AAA"), ("earnings_calendar", "BBB", "obs-BBB")], NOW
    )
    assert (summary.enrollment_failed, summary.enrolled) == (1, 1)
    skewed = ProposalEnrollmentService(results, lifecycle, MemoryEnrollments()).enroll(
        [("earnings_calendar", "BBB", "obs-BBB")], NOW - timedelta(minutes=1)
    )
    assert skewed.evidence_after_clock == 1


def test_first_proposal_per_session_wins_cap_holds_and_replay_is_idempotent() -> None:
    rows = [replace(_row(f"obs-{symbol}"), symbol=symbol) for symbol in ("AAA", "BBB", "CCC")]
    results, lifecycle, enrollments = _world(*rows)
    service = ProposalEnrollmentService(results, lifecycle, enrollments, maximum_per_session=2)
    pairs = [("earnings_calendar", symbol, f"obs-{symbol}") for symbol in ("CCC", "AAA", "BBB")]

    first = service.enroll(pairs, NOW)
    assert (first.enrolled, first.enrollment_deferred_by_cap) == (2, 1)
    assert sorted(item.symbol for item in enrollments.enrollments()) == ["AAA", "BBB"]
    replay = service.enroll(pairs, NOW + timedelta(minutes=5))
    assert (replay.enrolled, replay.already_enrolled, replay.enrollment_deferred_by_cap) == (
        0,
        2,
        1,
    )

    # A later cycle the same session with a new proposal for AAA is ignored.
    results.upsert(replace(rows[0], observation_id="obs-AAA-later"))
    lifecycle.put_execution_readiness(_artifact("obs-AAA-later", "AAA"))
    uncapped = ProposalEnrollmentService(results, lifecycle, enrollments)
    later = uncapped.enroll(
        [("earnings_calendar", "AAA", "obs-AAA-later")], NOW + timedelta(hours=1)
    )
    assert later.already_enrolled == 1
    assert len([item for item in enrollments.enrollments() if item.symbol == "AAA"]) == 1


def test_enrollment_contract_rejects_foreign_ids_and_time_travel() -> None:
    base = dict(
        enrollment_policy_version=ENROLLMENT_POLICY_VERSION,
        originating_observation_id="o",
        opportunity_id=None,
        signal_id="s",
        signal_version="1",
        symbol="SPY",
        session_date=date(2026, 9, 24),
        evidence_observed_at=ANCHOR,
        enrolled_at=ANCHOR,
        resolved_proposal_identity="p",
        resolved_proposal_json="{}",
    )
    with pytest.raises(ValueError, match="derive"):
        ProposalEnrollment(id=UUID(int=1), **base)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="precede"):
        ProposalEnrollment(
            id=enrollment_id("p"),
            **{**base, "enrolled_at": ANCHOR - timedelta(seconds=1)},  # type: ignore[arg-type]
        )


def _enrollment(enrolled_at: datetime, symbol: str = "SPY", key: str = "p1") -> ProposalEnrollment:
    return ProposalEnrollment(
        id=enrollment_id(key),
        enrollment_policy_version=ENROLLMENT_POLICY_VERSION,
        originating_observation_id=f"obs-{key}",
        opportunity_id=None,
        signal_id="any-strategy",
        signal_version="1.0.0",
        symbol=symbol,
        session_date=date(2026, 9, 24),
        evidence_observed_at=ANCHOR,
        enrolled_at=enrolled_at,
        resolved_proposal_identity=key,
        resolved_proposal_json=json.dumps(PROPOSAL),
    )


def test_horizons_due_before_enrollment_are_not_observable() -> None:
    enrollments = MemoryEnrollments()
    enrollments.add(_enrollment(D1 + timedelta(hours=1)))
    collector = ForwardOutcomeCollector(
        MemoryLifecycleRepository(),
        MemoryOutcomes(),
        FakeEvidence(D1),
        enrollments=enrollments,
    )
    summary = collector.collect(D1 + timedelta(hours=2))
    (d1,) = [item for item in enrollments.outcomes_for(enrollment_id("p1"))]
    assert d1.horizon_id == "d1"
    assert d1.status is OutcomeStatus.NOT_OBSERVABLE_BEFORE_TRACKING
    assert summary.not_observable == 1


def test_subject_cap_is_shared_user_first_and_deferrals_are_per_source() -> None:
    lifecycle = MemoryLifecycleRepository()
    lifecycle.add_candidate(_candidate())
    enrollments = MemoryEnrollments()
    enrollments.add(_enrollment(ANCHOR, symbol="QQQ", key="p2"))
    evidence = FakeEvidence(D1 - timedelta(minutes=5))
    outcomes = MemoryOutcomes()
    collector = ForwardOutcomeCollector(
        lifecycle, outcomes, evidence, enrollments=enrollments, maximum_subjects_per_tick=1
    )
    summary = collector.collect(D1)
    assert evidence.calls[0][0] == "SPY"  # the user subject is served first
    assert summary.deferred_by_source == {SYSTEM_ACTIONABLE: 1}
    assert outcomes.rows[(_candidate().id, "d1")].status is OutcomeStatus.OBSERVED
    assert enrollments.outcomes_for(enrollment_id("p2")) == ()


def test_system_outcomes_record_modeled_values_like_user_outcomes() -> None:
    enrollments = MemoryEnrollments()
    enrollments.add(_enrollment(ANCHOR))
    collector = ForwardOutcomeCollector(
        MemoryLifecycleRepository(),
        MemoryOutcomes(),
        FakeEvidence(D1 - timedelta(minutes=5)),
        enrollments=enrollments,
    )
    collector.collect(D1)
    (d1,) = enrollments.outcomes_for(enrollment_id("p1"))
    assert d1.status is OutcomeStatus.OBSERVED
    assert d1.modeled_pnl == Decimal("249.50")
    assert d1.subject_id == enrollment_id("p1")


_NEW_MODULES = (
    "asa/application/proposal_enrollment.py",
    "asa/application/proposal_freezing.py",
    "asa/application/forward_outcomes.py",
    "asa/integrations/proposal_enrollment_postgres.py",
    "asa/api/forward_outcome_routes.py",
    "asa/contracts/proposal_enrollment.py",
    "asa/scheduled_enrollment.py",
)


def test_no_strategy_ids_brokers_or_latest_state_reads_in_new_modules() -> None:
    root = Path(__file__).resolve().parents[2]
    for module in _NEW_MODULES:
        source = (root / module).read_text()
        for forbidden in (
            '"earnings_calendar"',
            '"forward_factor"',
            '"skew_momentum"',
            '"spy_put_credit_spread"',
            '"B001"',
            '"B002"',
            "Broker",
            "broker_provider",
        ):
            assert forbidden not in source, (module, forbidden)
    collector = (root / "asa/application/forward_outcomes.py").read_text()
    for forbidden in ("execution_readiness", "get_one", "LatestResultRepository"):
        assert forbidden not in collector
    # No update or delete path in either ledger.
    for module in (
        "asa/integrations/proposal_enrollment_postgres.py",
        "asa/integrations/forward_outcome_postgres.py",
    ):
        source = (root / module).read_text().upper()
        assert re.search(r"UPDATE\s+\w+\s+SET|DELETE\s+FROM", source) is None, module


@pytest.mark.skipif(not os.getenv("ASA_TEST_DATABASE_URL"), reason="ASA_TEST_DATABASE_URL not set")
def test_postgres_enrollment_ledger_is_insert_only_idempotent_and_restricted() -> None:
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from asa.integrations.postgres import create_postgres_engine
    from asa.integrations.proposal_enrollment_postgres import (
        PostgresProposalEnrollmentRepository,
    )

    engine = create_postgres_engine(os.environ["ASA_TEST_DATABASE_URL"])
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM enrolled_proposal_outcome_observations"))
        connection.execute(text("DELETE FROM proposal_outcome_enrollments"))
    repository = PostgresProposalEnrollmentRepository(engine)
    enrollment = _enrollment(ANCHOR)
    assert repository.add(enrollment, 8) == "enrolled"
    assert repository.add(enrollment, 8) == "already_enrolled"
    same_slot = replace(_enrollment(ANCHOR, key="p-other"), signal_id=enrollment.signal_id)
    assert repository.add(same_slot, 8) == "already_enrolled"
    assert repository.add(_enrollment(ANCHOR, symbol="QQQ", key="p-cap"), 1) == (
        "enrollment_deferred_by_cap"
    )
    assert repository.count_for_session(date(2026, 9, 24)) == 1
    assert repository.enrollment(enrollment.id) == enrollment

    collector = ForwardOutcomeCollector(
        MemoryLifecycleRepository(),
        MemoryOutcomes(),
        FakeEvidence(D1 - timedelta(minutes=5)),
        enrollments=repository,
    )
    collector.collect(D1)
    (stored,) = repository.outcomes_for(enrollment.id)
    assert repository.append_outcome(stored) == stored
    with pytest.raises(ForwardOutcomeConflictError):
        repository.append_outcome(replace(stored, content_identity="0" * 64))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("DELETE FROM proposal_outcome_enrollments WHERE id = :id"),
            {"id": enrollment.id},
        )


def test_cron_hands_enrollment_only_this_ticks_passing_observations(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import asa.scheduled_screening as module

    tick = (
        module.PairOutcome("alpha", "AAA", "pass", 1, None, True, "obs-a"),
        module.PairOutcome("alpha", "BBB", "no_signal", 1, None, True, "obs-b"),
        module.PairOutcome("alpha", "CCC", None, None, "boom", False),
    )
    captured: list[tuple[str, str, str]] = []
    monkeypatch.setattr(module, "run_scheduled_refresh", lambda **_kwargs: tick)
    monkeypatch.setattr(module, "run_scheduled_stock_benchmark_refresh", lambda: ())
    monkeypatch.setattr(module, "run_scheduled_fixed_subject_option_refresh", lambda: ())
    monkeypatch.setattr(module, "run_scheduled_portfolio_refresh", lambda: None)
    monkeypatch.setattr(module, "run_scheduled_outcome_collection", lambda: None)
    monkeypatch.setattr(
        module, "run_scheduled_proposal_enrollment", lambda pairs: captured.extend(pairs)
    )
    module.main(["--json"])
    assert captured == [("alpha", "AAA", "obs-a")]
