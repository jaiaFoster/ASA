"""Guardrail Layer (ADR-005).

Owns platform-wide risk and eligibility rules, shared across all Strategies
(Constitution Law 8). Narrower dependency rule (ADR-004, ASA-CORE-006):
may depend on guardrails, strategies, indicators, facts, reconciliation,
and domain — not observation or providers, even though both sit below
guardrails in the general pipeline order (Constitution Law 4, extended
from Strategies to Guardrails per ADR-005: consumers of established
knowledge do not gather it).
"""
from guardrails.engine import evaluate_guardrail, evaluate_opportunity
from guardrails.errors import (
    DuplicateGuardrailRegistrationError,
    EmptyOpportunityEvidenceError,
    GuardrailError,
    InvalidGuardrailParameterError,
    UnknownGuardrailIdError,
)
from guardrails.evaluations import (
    GUARDRAIL_EVALUATION_IDENTITY_NAMESPACE,
    GUARDRAIL_EVALUATION_IDENTITY_VERSION,
    OpportunityGuardrailEvaluation,
    guardrail_evaluation_identity,
)
from guardrails.registry import DEFAULT_REGISTRY, GuardrailRegistry

__all__ = [
    "DEFAULT_REGISTRY",
    "DuplicateGuardrailRegistrationError",
    "EmptyOpportunityEvidenceError",
    "GUARDRAIL_EVALUATION_IDENTITY_NAMESPACE",
    "GUARDRAIL_EVALUATION_IDENTITY_VERSION",
    "GuardrailError",
    "GuardrailRegistry",
    "InvalidGuardrailParameterError",
    "OpportunityGuardrailEvaluation",
    "UnknownGuardrailIdError",
    "evaluate_guardrail",
    "evaluate_opportunity",
    "guardrail_evaluation_identity",
]
