"""Pure deterministic Ranking Engine (ASA-CORE-007)."""

from __future__ import annotations

import hashlib
from decimal import Decimal, localcontext

from domain.canonicalization import serialize_canonical
from guardrails.evaluations import GuardrailDecision, OpportunityGuardrailEvaluation
from ranking.errors import DuplicateOpportunityEvaluationError, InvalidScorerOutputError
from ranking.models import (
    RANKING_ALGORITHM_VERSION,
    RANKING_IDENTITY_NAMESPACE,
    RANKING_RESULT_IDENTITY_NAMESPACE,
    SCORE_QUANTUM,
    RankedOpportunity,
    RankingParameters,
    RankingResult,
    ScoreComponent,
)
from ranking.registry import DEFAULT_REGISTRY, ScorerRegistry


def _component_identity(component: ScoreComponent) -> tuple[object, ...]:
    return (
        component.dimension,
        component.scorer_version,
        component.raw_value,
        component.score,
        component.effective_parameters,
        component.assumptions,
    )


def ranking_identity(
    opportunity_id: str,
    scoring_components: tuple[ScoreComponent, ...],
    effective_parameters: tuple[tuple[str, Decimal], ...],
) -> str:
    payload = "\n".join(
        (
            RANKING_IDENTITY_NAMESPACE,
            RANKING_ALGORITHM_VERSION,
            serialize_canonical(opportunity_id),
            serialize_canonical(tuple(_component_identity(item) for item in scoring_components)),
            serialize_canonical(effective_parameters),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _result_identity(
    ranked: tuple[RankedOpportunity, ...],
    effective_parameters: tuple[tuple[str, Decimal], ...],
) -> str:
    payload = "\n".join(
        (
            RANKING_RESULT_IDENTITY_NAMESPACE,
            RANKING_ALGORITHM_VERSION,
            serialize_canonical(tuple(item.ranking_id for item in ranked)),
            serialize_canonical(effective_parameters),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _score_evaluation(
    evaluation: OpportunityGuardrailEvaluation,
    parameters: RankingParameters,
    registry: ScorerRegistry,
) -> tuple[tuple[ScoreComponent, ...], Decimal]:
    components_list: list[ScoreComponent] = []
    for dimension in registry.registered_dimensions():
        definition = registry.get(dimension)
        component = definition.scorer(evaluation.opportunity, parameters)
        if (
            component.dimension != definition.dimension
            or component.scorer_version != definition.scorer_version
        ):
            raise InvalidScorerOutputError(
                f"scorer output does not match registered dimension/version: {dimension!r}"
            )
        components_list.append(component)
    components = tuple(components_list)
    scores = {component.dimension: component.score for component in components}
    with localcontext() as context:
        context.prec = 40
        weighted_sum = sum(
            (scores[dimension] * weight for dimension, weight in parameters.weights()),
            Decimal("0"),
        )
        weight_sum = sum((weight for _, weight in parameters.weights()), Decimal("0"))
        total = (weighted_sum / weight_sum).quantize(SCORE_QUANTUM)
    return components, total


def rank_opportunities(
    evaluations: tuple[OpportunityGuardrailEvaluation, ...],
    parameters: RankingParameters | None = None,
    registry: ScorerRegistry = DEFAULT_REGISTRY,
) -> RankingResult:
    """Filter to PASS evaluations, score, and order independently of input order."""
    parameters = parameters or RankingParameters()
    registry.validate_required_dimensions()
    seen: set[str] = set()
    eligible: list[OpportunityGuardrailEvaluation] = []
    for evaluation in evaluations:
        opportunity_id = evaluation.opportunity.opportunity_id
        if opportunity_id in seen:
            raise DuplicateOpportunityEvaluationError(opportunity_id)
        seen.add(opportunity_id)
        if evaluation.overall_decision is GuardrailDecision.PASS:
            eligible.append(evaluation)

    effective_parameters = parameters.canonical_items()
    scored: list[tuple[OpportunityGuardrailEvaluation, tuple[ScoreComponent, ...], Decimal]] = []
    for evaluation in eligible:
        components, total = _score_evaluation(evaluation, parameters, registry)
        scored.append((evaluation, components, total))
    scored.sort(
        key=lambda item: (
            -item[2],
            -Decimal(str(item[0].opportunity.evidence_confidence.score)),
            -item[0].opportunity.expected_outcome_metrics.expected_return,
            item[0].opportunity.opportunity_id,
        )
    )
    ranked = tuple(
        RankedOpportunity(
            ranking_id=ranking_identity(
                evaluation.opportunity.opportunity_id, components, effective_parameters
            ),
            rank=index,
            ranking_algorithm_version=RANKING_ALGORITHM_VERSION,
            evaluation=evaluation,
            scoring_components=components,
            total_score=total,
            effective_parameters=effective_parameters,
        )
        for index, (evaluation, components, total) in enumerate(scored, start=1)
    )
    return RankingResult(
        result_id=_result_identity(ranked, effective_parameters),
        ranking_algorithm_version=RANKING_ALGORITHM_VERSION,
        ranked_opportunities=ranked,
        effective_parameters=effective_parameters,
    )
