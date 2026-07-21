"""Guardrail outcome — deterministic, versioned, evidence-citing (ADR-005).

Structural definitions only — no business logic (ASA-CORE-001).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.references import EvidenceReference


@dataclass(frozen=True, slots=True)
class GuardrailOutcome:
    """The result of one versioned Guardrail against one Opportunity.

    Retained even for rejected Opportunities (ADR-003). ``reason`` is not
    free text alone: ``evidence`` cites the specific Fact and Indicator
    versions that drove the pass/fail result (ADR-005). Guardrail outcomes
    carry no independent Confidence value (ADR-005).
    """

    guardrail_id: str
    guardrail_version: str
    passed: bool
    reason: str
    evidence: tuple[EvidenceReference, ...]
    evaluated_at: datetime
