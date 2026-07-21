"""Opportunity — explainable, evidence-carrying record (ADR-003 as amended).

Structural definitions only — no business logic (ASA-CORE-001).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from domain.guardrail import GuardrailOutcome
from domain.operational import Instrument
from domain.outcome_metrics import ExpectedOutcomeMetrics
from domain.references import Confidence, EvidenceReference
from domain.values import require_positive, require_tz_aware


class RecommendationState(str, Enum):
    """Explicit lifecycle state of an Opportunity (ADR-003)."""

    DISCOVERED = "discovered"
    GUARDRAIL_EVALUATED = "guardrail_evaluated"
    RANKED = "ranked"
    PRESENTED = "presented"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class Opportunity:
    """One immutable version of an Opportunity record (ADR-003 as amended).

    Carries the full minimum structural content: canonical Instrument,
    pinned Strategy version,
    supporting Indicator versions, Evidence, Assumptions, evidence
    confidence, Expected Outcome Metrics, Guardrail outcomes, and an
    explicit lifecycle state. The Decision Journal entry for a presented
    Recommendation is this record frozen at presentation time — no separate
    structure exists (ADR-003). State progression yields a new version;
    ``opportunity_id`` is stable across the lifecycle.
    """

    opportunity_id: str
    version: int
    strategy_id: str
    strategy_version: str
    instrument: Instrument
    supporting_indicators: tuple[EvidenceReference, ...]
    evidence: tuple[EvidenceReference, ...]
    assumptions: tuple[str, ...]
    evidence_confidence: Confidence
    expected_outcome_metrics: ExpectedOutcomeMetrics
    state: RecommendationState
    effective_time: datetime
    created_time: datetime
    guardrail_outcomes: tuple[GuardrailOutcome, ...] = field(default=())

    def __post_init__(self) -> None:
        require_positive(self.version, "Opportunity", "version")
        require_tz_aware(self.effective_time, "Opportunity", "effective_time")
        require_tz_aware(self.created_time, "Opportunity", "created_time")
