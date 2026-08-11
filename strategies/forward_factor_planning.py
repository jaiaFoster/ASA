"""Provider-blind subject demands for Forward Factor."""

from __future__ import annotations

from datetime import date, datetime
from typing import Mapping  # noqa: UP035 -- strategies boundary permits typing only

from analytics.expiration_selection import ExpirationCandidate, rank_expiration_pairs
from domain import (
    CapabilityDemand,
    DemandExpansion,
    EvidenceUsability,
    ExpirationCollection,
    MarketCapability,
    OptionChain,
    ResolvedCapabilityEvidence,
    UnknownReason,
)
from strategies import FORWARD_FACTOR_CALENDAR_MANIFEST
from strategies.earnings_calendar_planning import earnings_demand
from strategies.manifest import node_parameter_value

MAX_PAIR_ATTEMPTS = 5


def _policy() -> dict[str, int]:
    names = (
        "front_min_dte",
        "front_max_dte",
        "back_min_dte",
        "back_max_dte",
        "minimum_gap_days",
        "maximum_gap_days",
        "target_front_dte",
        "target_gap_days",
    )
    values: dict[str, int] = {}
    for name in names:
        value = node_parameter_value(FORWARD_FACTOR_CALENDAR_MANIFEST, "expiration_select", name)
        assert isinstance(value, int) and not isinstance(value, bool)
        values[name] = value
    return values


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
    return quote_demand(now), expirations_demand(now), earnings_demand(now)


def _candidates(
    evidence: ResolvedCapabilityEvidence | None, as_of: date
) -> tuple[ExpirationCandidate, ...]:
    if evidence is None or evidence.usability is not EvidenceUsability.RESOLVED:
        return ()
    if isinstance(evidence.value, ExpirationCollection):
        dates = tuple(cycle.expiration_date for cycle in evidence.value.cycles)
    elif isinstance(evidence.value, OptionChain):
        dates = tuple(sorted({contract.expiration for contract in evidence.value.contracts}))
    else:
        return ()
    return tuple(
        ExpirationCandidate(expiration, (expiration - as_of).days)
        for expiration in dates
        if expiration >= as_of
    )


def expand_demands(
    evidence: Mapping[str, ResolvedCapabilityEvidence], *, now: datetime
) -> DemandExpansion:
    discovery = expirations_demand(now)
    ranked = rank_expiration_pairs(
        _candidates(evidence.get(discovery.demand_id), now.date()),
        **_policy(),
    )[:MAX_PAIR_ATTEMPTS]
    if not ranked:
        return DemandExpansion(
            unknown_reasons=(
                UnknownReason("no_valid_expiration_pair", (discovery.demand_id,)),
            )
        )
    dates = tuple(sorted({item.expiration_date for pair in ranked for item in pair}))
    demands = tuple(chain_demand(now, expiration) for expiration in dates)
    selections = tuple(
        (f"pair_{index}", f"{front.expiration_date.isoformat()}/{back.expiration_date.isoformat()}")
        for index, (front, back) in enumerate(ranked)
    )
    return DemandExpansion(demands=demands, selections=selections)


def resolved_field_requirements() -> dict[MarketCapability, tuple[tuple[str, ...], int]]:
    return {
        MarketCapability.REAL_TIME_QUOTE_V1: (("last",), 3600),
        MarketCapability.OPTION_CHAIN_V1: (("contracts",), 3600),
        MarketCapability.EARNINGS_CALENDAR_V1: (("earnings_date",), 3600),
    }
