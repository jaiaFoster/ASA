"""Canonical Fact — versioned, immutable best understanding (ADR-001).

Structural definitions only — no business logic (ASA-CORE-001).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.provenance import Provenance
from domain.references import Confidence


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
