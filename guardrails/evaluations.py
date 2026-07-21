"""Guardrail checks and the aggregate evaluation result (ASA-CORE-006).

Five required, deterministic guardrail checks — pure functions of one
``Opportunity`` and its parameters. No I/O, no repository access, no
randomness, no machine learning, no ranking, no execution. Each returns
``(passed: bool, reason: str)``; ``guardrails/engine.py`` wraps this into
an immutable ``domain.guardrail.GuardrailOutcome`` (ADR-005) — a check
function never constructs one itself (one calculation, one home).

``OpportunityGuardrailEvaluation`` is the aggregate "GuardrailEvaluation"
this ticket's ``outputs`` section refers to: the complete, ordered result
of running every registered guardrail against one Opportunity.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from domain.canonicalization import serialize_canonical
from domain.guardrail import GuardrailOutcome
from domain.opportunity import Opportunity
from domain.references import EvidenceReference
from domain.values import require_tz_aware
from guardrails.errors import EmptyOpportunityEvidenceError, InvalidGuardrailParameterError

GUARDRAIL_EVALUATION_IDENTITY_NAMESPACE = "asa.guardrail_evaluation"
GUARDRAIL_EVALUATION_IDENTITY_VERSION = "v2"
EffectivePolicyParameters = tuple[tuple[str, tuple[tuple[str, str], ...]], ...]


class GuardrailDecision(str, Enum):
    """The aggregate eligibility decision for one immutable Opportunity."""

    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class OpportunityGuardrailEvaluation:
    """The complete, ordered result of running every registered guardrail
    against one Opportunity — this ticket's "GuardrailEvaluation" output.

    The envelope retains the exact immutable ``opportunity`` that was
    evaluated; it never copies Opportunity fields into a parallel model.
    ``overall_decision`` is ``PASS`` only if every individual outcome passed.
    ``ordered_guardrail_outcomes`` is ordered by ``guardrail_id``, never
    insertion or execution order. ``effective_parameters`` preserves the
    canonical policy inputs included in the v2 deterministic identity.
    """

    evaluation_id: str
    opportunity: Opportunity
    ordered_guardrail_outcomes: tuple[GuardrailOutcome, ...]
    overall_decision: GuardrailDecision
    evaluated_at: datetime
    effective_parameters: EffectivePolicyParameters

    def __post_init__(self) -> None:
        require_tz_aware(self.evaluated_at, "OpportunityGuardrailEvaluation", "evaluated_at")


def guardrail_evaluation_identity(
    opportunity_id: str,
    outcomes: tuple[GuardrailOutcome, ...],
    effective_parameters: EffectivePolicyParameters,
) -> str:
    """Deterministic, versioned GuardrailEvaluation identity (algorithm v2).

    Inputs: opportunity_id, sorted (guardrail_id, guardrail_version, passed)
    triples, and effective policy parameters. ``evaluated_at`` is excluded:
    it records execution time, not a semantic policy input. No UUIDs,
    sequence numbers, insertion time, or randomness.
    """
    outcome_triples = tuple(sorted(
        (outcome.guardrail_id, outcome.guardrail_version, outcome.passed)
        for outcome in outcomes
    ))
    payload = "\n".join(
        (
            GUARDRAIL_EVALUATION_IDENTITY_NAMESPACE,
            GUARDRAIL_EVALUATION_IDENTITY_VERSION,
            serialize_canonical(opportunity_id),
            serialize_canonical(outcome_triples),
            serialize_canonical(effective_parameters),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def opportunity_cited_evidence(opportunity: Opportunity) -> tuple[EvidenceReference, ...]:
    """The evidence a GuardrailOutcome cites: the Opportunity's own Fact
    evidence plus its supporting Indicators, deterministically ordered.

    A Guardrail's determination is entirely a function of Opportunity
    fields, which were themselves built from this exact evidence chain
    (ADR-003) — so this *is* "the specific Facts and Indicators that drove
    the pass/fail result" (ADR-005), not a stand-in for it. Raises
    ``EmptyOpportunityEvidenceError`` if the Opportunity has neither —
    Strategies always populate at least one (ADR-003), so this indicates a
    malformed Opportunity, not a legitimate empty case.
    """
    combined = tuple(opportunity.evidence) + tuple(opportunity.supporting_indicators)
    if not combined:
        raise EmptyOpportunityEvidenceError(opportunity.opportunity_id)
    return tuple(sorted(combined, key=lambda ref: (ref.kind.value, ref.referenced_id)))


def guardrail_cited_evidence(
    guardrail_id: str, opportunity: Opportunity
) -> tuple[EvidenceReference, ...]:
    """Return only evidence consumed by a guardrail where attribution is known.

    Current financial-metric and confidence fields do not expose field-level
    provenance, so those guardrails retain the complete Opportunity evidence
    chain. ``placeholder_metrics_rejection`` reads assumptions only and cites
    no unrelated Fact or Indicator evidence.
    """
    if guardrail_id == "placeholder_metrics_rejection":
        return ()
    return opportunity_cited_evidence(opportunity)


def _require_decimal_param(guardrail_id: str, params: dict[str, object], key: str) -> Decimal:
    if key not in params:
        raise InvalidGuardrailParameterError(guardrail_id, f"missing required parameter {key!r}")
    value = params[key]
    if not isinstance(value, Decimal):
        raise InvalidGuardrailParameterError(
            guardrail_id, f"{key!r} must be a Decimal; got {type(value).__name__} {value!r}"
        )
    return value


def _require_int_param(guardrail_id: str, params: dict[str, object], key: str) -> int:
    if key not in params:
        raise InvalidGuardrailParameterError(guardrail_id, f"missing required parameter {key!r}")
    value = params[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidGuardrailParameterError(
            guardrail_id,
            f"{key!r} must be an exact int (bool is not accepted); "
            f"got {type(value).__name__} {value!r}",
        )
    return value


# ---------------------------------------------------------------------------
# Required guardrail checks
# ---------------------------------------------------------------------------

def minimum_evidence_confidence(
    opportunity: Opportunity, params: dict[str, object]
) -> tuple[bool, str]:
    """Reject Opportunities whose evidence_confidence falls below a threshold."""
    threshold = _require_decimal_param("minimum_evidence_confidence", params, "threshold")
    score = Decimal(str(opportunity.evidence_confidence.score))
    passed = score >= threshold
    reason = (
        f"evidence_confidence {score} {'>=' if passed else '<'} threshold {threshold}"
    )
    return passed, reason


def maximum_capital_required(
    opportunity: Opportunity, params: dict[str, object]
) -> tuple[bool, str]:
    """Reject Opportunities whose capital_required exceeds a threshold."""
    threshold = _require_decimal_param("maximum_capital_required", params, "threshold")
    capital = opportunity.expected_outcome_metrics.capital_required
    passed = capital <= threshold
    reason = f"capital_required {capital} {'<=' if passed else '>'} threshold {threshold}"
    return passed, reason


def maximum_loss(opportunity: Opportunity, params: dict[str, object]) -> tuple[bool, str]:
    """Reject Opportunities whose maximum_loss magnitude exceeds a threshold.

    ``expected_outcome_metrics.maximum_loss`` is stored as a non-positive
    Decimal (a loss); ``threshold`` is the maximum tolerable loss
    *magnitude*, a non-negative Decimal.
    """
    threshold = _require_decimal_param("maximum_loss", params, "threshold")
    loss_magnitude = -opportunity.expected_outcome_metrics.maximum_loss
    passed = loss_magnitude <= threshold
    reason = (
        f"maximum_loss magnitude {loss_magnitude} "
        f"{'<=' if passed else '>'} threshold {threshold}"
    )
    return passed, reason


def allowed_time_horizon(
    opportunity: Opportunity, params: dict[str, object]
) -> tuple[bool, str]:
    """Reject Opportunities whose time_horizon_days falls outside [min, max]."""
    minimum = _require_int_param("allowed_time_horizon", params, "minimum_days")
    maximum = _require_int_param("allowed_time_horizon", params, "maximum_days")
    if minimum > maximum:
        raise InvalidGuardrailParameterError(
            "allowed_time_horizon",
            f"minimum_days ({minimum}) must not exceed maximum_days ({maximum})",
        )
    horizon = opportunity.expected_outcome_metrics.time_horizon_days
    passed = minimum <= horizon <= maximum
    reason = f"time_horizon_days {horizon} {'within' if passed else 'outside'} [{minimum}, {maximum}]"
    return passed, reason


PLACEHOLDER_MARKER = "placeholder"


def placeholder_metrics_rejection(
    opportunity: Opportunity, params: dict[str, object]
) -> tuple[bool, str]:
    """Reject Opportunities whose Strategy admits (via ``assumptions``) to
    using uncalibrated placeholder Expected Outcome Metrics.

    Strategies document placeholder formulas explicitly in their
    ``assumptions`` (see ``strategies/calculations.py`` and GitHub Issue
    #46) — this guardrail operationalizes that admission into an enforced
    policy: no Opportunity built on an admitted placeholder model may pass
    until a calibrated model replaces it. Deterministic substring scan,
    case-insensitive, no ML.
    """
    flagged = tuple(
        a for a in opportunity.assumptions if PLACEHOLDER_MARKER in a.lower()
    )
    passed = len(flagged) == 0
    if passed:
        reason = "no placeholder-metric assumptions found"
    else:
        reason = f"{len(flagged)} assumption(s) admit placeholder metrics: {flagged[0]!r}"
    return passed, reason
