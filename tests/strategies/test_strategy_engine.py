"""ASA-CORE-005: strategy engine tests — determinism, replay, provenance."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from domain.canonical_fact import CanonicalFact
from domain.opportunity import RecommendationState
from domain.provenance import Provenance
from domain.references import Confidence, EvidenceKind
from indicators.engine import compute_indicator
from strategies.engine import evaluate_strategy, opportunity_identity
from strategies.errors import UnknownStrategyIdError

T0 = datetime(2026, 7, 21, 14, 0, tzinfo=timezone.utc)


def _fact(i: int, price: str) -> CanonicalFact:
    t = T0 + timedelta(minutes=i)
    return CanonicalFact(
        fact_id=f"fact-{i}", version=1, fact_type="market_price",
        value=(("currency", "USD"), ("price", Decimal(price)), ("symbol", "AAPL")),
        confidence=Confidence(score=1.0),
        provenance=Provenance(
            contributing_observation_ids=(f"o{i}",), contributing_provider_ids=("p1",),
            selected_provider_id="p1", disagreements=(), reconciled_at=t),
        effective_time=t, created_time=t,
    )


def _breakout_setup():
    facts = tuple(_fact(i, str(200 + i)) for i in range(5))
    rh, _ = compute_indicator("rolling_high", facts[:4], T0 + timedelta(minutes=3),
                              T0 + timedelta(minutes=3), params={"period": 3})
    lp, _ = compute_indicator("latest_price", facts, T0 + timedelta(minutes=4),
                              T0 + timedelta(minutes=4))
    return facts, rh, lp


class TestEvaluateStrategyBasics:
    def test_returns_opportunity_when_triggered(self):
        facts, rh, lp = _breakout_setup()
        opp = evaluate_strategy(
            "breakout", {"latest_price": lp, "rolling_high": rh}, facts,
            T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        assert opp is not None

    def test_returns_none_when_not_triggered(self):
        facts = (_fact(0, "200"), _fact(1, "210"), _fact(2, "190"))
        rh, _ = compute_indicator("rolling_high", facts, T0 + timedelta(minutes=2),
                                  T0 + timedelta(minutes=2), params={"period": 3})
        lp, _ = compute_indicator("latest_price", facts, T0 + timedelta(minutes=2),
                                  T0 + timedelta(minutes=2))
        opp = evaluate_strategy(
            "breakout", {"latest_price": lp, "rolling_high": rh}, facts,
            T0 + timedelta(minutes=2), T0 + timedelta(minutes=2))
        assert opp is None

    def test_unknown_strategy_raises(self):
        facts, rh, lp = _breakout_setup()
        with pytest.raises(UnknownStrategyIdError):
            evaluate_strategy("nonexistent", {}, facts, T0, T0)

    def test_opportunity_is_immutable(self):
        facts, rh, lp = _breakout_setup()
        opp = evaluate_strategy(
            "breakout", {"latest_price": lp, "rolling_high": rh}, facts,
            T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        with pytest.raises(Exception):
            opp.version = 2

    def test_opportunity_state_is_discovered(self):
        facts, rh, lp = _breakout_setup()
        opp = evaluate_strategy(
            "breakout", {"latest_price": lp, "rolling_high": rh}, facts,
            T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        assert opp.state == RecommendationState.DISCOVERED
        assert opp.guardrail_outcomes == ()

    def test_strategy_version_pinned(self):
        facts, rh, lp = _breakout_setup()
        opp = evaluate_strategy(
            "breakout", {"latest_price": lp, "rolling_high": rh}, facts,
            T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        assert opp.strategy_id == "breakout"
        assert opp.strategy_version == "v1"


class TestDeterminism:
    def test_identical_indicators_produce_identical_opportunities(self):
        facts, rh, lp = _breakout_setup()
        opp1 = evaluate_strategy(
            "breakout", {"latest_price": lp, "rolling_high": rh}, facts,
            T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        opp2 = evaluate_strategy(
            "breakout", {"latest_price": lp, "rolling_high": rh}, facts,
            T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        assert opp1 == opp2

    def test_replay_byte_identical(self):
        facts, rh, lp = _breakout_setup()
        opp1 = evaluate_strategy(
            "breakout", {"latest_price": lp, "rolling_high": rh}, facts,
            T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        opp2 = evaluate_strategy(
            "breakout", {"latest_price": lp, "rolling_high": rh}, facts,
            T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        assert opp1.opportunity_id == opp2.opportunity_id
        assert opp1.expected_outcome_metrics == opp2.expected_outcome_metrics
        assert opp1.evidence == opp2.evidence
        assert opp1.supporting_indicators == opp2.supporting_indicators

    def test_deterministic_identities(self):
        facts, rh, lp = _breakout_setup()
        opp = evaluate_strategy(
            "breakout", {"latest_price": lp, "rolling_high": rh}, facts,
            T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        assert len(opp.opportunity_id) == 64
        assert opp.opportunity_id == opp.opportunity_id.lower()
        int(opp.opportunity_id, 16)

    def test_deterministic_ordering_of_evidence_and_indicators(self):
        facts, rh, lp = _breakout_setup()
        # Supplying indicator dict keys in different insertion order must
        # not change the resulting evidence/supporting_indicators ordering.
        opp_a = evaluate_strategy(
            "breakout", {"latest_price": lp, "rolling_high": rh}, facts,
            T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        opp_b = evaluate_strategy(
            "breakout", {"rolling_high": rh, "latest_price": lp}, facts,
            T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        assert opp_a.evidence == opp_b.evidence
        assert opp_a.supporting_indicators == opp_b.supporting_indicators
        assert opp_a.opportunity_id == opp_b.opportunity_id


class TestProvenance:
    def test_complete_lineage(self):
        facts, rh, lp = _breakout_setup()
        opp = evaluate_strategy(
            "breakout", {"latest_price": lp, "rolling_high": rh}, facts,
            T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        assert len(opp.evidence) > 0
        assert len(opp.supporting_indicators) == 2
        for ref in opp.supporting_indicators:
            assert ref.kind == EvidenceKind.INDICATOR
        for ref in opp.evidence:
            assert ref.kind == EvidenceKind.CANONICAL_FACT

    def test_indicator_references_complete(self):
        facts, rh, lp = _breakout_setup()
        opp = evaluate_strategy(
            "breakout", {"latest_price": lp, "rolling_high": rh}, facts,
            T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        cited_indicator_ids = {r.referenced_id for r in opp.supporting_indicators}
        assert cited_indicator_ids == {lp.indicator_id, rh.indicator_id}

    def test_assumptions_present(self):
        facts, rh, lp = _breakout_setup()
        opp = evaluate_strategy(
            "breakout", {"latest_price": lp, "rolling_high": rh}, facts,
            T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        assert len(opp.assumptions) > 0

    def test_evidence_confidence_is_minimum_across_facts(self):
        t = T0
        low = CanonicalFact(
            fact_id="low", version=1, fact_type="market_price",
            value=(("currency", "USD"), ("price", Decimal("100")), ("symbol", "AAPL")),
            confidence=Confidence(score=0.3),
            provenance=Provenance(
                contributing_observation_ids=("o1",), contributing_provider_ids=("p1",),
                selected_provider_id="p1", disagreements=(), reconciled_at=t),
            effective_time=t, created_time=t)
        high = CanonicalFact(
            fact_id="high", version=1, fact_type="market_price",
            value=(("currency", "USD"), ("price", Decimal("110")), ("symbol", "AAPL")),
            confidence=Confidence(score=0.9),
            provenance=Provenance(
                contributing_observation_ids=("o2",), contributing_provider_ids=("p1",),
                selected_provider_id="p1", disagreements=(), reconciled_at=t),
            effective_time=t + timedelta(minutes=1), created_time=t + timedelta(minutes=1))
        pct, _ = compute_indicator("price_change_percent", (low, high),
                                   t + timedelta(minutes=1), t + timedelta(minutes=1))
        opp = evaluate_strategy(
            "momentum", {"price_change_percent": pct}, (low, high),
            t + timedelta(minutes=1), t + timedelta(minutes=1),
            params={"threshold": Decimal("0.05")})
        assert opp.evidence_confidence.score == 0.3


class TestOpportunityIdentity:
    def test_same_input_same_id(self):
        a = opportunity_identity("breakout", ("i1",), ("f1",), T0, _dummy_metrics())
        b = opportunity_identity("breakout", ("i1",), ("f1",), T0, _dummy_metrics())
        assert a == b

    def test_different_strategy_different_id(self):
        a = opportunity_identity("breakout", ("i1",), ("f1",), T0, _dummy_metrics())
        b = opportunity_identity("momentum", ("i1",), ("f1",), T0, _dummy_metrics())
        assert a != b

    def test_indicator_id_order_does_not_change_identity(self):
        a = opportunity_identity("breakout", ("i1", "i2"), ("f1",), T0, _dummy_metrics())
        b = opportunity_identity("breakout", ("i2", "i1"), ("f1",), T0, _dummy_metrics())
        assert a == b


def _dummy_metrics():
    from domain.outcome_metrics import ExpectedOutcomeMetrics
    return ExpectedOutcomeMetrics(
        expected_return=Decimal("0.1"), maximum_loss=Decimal("-5"),
        capital_required=Decimal("100"), time_horizon_days=10,
    )
