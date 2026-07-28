"""Explicit strategy-owned score transforms preserved during SPRINT-012."""

from __future__ import annotations

from decimal import Decimal


def normalize_richness(
    raw_value: Decimal,
    *,
    center: Decimal = Decimal(50),
    scale: Decimal = Decimal(300),
    floor: Decimal = Decimal(0),
    ceiling: Decimal = Decimal(100),
) -> Decimal:
    """Apply the existing version-1 bounded linear richness policy."""

    if scale <= 0 or floor > ceiling or not floor <= center <= ceiling:
        raise ValueError("richness normalization policy is invalid")
    return max(floor, min(ceiling, center + raw_value * scale))
