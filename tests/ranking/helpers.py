from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from domain.opportunity import Opportunity, RecommendationState
from domain.outcome_metrics import ExpectedOutcomeMetrics
from domain.references import Confidence, EvidenceKind, EvidenceReference
from guardrails.engine import evaluate_opportunity
from guardrails.evaluations import OpportunityGuardrailEvaluation

T0 = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
GUARDRAIL_PARAMETERS: dict[str, dict[str, object]] = {
    "minimum_evidence_confidence": {"threshold": Decimal("0")},
    "maximum_capital_required": {"threshold": Decimal("1000000")},
    "maximum_loss": {"threshold": Decimal("1000000")},
    "allowed_time_horizon": {"minimum_days": 1, "maximum_days": 3650},
}


def evaluation(
    opportunity_id: str,
    *,
    expected_return: str = "0.10",
    maximum_loss: str = "-10",
    capital_required: str = "100",
    horizon_days: int = 10,
    confidence: float = 0.8,
    probability: str | None = "0.7",
    eligible: bool = True,
    evaluated_at: datetime = T0,
) -> OpportunityGuardrailEvaluation:
    opportunity = Opportunity(
        opportunity_id=opportunity_id,
        version=1,
        strategy_id="test_strategy",
        strategy_version="v1",
        supporting_indicators=(
            EvidenceReference(
                kind=EvidenceKind.INDICATOR,
                referenced_id=f"indicator-{opportunity_id}",
                version=1,
            ),
        ),
        evidence=(
            EvidenceReference(
                kind=EvidenceKind.CANONICAL_FACT,
                referenced_id=f"fact-{opportunity_id}",
                version=1,
            ),
        ),
        assumptions=("calibrated model" if eligible else "placeholder model",),
        evidence_confidence=Confidence(score=confidence),
        expected_outcome_metrics=ExpectedOutcomeMetrics(
            expected_return=Decimal(expected_return),
            maximum_loss=Decimal(maximum_loss),
            capital_required=Decimal(capital_required),
            time_horizon_days=horizon_days,
            probability_of_profit=Decimal(probability) if probability is not None else None,
        ),
        state=RecommendationState.DISCOVERED,
        effective_time=T0,
        created_time=T0,
    )
    return evaluate_opportunity(
        opportunity,
        GUARDRAIL_PARAMETERS,
        evaluated_at=evaluated_at,
    )
