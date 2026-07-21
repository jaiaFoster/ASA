"""Cross-cutting reference and confidence value types (ADR-004 `domain/`).

Structural definitions only — no business logic (ASA-CORE-001).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EvidenceKind(str, Enum):
    """The kind of record an EvidenceReference points at."""

    OBSERVATION = "observation"
    CANONICAL_FACT = "canonical_fact"
    INDICATOR = "indicator"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """A pinned reference to a specific version of an evidence record.

    ADR-003 requires every Opportunity to carry a traceable path back to
    Evidence; ADR-006 requires that path to pin versions, not names.
    ``version`` is None only for Observations, which are unversioned
    append-only records (ADR-001).
    """

    kind: EvidenceKind
    referenced_id: str
    version: int | None = None


@dataclass(frozen=True, slots=True)
class Confidence:
    """A deterministic confidence value in [0.0, 1.0] (ADR-001).

    On a Canonical Fact this is an internal reconciliation attribute
    (ADR-001 as amended by ASA-CORE-001); on an Opportunity it appears
    only as deterministically aggregated evidence confidence (ADR-003).
    """

    score: float
