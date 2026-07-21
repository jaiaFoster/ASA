"""ASA-CORE-007 Phase 0 regression coverage for guardrail hardening."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from domain.opportunity import Opportunity, RecommendationState
from domain.outcome_metrics import ExpectedOutcomeMetrics
from domain.references import Confidence, EvidenceKind, EvidenceReference
from guardrails.engine import evaluate_guardrail, evaluate_opportunity
from guardrails.evaluations import GUARDRAIL_EVALUATION_IDENTITY_VERSION, GuardrailDecision
from guardrails.registry import DEFAULT_REGISTRY
from tests.instrument_helpers import TEST_INSTRUMENT

T0 = datetime(2026, 7, 21, 14, 0, tzinfo=timezone.utc)


def _opportunity() -> Opportunity:
    return Opportunity(
        opportunity_id="phase0-opportunity",
        version=1,
        strategy_id="strategy",
        strategy_version="v1",
        instrument=TEST_INSTRUMENT,
        supporting_indicators=(
            EvidenceReference(kind=EvidenceKind.INDICATOR, referenced_id="indicator", version=1),
        ),
        evidence=(
            EvidenceReference(
                kind=EvidenceKind.CANONICAL_FACT, referenced_id="fact", version=1
            ),
        ),
        assumptions=("calibrated model",),
        evidence_confidence=Confidence(score=0.8),
        expected_outcome_metrics=ExpectedOutcomeMetrics(
            expected_return=Decimal("0.1"),
            maximum_loss=Decimal("-10"),
            capital_required=Decimal("100"),
            time_horizon_days=10,
        ),
        state=RecommendationState.DISCOVERED,
        effective_time=T0,
        created_time=T0,
    )


def _parameters(loss_threshold: str = "20") -> dict[str, dict]:
    return {
        "minimum_evidence_confidence": {"threshold": Decimal("0.5")},
        "maximum_capital_required": {"threshold": Decimal("200")},
        "maximum_loss": {"threshold": Decimal(loss_threshold)},
        "allowed_time_horizon": {"minimum_days": 1, "maximum_days": 30},
    }


def test_effective_policy_change_changes_identity_even_when_outcomes_match() -> None:
    opportunity = _opportunity()
    conservative = evaluate_opportunity(opportunity, _parameters("20"))
    permissive = evaluate_opportunity(opportunity, _parameters("50"))

    assert conservative.overall_decision is GuardrailDecision.PASS
    assert permissive.overall_decision is GuardrailDecision.PASS
    assert tuple(outcome.passed for outcome in conservative.ordered_guardrail_outcomes) == tuple(
        outcome.passed for outcome in permissive.ordered_guardrail_outcomes
    )
    assert conservative.evaluation_id != permissive.evaluation_id
    assert conservative.effective_parameters != permissive.effective_parameters


def test_hardened_identity_algorithm_version_is_pinned() -> None:
    assert GUARDRAIL_EVALUATION_IDENTITY_VERSION == "v2"
    assert evaluate_opportunity(_opportunity(), _parameters()).evaluation_id == (
        "7537bc401a3068e01f99cdcb4d7ccc5baad51ec65de517cbdeecde874de7d2f0"
    )


def test_registry_declares_every_effective_policy_parameter() -> None:
    assert {
        guardrail_id: DEFAULT_REGISTRY.get(guardrail_id).parameter_names
        for guardrail_id in DEFAULT_REGISTRY.registered_ids()
    } == {
        "allowed_time_horizon": ("maximum_days", "minimum_days"),
        "maximum_capital_required": ("threshold",),
        "maximum_loss": ("threshold",),
        "minimum_evidence_confidence": ("threshold",),
        "placeholder_metrics_rejection": (),
    }


def test_execution_timestamp_is_excluded_from_identity() -> None:
    opportunity = _opportunity()
    first = evaluate_opportunity(opportunity, _parameters(), evaluated_at=T0)
    replay = evaluate_opportunity(
        opportunity, _parameters(), evaluated_at=T0 + timedelta(hours=2)
    )

    assert first.evaluated_at != replay.evaluated_at
    assert first.evaluation_id == replay.evaluation_id


def test_policy_mapping_order_does_not_change_identity() -> None:
    opportunity = _opportunity()
    forward = _parameters()
    reversed_mapping = {key: forward[key] for key in reversed(tuple(forward))}

    assert evaluate_opportunity(opportunity, forward).evaluation_id == evaluate_opportunity(
        opportunity, reversed_mapping
    ).evaluation_id


def test_irrelevant_unconsumed_parameter_does_not_change_identity() -> None:
    opportunity = _opportunity()
    baseline = _parameters()
    extra = _parameters()
    extra["maximum_loss"] = {**extra["maximum_loss"], "unused": Decimal("999")}

    assert evaluate_opportunity(opportunity, baseline).evaluation_id == evaluate_opportunity(
        opportunity, extra
    ).evaluation_id


def test_placeholder_guardrail_cites_no_unconsumed_evidence() -> None:
    outcome = evaluate_guardrail("placeholder_metrics_rejection", _opportunity())
    assert outcome.evidence == ()


def test_metric_guardrail_retains_available_opportunity_evidence() -> None:
    opportunity = _opportunity()
    outcome = evaluate_guardrail(
        "maximum_loss", opportunity, {"threshold": Decimal("20")}
    )
    assert outcome.evidence == tuple(
        sorted(
            opportunity.evidence + opportunity.supporting_indicators,
            key=lambda reference: (reference.kind.value, reference.referenced_id),
        )
    )
