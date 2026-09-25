"""OUTCOME-INTELLIGENCE OI-03/OI-04: collector, ledger, and read API."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from asa.application.forward_outcomes import ForwardOutcomeCollector
from asa.application.ports.forward_outcomes import (
    ForwardOutcomeConflictError,
    OutcomeEvidence,
)
from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from asa.contracts.forward_outcome import ForwardOutcomeObservation
from asa.contracts.portfolio_lifecycle import TrackedCandidate
from strategy_runtime.forward_outcome import LegQuote, OutcomeStatus
from tests.asa.fakes import InMemoryObservationRepository
from tests.asa.test_portfolio_lifecycle import MemoryLifecycleRepository

# Anchor Thursday 2026-09-24 19:00Z; d1 = Friday 2026-09-25 20:00Z close.
ANCHOR = datetime(2026, 9, 24, 19, 0, tzinfo=UTC)
D1 = datetime(2026, 9, 25, 20, 0, tzinfo=UTC)
EXPIRY = date(2026, 10, 23)
PROPOSAL = {
    "status": "available",
    "legs": [
        {
            "canonical_contract_identity": "P715",
            "buy_or_sell": "buy",
            "call_or_put": "put",
            "strike": "715",
            "expiration": EXPIRY.isoformat(),
            "quantity": "1",
        },
        {
            "canonical_contract_identity": "P755",
            "buy_or_sell": "sell",
            "call_or_put": "put",
            "strike": "755",
            "expiration": EXPIRY.isoformat(),
            "quantity": "1",
        },
    ],
    "modeled_entry": {"modeled_net_debit_or_credit": "-4.595"},
}


def _candidate(*, tracked_at: datetime = ANCHOR, proposal: bool = True) -> TrackedCandidate:
    return TrackedCandidate(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        originating_observation_id="obs-1",
        opportunity_id=None,
        strategy_id="any-strategy",
        strategy_version="1.0.0",
        symbol="SPY",
        tracked_at=tracked_at,
        originating_observed_at=ANCHOR,
        evidence_observed_at=ANCHOR,
        exact_option_symbols=(),
        resolved_proposal_identity="proposal-1" if proposal else None,
        resolved_proposal_json=json.dumps(PROPOSAL) if proposal else None,
    )


class MemoryOutcomes:
    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, str], ForwardOutcomeObservation] = {}

    def append(self, observation: ForwardOutcomeObservation) -> ForwardOutcomeObservation:
        key = (observation.tracked_candidate_id, observation.horizon_id)
        stored = self.rows.setdefault(key, observation)
        if stored.content_identity != observation.content_identity:
            raise ForwardOutcomeConflictError("conflict")
        return stored

    def for_candidate(self, candidate_id: UUID) -> tuple[ForwardOutcomeObservation, ...]:
        return tuple(v for (c, _), v in sorted(self.rows.items()) if c == candidate_id)


class FakeEvidence:
    def __init__(self, observed_at: datetime) -> None:
        self.observed_at = observed_at
        self.calls: list[tuple[str, tuple[date, ...]]] = []

    def collect(self, symbol: str, expirations: tuple[date, ...], now: datetime) -> OutcomeEvidence:
        self.calls.append((symbol, expirations))
        return OutcomeEvidence(
            underlying_price=Decimal("760"),
            underlying_observed_at=self.observed_at,
            leg_quotes={
                "P715": LegQuote(Decimal("1.00"), Decimal("1.20")),
                "P755": LegQuote(Decimal("3.00"), Decimal("3.40")),
            },
            chain_observed_at=self.observed_at,
            provenance=("observation:q", "observation:c"),
        )


def _collector(candidate: TrackedCandidate, evidence: FakeEvidence, **kwargs):  # type: ignore[no-untyped-def]
    lifecycle = MemoryLifecycleRepository()
    lifecycle.add_candidate(candidate)
    outcomes = MemoryOutcomes()
    return ForwardOutcomeCollector(lifecycle, outcomes, evidence, **kwargs), outcomes


def test_in_window_evidence_records_a_modeled_outcome_once() -> None:
    evidence = FakeEvidence(D1 - timedelta(minutes=5))
    collector, outcomes = _collector(_candidate(), evidence)

    summary = collector.collect(D1)
    d1 = outcomes.rows[(_candidate().id, "d1")]

    assert summary.observed == 1 and summary.pending >= 1
    assert d1.status is OutcomeStatus.OBSERVED
    assert d1.modeled_mark == Decimal("-210.00")
    assert d1.modeled_pnl == Decimal("249.50")
    assert d1.mark_basis == "modeled_midpoint_mark_not_fill"
    assert evidence.calls == [("SPY", (EXPIRY,))]
    # Golden: a payload change would conflict with every stored ledger row.
    assert d1.content_identity == (
        "f99d90cf975e0b33dd27f0d1a6ad68b28d5a6ea143ac6a9b296000c6ad906459"
    )
    # First eligible observation is final; a later tick never rewrites it.
    collector.collect(D1 + timedelta(minutes=5))
    assert outcomes.rows[(_candidate().id, "d1")] == d1


def test_stale_evidence_is_never_accepted_and_the_window_then_records_missed() -> None:
    evidence = FakeEvidence(D1 - timedelta(hours=3))  # provider served a stale quote
    collector, outcomes = _collector(_candidate(), evidence)

    first = collector.collect(D1)
    assert first.evidence_outside_window == 1
    assert (_candidate().id, "d1") not in outcomes.rows

    later = collector.collect(D1 + timedelta(minutes=11))
    assert later.missed >= 1
    missed = outcomes.rows[(_candidate().id, "d1")]
    assert missed.status is OutcomeStatus.MISSED
    assert missed.modeled_mark is None and missed.observed_at is None


def test_nothing_is_fetched_before_the_window_opens() -> None:
    evidence = FakeEvidence(D1)
    collector, outcomes = _collector(_candidate(), evidence)

    summary = collector.collect(D1 - timedelta(hours=1))

    assert summary.pending >= 1 and not outcomes.rows and not evidence.calls


def test_horizons_due_before_tracking_are_not_observable() -> None:
    candidate = _candidate(tracked_at=D1 + timedelta(days=1))
    collector, outcomes = _collector(candidate, FakeEvidence(D1))

    collector.collect(D1 + timedelta(days=1))

    assert outcomes.rows[(candidate.id, "d1")].status is (
        OutcomeStatus.NOT_OBSERVABLE_BEFORE_TRACKING
    )


def test_stock_or_legacy_candidates_record_underlying_only() -> None:
    evidence = FakeEvidence(D1)
    collector, outcomes = _collector(_candidate(proposal=False), evidence)

    collector.collect(D1)
    d1 = outcomes.rows[(_candidate().id, "d1")]

    assert evidence.calls == [("SPY", ())]
    assert d1.underlying_price == Decimal("760") and d1.modeled_pnl is None
    assert "no_frozen_structure_entry" in d1.unknown_reasons


def test_subject_cap_defers_rather_than_drops() -> None:
    evidence = FakeEvidence(D1)
    lifecycle = MemoryLifecycleRepository()
    lifecycle.add_candidate(_candidate())
    other = replace(_candidate(), id=uuid4(), originating_observation_id="obs-2", symbol="QQQ")
    lifecycle.add_candidate(other)
    outcomes = MemoryOutcomes()

    summary = ForwardOutcomeCollector(
        lifecycle, outcomes, evidence, maximum_subjects_per_tick=1
    ).collect(D1)

    assert summary.observed == 1 and summary.deferred_by_subject_cap == 1


def test_conflicting_outcome_for_a_recorded_horizon_fails_closed() -> None:
    evidence = FakeEvidence(D1)
    collector, outcomes = _collector(_candidate(), evidence)
    collector.collect(D1)
    stored = outcomes.rows[(_candidate().id, "d1")]

    with pytest.raises(ForwardOutcomeConflictError):
        outcomes.append(replace(stored, content_identity="0" * 64))


def test_new_modules_are_strategy_blind_and_never_read_latest_state() -> None:
    root = Path(__file__).parents[2]
    for relative in (
        "asa/application/forward_outcomes.py",
        "asa/integrations/forward_outcome_market_data.py",
        "asa/integrations/forward_outcome_postgres.py",
        "asa/scheduled_outcomes.py",
    ):
        source = (root / relative).read_text()
        for forbidden in (
            "earnings_calendar",
            "forward_factor",
            "skew_momentum",
            "spy_put_credit_spread",
            "universal_screening_state",
            "execution_readiness",
            "LatestResultRepository",
            "BrokerPortfolioProvider",
            "broker_provider",
        ):
            assert forbidden not in source, (relative, forbidden)


def _app(outcomes: MemoryOutcomes, lifecycle: MemoryLifecycleRepository) -> TestClient:
    return TestClient(
        build_application(
            Settings(agent_api_token="t", _env_file=None),
            DependencyOverrides(
                repository=InMemoryObservationRepository(),
                portfolio_lifecycle_repository=lifecycle,  # type: ignore[arg-type]
                forward_outcome_repository=outcomes,
            ),
        )
    )


def test_outcomes_api_shows_recorded_and_pending_horizons_and_404s_unknown() -> None:
    lifecycle = MemoryLifecycleRepository()
    lifecycle.add_candidate(_candidate())
    outcomes = MemoryOutcomes()
    ForwardOutcomeCollector(lifecycle, outcomes, FakeEvidence(D1)).collect(D1)
    client = _app(outcomes, lifecycle)
    headers = {"Authorization": "Bearer t"}

    response = client.get(
        f"/api/v1/portfolio/tracked-candidates/{_candidate().id}/outcomes", headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    statuses = {item["horizon_id"]: item["status"] for item in body["outcomes"]}
    assert statuses == {
        "d1": "observed",
        "d5": "pending",
        "d10": "pending",
        "first_expiration": "pending",
    }
    assert "not_brokerage_fill" in body["basis"]
    missing = client.get(
        f"/api/v1/portfolio/tracked-candidates/{uuid4()}/outcomes", headers=headers
    )
    assert missing.status_code == 404


@pytest.mark.skipif(not os.getenv("ASA_TEST_DATABASE_URL"), reason="ASA_TEST_DATABASE_URL not set")
def test_postgres_ledger_is_append_only_idempotent_and_restricts_deletes() -> None:
    from sqlalchemy import text

    from asa.integrations.forward_outcome_postgres import PostgresForwardOutcomeRepository
    from asa.integrations.portfolio_lifecycle_postgres import PostgresPortfolioLifecycleRepository
    from asa.integrations.postgres import create_postgres_engine

    engine = create_postgres_engine(os.environ["ASA_TEST_DATABASE_URL"])
    candidate = replace(_candidate(), id=uuid4(), originating_observation_id=f"obs-{uuid4()}")
    PostgresPortfolioLifecycleRepository(engine).add_candidate(candidate)
    lifecycle = MemoryLifecycleRepository()
    lifecycle.add_candidate(candidate)
    ledger = PostgresForwardOutcomeRepository(engine)
    ForwardOutcomeCollector(lifecycle, ledger, FakeEvidence(D1)).collect(D1)

    stored = ledger.for_candidate(candidate.id)
    assert [item.horizon_id for item in stored] == ["d1"]
    assert stored[0].modeled_pnl == Decimal("249.50")
    assert ledger.append(stored[0]) == stored[0]  # idempotent replay
    with pytest.raises(ForwardOutcomeConflictError):
        ledger.append(replace(stored[0], content_identity="0" * 64))
    assert not hasattr(ledger, "update") and not hasattr(ledger, "delete")
    with (
        pytest.raises(Exception, match="(?i)foreign key|violates"),
        engine.begin() as connection,
    ):
        connection.execute(
            text("DELETE FROM tracked_candidates WHERE id = :id"), {"id": candidate.id}
        )


def test_same_symbol_subjects_with_different_expirations_never_share_evidence() -> None:
    later = replace(
        _candidate(),
        id=UUID("22222222-2222-2222-2222-222222222222"),
        originating_observation_id="obs-2",
        resolved_proposal_identity="proposal-2",
        resolved_proposal_json=json.dumps(
            {
                **PROPOSAL,
                "legs": [
                    {**leg, "expiration": "2026-11-20"}
                    for leg in PROPOSAL["legs"]  # type: ignore[index]
                ],
            }
        ),
    )
    lifecycle = MemoryLifecycleRepository()
    lifecycle.add_candidate(_candidate())
    lifecycle.add_candidate(later)
    evidence = FakeEvidence(D1 - timedelta(minutes=5))
    ForwardOutcomeCollector(lifecycle, MemoryOutcomes(), evidence).collect(D1)
    assert sorted(evidence.calls) == [("SPY", (EXPIRY,)), ("SPY", (date(2026, 11, 20),))]
