"""S001 provider-neutral demand for completed-month historical evidence."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Mapping  # noqa: UP035

from domain import (
    CapabilityDemand,
    DemandExpansion,
    MarketCapability,
    ResolvedCapabilityEvidence,
)

HISTORICAL_LOOKBACK_DAYS = 430


def s001_historical_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.HISTORICAL_BARS_V1,
        ("adjusted_close",),
        now - timedelta(days=HISTORICAL_LOOKBACK_DAYS),
        now,
        maximum_age_seconds=int(timedelta(days=HISTORICAL_LOOKBACK_DAYS + 1).total_seconds()),
    )


def no_phase_two(evidence: Mapping[str, ResolvedCapabilityEvidence]) -> DemandExpansion:
    del evidence
    return DemandExpansion()


def s001_resolved_field_requirements() -> dict[MarketCapability, tuple[tuple[str, ...], int]]:
    return {
        MarketCapability.HISTORICAL_BARS_V1: (
            ("adjusted_close",),
            int(timedelta(days=HISTORICAL_LOOKBACK_DAYS + 1).total_seconds()),
        )
    }
