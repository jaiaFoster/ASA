"""Provider-neutral staged demands for the Cboe BXM methodology."""

from datetime import datetime, timedelta
from typing import Mapping  # noqa: UP035

from analytics.calendar_facts import new_york_time
from domain import (
    CapabilityDemand,
    DemandExpansion,
    MarketCapability,
    ResolvedCapabilityEvidence,
)
from strategies.cboe_put_planning import (
    expand_demands as expand_monthly_chain_demands,
)
from strategies.cboe_put_planning import (
    expirations_demand,
    quote_demand,
)


def trade_tape_demand(now: datetime) -> CapabilityDemand:
    local = new_york_time(now)
    window_start = local.replace(hour=11, minute=30, second=0, microsecond=0)
    window_end = local.replace(hour=13, minute=30, second=0, microsecond=0)
    return CapabilityDemand(
        MarketCapability.OPTION_TRADE_TAPE_V1,
        ("contract_identity", "event_time", "price", "sale_condition_codes", "size"),
        window_start,
        window_end,
        required=False,
    )


def dividend_points_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.INDEX_DIVIDEND_POINTS_V1,
        ("effective_date", "points"),
        now - timedelta(days=35),
        now,
        required=False,
    )


def settlement_value_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.INDEX_SETTLEMENT_VALUE_V1,
        ("observed_at", "settlement_date", "settlement_style", "value"),
        now - timedelta(days=35),
        now,
        required=False,
    )


def bootstrap_demands(now: datetime) -> tuple[CapabilityDemand, ...]:
    return (
        quote_demand(now),
        expirations_demand(now),
        trade_tape_demand(now),
        dividend_points_demand(now),
        settlement_value_demand(now),
    )


def expand_demands(
    evidence: Mapping[str, ResolvedCapabilityEvidence], *, now: datetime
) -> DemandExpansion:
    expanded = expand_monthly_chain_demands(evidence, now=now)
    return DemandExpansion(expanded.demands, expanded.selections, expanded.unknown_reasons)


def resolved_field_requirements() -> dict[MarketCapability, tuple[tuple[str, ...], int]]:
    return {
        MarketCapability.REAL_TIME_QUOTE_V1: (("last",), 3600),
        MarketCapability.OPTION_CHAIN_V1: (("contracts",), 3600),
        MarketCapability.OPTION_TRADE_TAPE_V1: (
            ("contract_identity", "event_time", "price", "sale_condition_codes", "size"),
            86400,
        ),
        MarketCapability.INDEX_DIVIDEND_POINTS_V1: (("effective_date", "points"), 86400 * 35),
        MarketCapability.INDEX_SETTLEMENT_VALUE_V1: (
            ("observed_at", "settlement_date", "settlement_style", "value"),
            86400 * 35,
        ),
    }
