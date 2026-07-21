"""ASA-CORE-006: guardrail engine tests — determinism, replay, identity, ordering."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from domain.opportunity import Opportunity, RecommendationState
from domain.outcome_metrics import ExpectedOutcomeMetrics
from domain.references import Confidence, EvidenceKind, EvidenceReference
from guardrails.engine import evaluate_guardrail, evaluate_opportunity
from guardrails.errors import UnknownGuardrailIdError
from guardrails.evaluations import guardrail_evaluation_identity

T0 = datetime(2026, 7, 21, 14, 0, tzinfo=timezone.utc)


def _opp(assumptions=("a normal, calibrated assumption",)) -> Opportunity:
    return Opportunity(
        opportunity_id="opp-1", version=1, strategy_id="s1", strategy_version="v1",
        supporting_indicators=(EvidenceReference(
            kind=EvidenceKind.INDICATOR, referenced_id="i1", version=1),),
        evidence=(EvidenceReference(
            kind=EvidenceKind.CANONICAL_FACT, referenced_id="f1", version=1),),
        assumptions=assumptions, evidence_confidence=Confidence(score=0.8),
        expected_outcome_metrics=ExpectedOutcomeMetrics(
            expected_return=Decimal("0.1"), maximum_loss=Decimal("-10"),
            capital_required=Decimal("100"), time_horizon_days=10),
        state=RecommendationState.DISCOVERED, effective_time=T0, created_time=T0,
    )


PARAMS = {
    "minimum_evidence_confidence": {"threshold": Decimal("0.5")},
    "maximum_capital_required": {"threshold": Decimal("200")},
    "maximum_loss": {"threshold": Decimal("20")},
    "allowed_time_horizon": {"minimum_days": 1, "maximum_days": 30},
}


class TestEvaluateGuardrailBasics:
    def test_returns_outcome(self):
        opp = _opp()
        outcome = evaluate_guardrail(
            "minimum_evidence_confidence", opp, {"threshold": Decimal("0.5")})
        assert outcome.guardrail_id == "minimum_evidence_confidence"
        assert outcome.passed

    def test_unknown_guardrail_raises(self):
        opp = _opp()
        with pytest.raises(UnknownGuardrailIdError):
            evaluate_guardrail("nonexistent", opp, {})

    def test_outcome_is_immutable(self):
        opp = _opp()
        outcome = evaluate_guardrail(
            "minimum_evidence_confidence", opp, {"threshold": Decimal("0.5")})
        with pytest.raises(Exception):
            outcome.passed = False

    def test_default_evaluated_at_is_opportunity_effective_time(self):
        opp = _opp()
        outcome = evaluate_guardrail(
            "minimum_evidence_confidence", opp, {"threshold": Decimal("0.5")})
        assert outcome.evaluated_at == opp.effective_time

    def test_guardrail_version_pinned(self):
        opp = _opp()
        outcome = evaluate_guardrail(
            "minimum_evidence_confidence", opp, {"threshold": Decimal("0.5")})
        assert outcome.guardrail_version == "v1"


class TestEvaluateOpportunity:
    def test_all_five_guardrails_run(self):
        opp = _opp()
        evaluation = evaluate_opportunity(opp, PARAMS)
        assert len(evaluation.outcomes) == 5

    def test_overall_passed_requires_unanimous(self):
        opp = _opp()  # non-placeholder assumptions, passes all thresholds
        evaluation = evaluate_opportunity(opp, PARAMS)
        assert evaluation.passed

    def test_single_failure_blocks_overall(self):
        opp = _opp(assumptions=("uses a fixed placeholder value",))
        evaluation = evaluate_opportunity(opp, PARAMS)
        assert not evaluation.passed
        failing = [o for o in evaluation.outcomes if not o.passed]
        assert any(o.guardrail_id == "placeholder_metrics_rejection" for o in failing)

    def test_deterministic_ordering_by_guardrail_id(self):
        opp = _opp()
        evaluation = evaluate_opportunity(opp, PARAMS)
        ids = [o.guardrail_id for o in evaluation.outcomes]
        assert ids == sorted(ids)


class TestDeterminism:
    def test_identical_opportunity_produces_identical_evaluation(self):
        opp = _opp()
        eval1 = evaluate_opportunity(opp, PARAMS)
        eval2 = evaluate_opportunity(opp, PARAMS)
        assert eval1 == eval2

    def test_replay_byte_identical(self):
        opp = _opp()
        eval1 = evaluate_opportunity(opp, PARAMS)
        eval2 = evaluate_opportunity(opp, PARAMS)
        assert eval1.evaluation_id == eval2.evaluation_id
        assert eval1.outcomes == eval2.outcomes

    def test_deterministic_identity(self):
        opp = _opp()
        evaluation = evaluate_opportunity(opp, PARAMS)
        assert len(evaluation.evaluation_id) == 64
        assert evaluation.evaluation_id == evaluation.evaluation_id.lower()
        int(evaluation.evaluation_id, 16)

    def test_param_dict_key_order_does_not_affect_result(self):
        opp = _opp()
        params_a = dict(PARAMS)
        params_b = {k: PARAMS[k] for k in reversed(list(PARAMS))}
        eval_a = evaluate_opportunity(opp, params_a)
        eval_b = evaluate_opportunity(opp, params_b)
        assert eval_a.evaluation_id == eval_b.evaluation_id


class TestGuardrailEvaluationIdentity:
    def test_same_input_same_id(self):
        opp = _opp()
        eval1 = evaluate_opportunity(opp, PARAMS)
        a = guardrail_evaluation_identity(opp.opportunity_id, eval1.outcomes, T0)
        b = guardrail_evaluation_identity(opp.opportunity_id, eval1.outcomes, T0)
        assert a == b

    def test_outcome_order_does_not_change_identity(self):
        opp = _opp()
        evaluation = evaluate_opportunity(opp, PARAMS)
        forward = guardrail_evaluation_identity(opp.opportunity_id, evaluation.outcomes, T0)
        backward = guardrail_evaluation_identity(
            opp.opportunity_id, tuple(reversed(evaluation.outcomes)), T0)
        assert forward == backward

    def test_different_opportunity_different_id(self):
        opp = _opp()
        evaluation = evaluate_opportunity(opp, PARAMS)
        a = guardrail_evaluation_identity("opp-1", evaluation.outcomes, T0)
        b = guardrail_evaluation_identity("opp-2", evaluation.outcomes, T0)
        assert a != b
