"""Shared domain module (ADR-004 `domain/`).

Cross-cutting, immutable value types referenced by multiple layers —
defined once here, referenced everywhere (Constitution Law 3). Structural
definitions only; no business logic lives in this package (ASA-CORE-001).

Depends on nothing but itself and the standard library.
"""
from domain.canonical_fact import CanonicalFact
from domain.guardrail import GuardrailOutcome
from domain.indicator import Indicator
from domain.observation import Observation
from domain.opportunity import Opportunity, RecommendationState
from domain.outcome_metrics import ExpectedOutcomeMetrics
from domain.provenance import Provenance, ProviderDisagreement
from domain.provider import Provider
from domain.references import Confidence, EvidenceKind, EvidenceReference

__all__ = [
    "CanonicalFact",
    "Confidence",
    "EvidenceKind",
    "EvidenceReference",
    "ExpectedOutcomeMetrics",
    "GuardrailOutcome",
    "Indicator",
    "Observation",
    "Opportunity",
    "Provenance",
    "Provider",
    "ProviderDisagreement",
    "RecommendationState",
]
