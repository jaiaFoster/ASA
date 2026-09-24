"""Provider-blind subject demands for the SPY 30-DTE put credit spread.

Source: Option Alpha, "8 SPY Put Credit Spread Backtest Results Analyzed"
(Du Plessis, Henry, Hysmith; 2021-11-17, updated 2023-01-11), backtest 1:
"30 days to expiration" -- implemented as the future expiration nearest 30
calendar days. An equidistant tie is a typed unknown, never a chosen side.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Mapping  # noqa: UP035

from domain import (
    CapabilityDemand,
    DemandExpansion,
    EvidenceUsability,
    ExpirationCollection,
    MarketCapability,
    ResolvedCapabilityEvidence,
    UnknownReason,
)

TARGET_DAYS_TO_EXPIRATION = 30


def quote_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(MarketCapability.REAL_TIME_QUOTE_V1, ("last",), now, now)


def expirations_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(MarketCapability.OPTION_CHAIN_V1, ("expirations",), now, now)


def chain_demand(now: datetime, expiration: date) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.OPTION_CHAIN_V1,
        ("contracts",),
        now,
        now,
        expiration=expiration,
    )


def bootstrap_demands(now: datetime) -> tuple[CapabilityDemand, ...]:
    return quote_demand(now), expirations_demand(now)


def select_target_expiration(expirations: tuple[date, ...], today: date) -> date | UnknownReason:
    """Nearest future expiration to the target DTE; a tie is a typed unknown."""
    future = sorted({item for item in expirations if item > today})
    if not future:
        return UnknownReason("no_future_expiration")
    distances = sorted(
        (abs((item - today).days - TARGET_DAYS_TO_EXPIRATION), item) for item in future
    )
    if len(distances) > 1 and distances[0][0] == distances[1][0]:
        return UnknownReason("ambiguous_expiration_tie")
    return distances[0][1]


def expand_demands(
    evidence: Mapping[str, ResolvedCapabilityEvidence], *, now: datetime
) -> DemandExpansion:
    discovery = expirations_demand(now)
    resolved = evidence.get(discovery.demand_id)
    if (
        resolved is None
        or resolved.usability is not EvidenceUsability.RESOLVED
        or not isinstance(resolved.value, ExpirationCollection)
    ):
        return DemandExpansion(unknown_reasons=(UnknownReason("no_future_expiration"),))
    selected = select_target_expiration(
        tuple(cycle.expiration_date for cycle in resolved.value.cycles), now.date()
    )
    if isinstance(selected, UnknownReason):
        return DemandExpansion(unknown_reasons=(selected,))
    return DemandExpansion(
        demands=(chain_demand(now, selected),),
        selections=(("expiration", selected.isoformat()),),
    )


def resolved_field_requirements() -> dict[MarketCapability, tuple[tuple[str, ...], int]]:
    return {
        MarketCapability.REAL_TIME_QUOTE_V1: (("last",), 3600),
        MarketCapability.OPTION_CHAIN_V1: (("contracts",), 3600),
    }
