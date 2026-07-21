"""Indicator — versioned, immutable derived value (ADR-006).

Structural definitions only — no business logic (ASA-CORE-001).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.references import EvidenceReference


@dataclass(frozen=True, slots=True)
class Indicator:
    """One immutable version of a derived Indicator value (ADR-006).

    A new version is produced when an underlying Canonical Fact version
    changes or the calculation logic changes. ``computed_from`` pins the
    exact Canonical Fact version(s); ``logic_version`` pins the exact
    calculation-logic version. Never mutated or silently recomputed.
    """

    indicator_id: str
    version: int
    logic_version: str
    value: object
    computed_from: tuple[EvidenceReference, ...]
    effective_time: datetime
    created_time: datetime
