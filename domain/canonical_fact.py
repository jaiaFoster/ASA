"""Canonical Fact — versioned, immutable best understanding (ADR-001).

Structural definitions only — no business logic (ASA-CORE-001).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.market_data import MarketCapability
from domain.provenance import Provenance
from domain.references import Confidence
from domain.values import require_normalized, require_positive, require_tz_aware


@dataclass(frozen=True, slots=True)
class CanonicalFact:
    """One immutable version of ASA's resolved record for a data point.

    Each reconciliation that changes the resolved value produces a new
    version; prior versions are retained permanently and never recomputed
    (ADR-001). ``confidence`` is an internal reconciliation attribute;
    ``provenance`` is externally visible and mandatory (ADR-001 as amended
    by ASA-CORE-001).
    """

    fact_id: str
    version: int
    fact_type: str
    value: object
    confidence: Confidence
    provenance: Provenance
    effective_time: datetime
    created_time: datetime

    def __post_init__(self) -> None:
        require_positive(self.version, "CanonicalFact", "version")
        require_normalized(self.value, "CanonicalFact", "value")
        require_tz_aware(self.effective_time, "CanonicalFact", "effective_time")
        require_tz_aware(self.created_time, "CanonicalFact", "created_time")


@dataclass(frozen=True, slots=True)
class CanonicalFactRequest:
    """One scalar a strategy-owned structural selection/binding wants
    projected into a CanonicalFact (SPRINT-014 S14-PR-05A, Architect
    checkpoint: ninth review, generic read-only knowledge composition).
    Pure data -- no market_data/facts dependency needed to construct one,
    so a strategy-owned binding (which cannot import either) can build
    these directly. ``capability`` names which sealed resolution grounds
    this fact's own provenance; a generic orchestrator elsewhere looks
    that resolution up by capability and never needs to know why a
    binding chose it.
    """

    capability: MarketCapability
    value: object
    subject: str
    fact_type: str
