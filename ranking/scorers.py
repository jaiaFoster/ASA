"""Versioned deterministic component scorers for Ranking v1."""

from __future__ import annotations

from decimal import Decimal, localcontext

from domain.opportunity import Opportunity
from ranking.models import RankingParameters, SCORE_QUANTUM, ScoreComponent

SCORER_VERSION = "v1"
NEUTRAL_LIQUIDITY_ASSUMPTION = (
    "v1 placeholder: Opportunity has no liquidity metric; use configured neutral score",
)
NEUTRAL_QUALITY_ASSUMPTION = (
    "v1 placeholder: probability_of_profit is unavailable; use configured neutral score",
)


def _bounded(value: Decimal) -> Decimal:
    return min(Decimal("1"), max(Decimal("0"), value))


def _quantized(value: Decimal) -> Decimal:
    return value.quantize(SCORE_QUANTUM)


def _linear(value: Decimal, floor: Decimal, ceiling: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 40
        return _quantized(_bounded((value - floor) / (ceiling - floor)))


def score_expected_return(
    opportunity: Opportunity, parameters: RankingParameters
) -> ScoreComponent:
    raw = opportunity.expected_outcome_metrics.expected_return
    return ScoreComponent(
        dimension="expected_return",
        scorer_version=SCORER_VERSION,
        raw_value=raw,
        score=_linear(raw, parameters.expected_return_floor, parameters.expected_return_ceiling),
        effective_parameters=(
            ("ceiling", parameters.expected_return_ceiling),
            ("floor", parameters.expected_return_floor),
        ),
    )


def score_downside_risk(opportunity: Opportunity, parameters: RankingParameters) -> ScoreComponent:
    metrics = opportunity.expected_outcome_metrics
    loss = -metrics.maximum_loss
    with localcontext() as context:
        context.prec = 40
        if metrics.capital_required == 0:
            ratio = Decimal("0") if loss == 0 else parameters.maximum_loss_ratio_ceiling
        else:
            ratio = loss / metrics.capital_required
        score = _quantized(Decimal("1") - _bounded(ratio / parameters.maximum_loss_ratio_ceiling))
    return ScoreComponent(
        dimension="downside_risk",
        scorer_version=SCORER_VERSION,
        raw_value=ratio,
        score=score,
        effective_parameters=(
            ("maximum_loss_ratio_ceiling", parameters.maximum_loss_ratio_ceiling),
        ),
    )


def score_evidence_confidence(
    opportunity: Opportunity, parameters: RankingParameters
) -> ScoreComponent:
    del parameters
    raw = Decimal(str(opportunity.evidence_confidence.score))
    return ScoreComponent(
        dimension="evidence_confidence",
        scorer_version=SCORER_VERSION,
        raw_value=raw,
        score=_quantized(raw),
        effective_parameters=(),
    )


def score_capital_efficiency(
    opportunity: Opportunity, parameters: RankingParameters
) -> ScoreComponent:
    metrics = opportunity.expected_outcome_metrics
    with localcontext() as context:
        context.prec = 40
        daily_return = metrics.expected_return / Decimal(metrics.time_horizon_days)
    return ScoreComponent(
        dimension="capital_efficiency",
        scorer_version=SCORER_VERSION,
        raw_value=daily_return,
        score=_linear(daily_return, parameters.daily_return_floor, parameters.daily_return_ceiling),
        effective_parameters=(
            ("daily_return_ceiling", parameters.daily_return_ceiling),
            ("daily_return_floor", parameters.daily_return_floor),
        ),
        assumptions=("v1 heuristic: capital efficiency is expected return per horizon day",),
    )


def score_liquidity(opportunity: Opportunity, parameters: RankingParameters) -> ScoreComponent:
    del opportunity
    raw = parameters.liquidity_placeholder_score
    return ScoreComponent(
        dimension="liquidity",
        scorer_version=SCORER_VERSION,
        raw_value=raw,
        score=_quantized(raw),
        effective_parameters=(("placeholder_score", raw),),
        assumptions=NEUTRAL_LIQUIDITY_ASSUMPTION,
    )


def score_opportunity_quality(
    opportunity: Opportunity, parameters: RankingParameters
) -> ScoreComponent:
    probability = opportunity.expected_outcome_metrics.probability_of_profit
    assumptions: tuple[str, ...]
    effective: tuple[tuple[str, Decimal], ...]
    if probability is None:
        raw = parameters.quality_placeholder_score
        assumptions = NEUTRAL_QUALITY_ASSUMPTION
        effective = (("placeholder_score", raw),)
    else:
        raw = probability
        assumptions = ()
        effective = ()
    return ScoreComponent(
        dimension="opportunity_quality",
        scorer_version=SCORER_VERSION,
        raw_value=raw,
        score=_quantized(raw),
        effective_parameters=effective,
        assumptions=assumptions,
    )
