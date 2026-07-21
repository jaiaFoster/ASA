"""Deterministic Guardrail engine (ASA-CORE-006).

Evaluates immutable Opportunities against platform policies via the
guardrail registry (``guardrails/registry.py``) to produce immutable
``GuardrailOutcome`` records (ADR-005) and the aggregate
``OpportunityGuardrailEvaluation`` (``guardrails/evaluations.py``). Pure
orchestration — no repository access, no randomness, no ranking, no
execution, no broker/provider access, no persistence. A total,
deterministic function of its arguments, making guardrail evaluation
fully replayable.
"""
from __future__ import annotations

from datetime import datetime

from domain.canonicalization import serialize_canonical
from domain.guardrail import GuardrailOutcome
from domain.opportunity import Opportunity
from domain.values import require_tz_aware
from guardrails.evaluations import (
    EffectivePolicyParameters,
    OpportunityGuardrailEvaluation,
    guardrail_cited_evidence,
    guardrail_evaluation_identity,
)
from guardrails.registry import DEFAULT_REGISTRY, GuardrailRegistry


def evaluate_guardrail(
    guardrail_id: str,
    opportunity: Opportunity,
    params: dict[str, object] | None = None,
    evaluated_at: datetime | None = None,
    registry: GuardrailRegistry = DEFAULT_REGISTRY,
) -> GuardrailOutcome:
    """Evaluate one guardrail against one Opportunity.

    ``evaluated_at`` defaults to ``opportunity.effective_time`` if not
    supplied (evaluating "as of" the Opportunity's own effective time is
    the natural default; callers evaluating at a later wall-clock time
    should pass it explicitly).
    """
    params = params or {}
    if evaluated_at is None:
        evaluated_at = opportunity.effective_time
    require_tz_aware(evaluated_at, "evaluate_guardrail", "evaluated_at")

    definition = registry.get(guardrail_id)
    passed, reason = definition.check(opportunity, params)
    evidence = guardrail_cited_evidence(guardrail_id, opportunity)

    return GuardrailOutcome(
        guardrail_id=guardrail_id,
        guardrail_version=definition.guardrail_version,
        passed=passed,
        reason=reason,
        evidence=evidence,
        evaluated_at=evaluated_at,
    )


def evaluate_opportunity(
    opportunity: Opportunity,
    params_by_guardrail: dict[str, dict[str, object]] | None = None,
    evaluated_at: datetime | None = None,
    registry: GuardrailRegistry = DEFAULT_REGISTRY,
) -> OpportunityGuardrailEvaluation:
    """Run every registered guardrail against one Opportunity.

    ``params_by_guardrail`` maps ``guardrail_id -> params`` for guardrails
    that require parameters (all but ``placeholder_metrics_rejection``, in
    the default registry); a guardrail with no entry is evaluated with
    empty params, which will raise ``InvalidGuardrailParameterError`` if
    it requires one. Outcomes are ordered deterministically by
    ``guardrail_id`` — never registration or evaluation order.
    """
    params_by_guardrail = params_by_guardrail or {}
    if evaluated_at is None:
        evaluated_at = opportunity.effective_time
    require_tz_aware(evaluated_at, "evaluate_opportunity", "evaluated_at")

    outcomes = tuple(
        evaluate_guardrail(
            guardrail_id, opportunity,
            params=params_by_guardrail.get(guardrail_id),
            evaluated_at=evaluated_at, registry=registry,
        )
        for guardrail_id in registry.registered_ids()
    )
    overall_passed = all(outcome.passed for outcome in outcomes)
    effective_parameters: EffectivePolicyParameters = tuple(
        (
            guardrail_id,
            tuple(
                (name, serialize_canonical(params_by_guardrail.get(guardrail_id, {})[name]))
                for name in registry.get(guardrail_id).parameter_names
            ),
        )
        for guardrail_id in registry.registered_ids()
    )

    return OpportunityGuardrailEvaluation(
        evaluation_id=guardrail_evaluation_identity(
            opportunity.opportunity_id, outcomes, effective_parameters
        ),
        opportunity_id=opportunity.opportunity_id,
        outcomes=outcomes,
        passed=overall_passed,
        evaluated_at=evaluated_at,
        effective_parameters=effective_parameters,
    )
