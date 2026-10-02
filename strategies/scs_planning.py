"""Provider-neutral two-phase SPX demands for SCS."""

from datetime import date, datetime, timedelta
from decimal import Decimal
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
from strategies.scs_components import select_monthly_expiration
from strategies.scs_manifest import scs_parameter


def quote_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(MarketCapability.REAL_TIME_QUOTE_V1, ("last",), now, now)


def expirations_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(MarketCapability.OPTION_CHAIN_V1, ("expirations",), now, now)


def chain_demand(now: datetime, expiration: date) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.OPTION_CHAIN_V1, ("contracts",), now, now, expiration=expiration
    )


def rate_demand(now: datetime, parameter_name: str) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.RATE_OBSERVATION_V1,
        ("value",),
        now - timedelta(days=7),
        now,
        # Optional input (the SCS evaluation types a missing rate); with no
        # enabled rate provider the demand must degrade to typed
        # UNSUPPORTED_CAPABILITY, never fail the shared SPX subject.
        required=False,
        subject_symbol=str(scs_parameter(parameter_name)),
        maximum_age_seconds=86400 * 7,
    )


def settlement_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.INDEX_SETTLEMENT_VALUE_V1,
        ("observed_at", "settlement_date", "settlement_style", "value"),
        now - timedelta(days=7),
        now,
        required=False,
    )


def bootstrap_demands(now: datetime) -> tuple[CapabilityDemand, ...]:
    return (
        quote_demand(now),
        expirations_demand(now),
        rate_demand(now, "risk_free_series"),
        rate_demand(now, "dividend_yield_series"),
        settlement_demand(now),
    )


def expand_demands(
    evidence: Mapping[str, ResolvedCapabilityEvidence], *, now: datetime
) -> DemandExpansion:
    resolved = evidence.get(expirations_demand(now).demand_id)
    if (
        resolved is None
        or resolved.usability is not EvidenceUsability.RESOLVED
        or not isinstance(resolved.value, ExpirationCollection)
    ):
        return DemandExpansion(unknown_reasons=(UnknownReason("G_SCS_EXPIRY_UNIQUE_UNKNOWN"),))
    target = Decimal(str(scs_parameter("target_dte_calendar_days")))
    if target != target.to_integral_value() or target <= 0:
        raise ValueError("target_dte_calendar_days must be a positive integer")
    expiration = select_monthly_expiration(
        tuple(
            (item.expiration_date, item.days_to_expiration, item.monthly)
            for item in resolved.value.cycles
        ),
        int(target),
        str(scs_parameter("expiration_cycle")),
    )
    if isinstance(expiration, UnknownReason):
        return DemandExpansion(unknown_reasons=(expiration,))
    return DemandExpansion(
        demands=(chain_demand(now, expiration),),
        selections=(("expiration", expiration.isoformat()),),
    )


def resolved_field_requirements() -> dict[MarketCapability, tuple[tuple[str, ...], int]]:
    return {
        MarketCapability.REAL_TIME_QUOTE_V1: (("last",), 3600),
        MarketCapability.OPTION_CHAIN_V1: (("contracts",), 3600),
        MarketCapability.RATE_OBSERVATION_V1: (("value",), 86400 * 7),
        MarketCapability.INDEX_SETTLEMENT_VALUE_V1: (
            ("observed_at", "settlement_date", "settlement_style", "value"),
            86400 * 7,
        ),
    }
