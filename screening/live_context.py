"""Live subject construction and chain-derived expirations (LIVE-002).

Bridges screening/live_acquisition.py's canonical acquisition output back
into the shapes screening/context_builders.py already expects -- no new
strategy logic, no provider-specific code. Monthly/weekly classification
uses the same standard third-Friday convention already used elsewhere in
this codebase (strategies/stonk_components.py's private
_is_monthly_expiration), reimplemented locally since screening/ cannot
reach into strategies/'s private internals and this is a small, standard,
non-controversial calendar rule, not strategy logic.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from analytics.atm_selection import select_atm_strike
from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    ExpirationCycle,
    Instrument,
    InstrumentKind,
    MarketCapability,
    MarketDataRequestContext,
    MarketDataSubject,
    MarketDataSubjectType,
    OptionChain,
    OptionType,
    ProviderAddressProjection,
)


class NoContractsAtExpirationError(ValueError):
    """No contract of the requested type exists at the given expiration."""


def select_atm_strike_at_expiration(
    chain: OptionChain, expiration: date, spot_price: Decimal, option_type: OptionType
) -> Decimal:
    strikes = tuple(
        contract.strike
        for contract in chain.find(expiration=expiration, option_type=option_type)
    )
    if not strikes:
        raise NoContractsAtExpirationError(
            f"no {option_type.value} contracts at expiration {expiration.isoformat()}"
        )
    return select_atm_strike(strikes, spot_price)


def _is_monthly_expiration(expiration: date) -> bool:
    """Third Friday of the month -- the standard monthly options cycle."""
    return expiration.weekday() == 4 and 15 <= expiration.day <= 21


def expirations_from_chain(chain: OptionChain, as_of: date) -> tuple[ExpirationCycle, ...]:
    """Derive the distinct expiration cycles actually present in an
    acquired live OptionChain -- no separate acquisition needed.
    """
    unique_dates = sorted({contract.expiration for contract in chain.contracts})
    return tuple(
        ExpirationCycle(
            expiration,
            (expiration - as_of).days,
            _is_monthly_expiration(expiration),
            not _is_monthly_expiration(expiration),
            as_of,
            chain.evidence,
        )
        for expiration in unique_dates
        if expiration >= as_of
    )


# CapabilityFulfillmentService selects the serving provider internally
# (priority order, with fallback) -- the caller cannot know in advance
# which one will actually be tried, and each provider looks up its own
# symbol mapping via subject.projection_for(that provider's own
# provider_id, ...). So the subject must carry one projection per provider
# that could possibly be selected, not a single placeholder -- every
# provider this codebase knows how to construct uses the ticker symbol
# directly as its own address value, so the same symbol is valid for all.
KNOWN_PROVIDER_IDS = ("tradier", "finnhub", "alpha_vantage", "deterministic_fixture")


def build_capability_subject(
    symbol: str,
    capability: MarketCapability,
    as_of: datetime,
    *,
    provider_symbol_window_days: int = 2,
) -> MarketDataSubject:
    """A bounded, symbol-scoped subject for acquire_capability(). The
    symbol is always caller-supplied explicitly -- never inferred, never
    unbounded (screening/cli.py validates it against an explicit,
    finite universe before this is ever called).
    """
    subject_type = {
        MarketCapability.OPTION_CHAIN_V1: MarketDataSubjectType.OPTION_UNDERLYING,
        MarketCapability.EARNINGS_CALENDAR_V1: MarketDataSubjectType.EARNINGS_SECURITY,
    }.get(capability, MarketDataSubjectType.INSTRUMENT)
    evidence = (EvidenceReference(EvidenceKind.OBSERVATION, f"screening:live:{symbol}"),)
    window_start = as_of - timedelta(days=provider_symbol_window_days)
    projections = tuple(
        ProviderAddressProjection(provider_id, "v1", "symbol", symbol, window_start, None, evidence)
        for provider_id in KNOWN_PROVIDER_IDS
    )
    instrument = Instrument(
        CanonicalInstrumentIdentity("symbol", symbol), InstrumentKind.EQUITY, symbol, "USD"
    )
    required_fields = {
        MarketCapability.OPTION_CHAIN_V1: ("contracts",),
        MarketCapability.EARNINGS_CALENDAR_V1: ("earnings_date",),
        MarketCapability.REAL_TIME_QUOTE_V1: ("last",),
    }.get(capability, ("last",))
    return MarketDataSubject(
        instrument,
        subject_type,
        capability,
        MarketDataRequestContext(as_of, as_of, required_fields, projections, evidence),
    )
