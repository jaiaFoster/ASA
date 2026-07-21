"""ASA-CORE-006: guardrail check unit tests (policy validation)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from domain.opportunity import Opportunity, RecommendationState
from domain.outcome_metrics import ExpectedOutcomeMetrics
from domain.references import Confidence, EvidenceKind, EvidenceReference
from guardrails.errors import EmptyOpportunityEvidenceError, InvalidGuardrailParameterError
from guardrails.evaluations import (
    allowed_time_horizon,
    maximum_capital_required,
    maximum_loss,
    minimum_evidence_confidence,
    opportunity_cited_evidence,
    placeholder_metrics_rejection,
)
from tests.instrument_helpers import TEST_INSTRUMENT

T0 = datetime(2026, 7, 21, 14, 0, tzinfo=timezone.utc)


def _opp(
    expected_return=Decimal("0.1"), maximum_loss_val=Decimal("-10"),
    capital_required=Decimal("100"), time_horizon_days=10,
    evidence_confidence=0.8, assumptions=(),
    evidence=(EvidenceReference(kind=EvidenceKind.CANONICAL_FACT, referenced_id="f1", version=1),),
    supporting_indicators=(),
) -> Opportunity:
    return Opportunity(
        opportunity_id="opp-1", version=1, strategy_id="s1", strategy_version="v1",
        instrument=TEST_INSTRUMENT,
        supporting_indicators=supporting_indicators, evidence=evidence,
        assumptions=assumptions, evidence_confidence=Confidence(score=evidence_confidence),
        expected_outcome_metrics=ExpectedOutcomeMetrics(
            expected_return=expected_return, maximum_loss=maximum_loss_val,
            capital_required=capital_required, time_horizon_days=time_horizon_days),
        state=RecommendationState.DISCOVERED, effective_time=T0, created_time=T0,
    )


class TestMinimumEvidenceConfidence:
    def test_passes_at_or_above_threshold(self):
        opp = _opp(evidence_confidence=0.8)
        passed, _ = minimum_evidence_confidence(opp, {"threshold": Decimal("0.5")})
        assert passed

    def test_fails_below_threshold(self):
        opp = _opp(evidence_confidence=0.3)
        passed, _ = minimum_evidence_confidence(opp, {"threshold": Decimal("0.5")})
        assert not passed

    def test_exact_threshold_passes(self):
        opp = _opp(evidence_confidence=0.5)
        passed, _ = minimum_evidence_confidence(opp, {"threshold": Decimal("0.5")})
        assert passed

    def test_missing_threshold_raises(self):
        opp = _opp()
        with pytest.raises(InvalidGuardrailParameterError):
            minimum_evidence_confidence(opp, {})

    def test_non_decimal_threshold_raises(self):
        opp = _opp()
        with pytest.raises(InvalidGuardrailParameterError):
            minimum_evidence_confidence(opp, {"threshold": 0.5})


class TestMaximumCapitalRequired:
    def test_passes_at_or_below_threshold(self):
        opp = _opp(capital_required=Decimal("100"))
        passed, _ = maximum_capital_required(opp, {"threshold": Decimal("200")})
        assert passed

    def test_fails_above_threshold(self):
        opp = _opp(capital_required=Decimal("300"))
        passed, _ = maximum_capital_required(opp, {"threshold": Decimal("200")})
        assert not passed

    def test_exact_threshold_passes(self):
        opp = _opp(capital_required=Decimal("200"))
        passed, _ = maximum_capital_required(opp, {"threshold": Decimal("200")})
        assert passed


class TestMaximumLoss:
    def test_passes_within_tolerance(self):
        opp = _opp(maximum_loss_val=Decimal("-5"))
        passed, _ = maximum_loss(opp, {"threshold": Decimal("10")})
        assert passed

    def test_fails_beyond_tolerance(self):
        opp = _opp(maximum_loss_val=Decimal("-15"))
        passed, _ = maximum_loss(opp, {"threshold": Decimal("10")})
        assert not passed

    def test_exact_threshold_passes(self):
        opp = _opp(maximum_loss_val=Decimal("-10"))
        passed, _ = maximum_loss(opp, {"threshold": Decimal("10")})
        assert passed

    def test_zero_loss_always_passes(self):
        opp = _opp(maximum_loss_val=Decimal("0"))
        passed, _ = maximum_loss(opp, {"threshold": Decimal("0")})
        assert passed


class TestAllowedTimeHorizon:
    def test_passes_within_range(self):
        opp = _opp(time_horizon_days=15)
        passed, _ = allowed_time_horizon(opp, {"minimum_days": 1, "maximum_days": 30})
        assert passed

    def test_fails_below_range(self):
        opp = _opp(time_horizon_days=1)
        passed, _ = allowed_time_horizon(opp, {"minimum_days": 5, "maximum_days": 30})
        assert not passed

    def test_fails_above_range(self):
        opp = _opp(time_horizon_days=45)
        passed, _ = allowed_time_horizon(opp, {"minimum_days": 1, "maximum_days": 30})
        assert not passed

    def test_boundary_values_pass(self):
        opp_min = _opp(time_horizon_days=1)
        opp_max = _opp(time_horizon_days=30)
        assert allowed_time_horizon(opp_min, {"minimum_days": 1, "maximum_days": 30})[0]
        assert allowed_time_horizon(opp_max, {"minimum_days": 1, "maximum_days": 30})[0]

    def test_inverted_range_raises(self):
        opp = _opp(time_horizon_days=10)
        with pytest.raises(InvalidGuardrailParameterError):
            allowed_time_horizon(opp, {"minimum_days": 30, "maximum_days": 1})

    def test_bool_days_rejected(self):
        opp = _opp(time_horizon_days=10)
        with pytest.raises(InvalidGuardrailParameterError):
            allowed_time_horizon(opp, {"minimum_days": True, "maximum_days": 30})


class TestPlaceholderMetricsRejection:
    def test_fails_when_placeholder_assumption_present(self):
        opp = _opp(assumptions=(
            "maximum_loss uses a fixed 0.05 stop-loss placeholder, not a calibrated risk model",
        ))
        passed, reason = placeholder_metrics_rejection(opp, {})
        assert not passed
        assert "placeholder" in reason.lower()

    def test_passes_with_no_placeholder_assumptions(self):
        opp = _opp(assumptions=("this is a calibrated, real assumption",))
        passed, _ = placeholder_metrics_rejection(opp, {})
        assert passed

    def test_passes_with_no_assumptions_at_all(self):
        opp = _opp(assumptions=())
        passed, _ = placeholder_metrics_rejection(opp, {})
        assert passed

    def test_case_insensitive_detection(self):
        opp = _opp(assumptions=("Uses a PLACEHOLDER value",))
        passed, _ = placeholder_metrics_rejection(opp, {})
        assert not passed


class TestOpportunityCitedEvidence:
    def test_combines_evidence_and_supporting_indicators(self):
        ev = (EvidenceReference(kind=EvidenceKind.CANONICAL_FACT, referenced_id="f1", version=1),)
        ind = (EvidenceReference(kind=EvidenceKind.INDICATOR, referenced_id="i1", version=1),)
        opp = _opp(evidence=ev, supporting_indicators=ind)
        cited = opportunity_cited_evidence(opp)
        assert len(cited) == 2

    def test_deterministic_ordering(self):
        ev = (EvidenceReference(kind=EvidenceKind.CANONICAL_FACT, referenced_id="f2", version=1),
              EvidenceReference(kind=EvidenceKind.CANONICAL_FACT, referenced_id="f1", version=1))
        opp = _opp(evidence=ev)
        cited = opportunity_cited_evidence(opp)
        assert [r.referenced_id for r in cited] == ["f1", "f2"]

    def test_empty_raises(self):
        opp = _opp(evidence=(), supporting_indicators=())
        with pytest.raises(EmptyOpportunityEvidenceError):
            opportunity_cited_evidence(opp)
