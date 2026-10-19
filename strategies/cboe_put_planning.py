"""Provider-neutral two-phase demands for Cboe PUT."""

from datetime import date, datetime
from typing import Mapping  # noqa: UP035

from domain import (
    CapabilityDemand,
    DemandExpansion,
    ExpirationCycle,
    MarketCapability,
    ResolvedCapabilityEvidence,
    UnknownReason,
)
from strategies.monthly_option_planning import chain_demand as chain_demand
from strategies.monthly_option_planning import expand_monthly_chain_demands, next_month_expiration
from strategies.monthly_option_planning import expirations_demand as expirations_demand
from strategies.monthly_option_planning import quote_demand as quote_demand


def bootstrap_demands(now: datetime) -> tuple[CapabilityDemand, ...]:
    return quote_demand(now), expirations_demand(now)


def _next_month_expiration(
    expirations: tuple[ExpirationCycle, ...], today: date
) -> date | UnknownReason:
    return next_month_expiration(expirations, today) or UnknownReason("G_PUT_STRIKE_EXISTS_UNKNOWN")


def expand_demands(
    evidence: Mapping[str, ResolvedCapabilityEvidence], *, now: datetime
) -> DemandExpansion:
    return expand_monthly_chain_demands(
        evidence, now=now, unknown_code="G_PUT_STRIKE_EXISTS_UNKNOWN"
    )


def resolved_field_requirements() -> dict[MarketCapability, tuple[tuple[str, ...], int]]:
    return {
        MarketCapability.REAL_TIME_QUOTE_V1: (("last",), 3600),
        MarketCapability.OPTION_CHAIN_V1: (("contracts",), 3600),
    }
