"""Indicator — versioned, immutable derived value (ADR-006).

Structural definitions only — no business logic (ASA-CORE-001).

``indicator_type`` added in ASA-CORE-004: required to support deterministic
indicator identity (namespace ``asa.indicator``) and the Indicator
repository's ``by_indicator_type`` query, mirroring ``CanonicalFact.fact_type``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.references import EvidenceReference
from domain.values import require_normalized, require_positive, require_tz_aware


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
    indicator_type: str
    logic_version: str
    value: object
    computed_from: tuple[EvidenceReference, ...]
    effective_time: datetime
    created_time: datetime

    def __post_init__(self) -> None:
        require_positive(self.version, "Indicator", "version")
        require_normalized(self.value, "Indicator", "value")
        require_tz_aware(self.effective_time, "Indicator", "effective_time")
        require_tz_aware(self.created_time, "Indicator", "created_time")
