"""Provider-blind subject demands for the stock benchmarks (B001/B002)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Mapping  # noqa: UP035

from domain import (
    CapabilityDemand,
    DemandExpansion,
    MarketCapability,
    ResolvedCapabilityEvidence,
)

# Ten completed calendar months back from any as_of date reaches at most
# ~310 days into the past; this adds a full extra quarter of buffer for
# month-boundary/weekend/holiday alignment without inventing a second,
# hand-tuned constant elsewhere.
HISTORICAL_LOOKBACK_DAYS = 400


def quote_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(MarketCapability.REAL_TIME_QUOTE_V1, ("last",), now, now)


def bars_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.HISTORICAL_BARS_V1,
        ("close",),
        now - timedelta(days=HISTORICAL_LOOKBACK_DAYS),
        now,
        maximum_age_seconds=int(timedelta(days=HISTORICAL_LOOKBACK_DAYS + 1).total_seconds()),
    )


def b001_bootstrap_demands(now: datetime) -> tuple[CapabilityDemand, ...]:
    return (quote_demand(now),)


def b002_bootstrap_demands(now: datetime) -> tuple[CapabilityDemand, ...]:
    return quote_demand(now), bars_demand(now)


def no_op_expand(evidence: Mapping[str, ResolvedCapabilityEvidence]) -> DemandExpansion:
    """Neither benchmark selects an expiration or any other phase-two
    evidence -- both are single-phase acquisitions."""

    del evidence
    return DemandExpansion()


def b001_resolved_field_requirements() -> dict[MarketCapability, tuple[tuple[str, ...], int]]:
    return {MarketCapability.REAL_TIME_QUOTE_V1: (("last",), 3600)}


def b002_resolved_field_requirements() -> dict[MarketCapability, tuple[tuple[str, ...], int]]:
    return {
        MarketCapability.REAL_TIME_QUOTE_V1: (("last",), 3600),
        MarketCapability.HISTORICAL_BARS_V1: (
            ("close",),
            int(timedelta(days=HISTORICAL_LOOKBACK_DAYS + 1).total_seconds()),
        ),
    }
