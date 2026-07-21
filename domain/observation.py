"""Observation — immutable, append-only provider evidence (ADR-001).

Structural definitions only — no business logic (ASA-CORE-001).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.values import require_normalized, require_tz_aware


@dataclass(frozen=True, slots=True)
class Observation:
    """What a specific Provider reported, at a specific time (ADR-001).

    Never edited or deleted once written; a Provider correction is a new
    Observation. ``value`` is already structurally normalized into ASA's
    schema for ``observation_type`` (ADR-002) — normalization is a
    structural transform, never an interpretive one.
    """

    observation_id: str
    observation_type: str
    provider_id: str
    value: object
    effective_time: datetime
    recorded_time: datetime

    def __post_init__(self) -> None:
        require_normalized(self.value, "Observation", "value")
        require_tz_aware(self.effective_time, "Observation", "effective_time")
        require_tz_aware(self.recorded_time, "Observation", "recorded_time")
