"""Provider identity value type (ADR-002).

Structural definitions only — no business logic (ASA-CORE-001).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Provider:
    """A stable, ASA-internal Provider identity (ADR-002).

    ``provider_id`` is distinct from any vendor-specific account or API-key
    identifier and must not change when keys rotate or vendors rename tiers.
    """

    provider_id: str
    name: str
