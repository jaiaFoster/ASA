"""Provenance — first-class, externally visible (ADR-001 as amended).

Structural definitions only — no business logic (ASA-CORE-001).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ProviderDisagreement:
    """One Provider's conflicting report, retained for drill-down (ADR-001)."""

    provider_id: str
    observation_id: str
    reported_value: object


@dataclass(frozen=True, slots=True)
class Provenance:
    """Complete provenance for a reconciled record (ADR-001 as amended).

    Carries everything the amended ADR-001 drill-down requirement demands:
    contributing providers, selected provider, provider disagreements,
    timestamps, and reconciliation metadata. Every Canonical Fact version
    must carry one of these structurally — it is not an optional annotation.
    """

    contributing_observation_ids: tuple[str, ...]
    contributing_provider_ids: tuple[str, ...]
    selected_provider_id: str | None
    disagreements: tuple[ProviderDisagreement, ...]
    reconciled_at: datetime
    reconciliation_metadata: tuple[tuple[str, str], ...] = field(default=())
