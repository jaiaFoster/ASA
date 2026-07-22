"""Live subject construction and chain-derived expirations (LIVE-002,
PATCH-007A/TRADIER-PATCH-001/TRADIER-PATCH-004).

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

from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal

from analytics.atm_selection import select_atm_strike
from domain import (
    CanonicalInstrumentIdentity,
    DomainInvariantError,
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
    OptionContract,
    OptionType,
    ProviderAddressProjection,
)
from market_data import CapabilityFulfillmentService, FulfillmentStatus
from screening.live_acquisition import acquire_capability
from screening.results import ScreeningOutcomeStatus
from screening.runner import StrategyAdapterError

# The only signal available to tell apart two DomainInvariantError causes
# that both mean "this live request cannot be fulfilled" for different
# reasons (TRADIER-PATCH-004): neither CapabilityFulfillmentService nor
# CapabilityRegistry expose a public pre-check a caller could use instead of
# reading the message, and adding one is a larger API-surface change than
# this ticket's own "narrow exception handling in _acquire_or_raise" scope.
_NO_CAPABLE_PROVIDER_MESSAGE_PREFIX = "No priority policy for"


def classify_domain_invariant_error(
    error: DomainInvariantError, capability: MarketCapability, symbol: str
) -> str:
    """Distinguish "no enabled provider declares this capability at all"
    (market_data/registry.py::ProviderPriorityPolicy.for_capability()
    raises "No priority policy for {capability}" before any provider is
    ever selected) from "a provider WAS selected, but the canonical request
    subject was incomplete or invalid for it" (#156's original defect --
    e.g. no "expiration" projection for an option-chain request -- and
    every other DomainInvariantError a provider's own fetch() can raise
    before its transport is ever reached).
    """
    if str(error).startswith(_NO_CAPABLE_PROVIDER_MESSAGE_PREFIX):
        return f"no enabled provider declares or satisfies {capability.value} for {symbol}: {error}"
    return (
        f"a provider was selected for {capability.value} for {symbol}, but the canonical "
        f"request subject was incomplete or invalid: {error}"
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


def combine_option_chains(
    chains: tuple[OptionChain, ...], observed_at: datetime
) -> OptionChain:
    """Combine one or more per-expiration OptionChain acquisitions into a
    single OptionChain a strategy manifest can query across all of them
    (TRADIER-PATCH-003).

    Tradier's real option-chain endpoint scopes each request to one
    expiration (TRADIER-PATCH-002/#156), so live acquisition of a strategy
    that needs two expirations (Forward Factor, Earnings Calendar) makes
    two separate chain requests -- but strategy components like
    strategies/stonk_components.py's CalendarStructure expect one chain
    object spanning every expiration they need, exactly like the offline
    fixture's single, all-expirations-at-once response already provides.

    OptionChain's own invariant requires every contract to share the
    chain's own observed_at exactly. Contracts from separately-timed
    acquisitions are rebuilt with one canonical observed_at (this
    combination's own caller-supplied timestamp) -- never their raw
    prices, strikes, or greeks -- the same modeling choice as treating
    near-simultaneous per-expiration reads as one logical market-data
    snapshot, not fabricating data.

    Deduplicates by contract identity after normalizing observed_at: a
    provider that (like the offline fixture) doesn't actually scope its
    response to the requested expiration and returns the same contracts
    for both requests would otherwise violate OptionCollection's own
    duplicate-contract invariant on merge.
    """
    if not chains:
        raise ValueError("combine_option_chains requires at least one chain")
    underlying = chains[0].underlying
    for chain in chains[1:]:
        if chain.underlying.identity != underlying.identity:
            raise ValueError("combine_option_chains requires every chain to share one underlying")
    deduplicated: dict[str, OptionContract] = {}
    for chain in chains:
        for contract in chain.contracts:
            normalized = replace(contract, observed_at=observed_at)
            deduplicated[normalized.identity] = normalized
    evidence = tuple(dict.fromkeys(item for chain in chains for item in chain.evidence))
    chain_id = "combined:" + ":".join(chain.option_chain_id for chain in chains)
    return OptionChain(
        chain_id, underlying, observed_at, tuple(deduplicated.values()), evidence
    )


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
    required_fields: tuple[str, ...] | None = None,
    expiration: date | None = None,
) -> MarketDataSubject:
    """A bounded, symbol-scoped subject for acquire_capability(). The
    symbol is always caller-supplied explicitly -- never inferred, never
    unbounded (screening/cli.py validates it against an explicit,
    finite universe before this is ever called).

    required_fields defaults to each capability's usual shape but can be
    overridden (e.g. ("expirations",) for an expirations-only OPTION_CHAIN_V1
    request) -- CapabilityRequest.__post_init__ requires the subject's own
    required_fields to match exactly what acquire_capability() is called
    with, so the two must always be constructed together, not independently.

    expiration, when given, additionally attaches one "expiration"-address-
    type ProviderAddressProjection per KNOWN_PROVIDER_IDS entry, explicit
    and separate from the "symbol" projection -- required by providers
    (Tradier) whose OPTION_CHAIN_V1 endpoint is scoped to one specific
    expiration per request (market_data/tradier.py's own
    subject.projection_for("tradier", "expiration", ...) lookup,
    TRADIER-PATCH-001/#156). Selecting *which* expiration to request is
    entirely the caller's own responsibility (via
    analytics/expiration_selection.py's canonical DTE-policy functions,
    over acquire_expirations()'s output) -- this only attaches whatever
    expiration the caller already chose, as an explicit projection value;
    it never invents, defaults, or hard-codes a selection policy itself.
    """
    if expiration is not None and expiration < as_of.date():
        raise ValueError(
            f"expiration {expiration.isoformat()} is before as_of {as_of.date().isoformat()}"
        )
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
    if expiration is not None:
        projections += tuple(
            ProviderAddressProjection(
                provider_id,
                "v1",
                "expiration",
                expiration.isoformat(),
                window_start,
                None,
                evidence,
            )
            for provider_id in KNOWN_PROVIDER_IDS
        )
    instrument = Instrument(
        CanonicalInstrumentIdentity("symbol", symbol), InstrumentKind.EQUITY, symbol, "USD"
    )
    if required_fields is None:
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


def acquire_expirations(
    fulfillment: CapabilityFulfillmentService,
    symbol: str,
    now: datetime,
) -> tuple[ExpirationCycle, ...]:
    """Acquire the option expirations available for `symbol`, independent
    of any single expiration's contracts (TRADIER-PATCH-001).

    Normalizes two distinct, both-legitimate provider response shapes into
    one canonical, deterministically-ordered result:

    - A provider (Tradier) that treats an expirations-only request
      (required_fields=("expirations",), no "contracts") as its own
      narrower query and returns one MarketObservation per expiration,
      each wrapping a bare ExpirationCycle.
    - A provider or fixture that doesn't distinguish an expirations-only
      request from a full chain request and returns one MarketObservation
      wrapping a complete OptionChain -- expirations are derived from its
      contracts locally via expirations_from_chain(), exactly as this
      module already does for a chain acquired for other reasons.

    Raises StrategyAdapterError(MISSING_DATA) on acquisition failure, an
    unrecognized response shape, or a result that normalizes to zero
    expirations -- callers never need a separate empty-result branch, since
    there is no legitimate case that looks empty but isn't a failure. Also
    raises MISSING_DATA (never a raw exception) if no enabled provider
    declares OPTION_CHAIN_V1 at all -- CapabilityRegistry.lookup() raises
    DomainInvariantError rather than returning a not-fulfilled result in
    that case (TRADIER-PATCH-004), same as screening/live_adapters.py's own
    _acquire_or_raise handles it.
    """
    subject = build_capability_subject(
        symbol, MarketCapability.OPTION_CHAIN_V1, now, required_fields=("expirations",)
    )
    try:
        result = acquire_capability(
            fulfillment,
            MarketCapability.OPTION_CHAIN_V1,
            subject,
            effective_start=now,
            effective_end=now,
            required_fields=("expirations",),
            maximum_age_seconds=3600,
        )
    except DomainInvariantError as exc:
        raise StrategyAdapterError(
            ScreeningOutcomeStatus.MISSING_DATA,
            classify_domain_invariant_error(exc, MarketCapability.OPTION_CHAIN_V1, symbol),
        ) from exc
    if result.status is not FulfillmentStatus.FULFILLED or not result.observations:
        raise StrategyAdapterError(
            ScreeningOutcomeStatus.MISSING_DATA,
            f"a valid request for live option expirations for {symbol} "
            "could not be completed or normalized",
        )
    as_of = now.date()
    values = tuple(observation.value for observation in result.observations)
    if all(isinstance(value, ExpirationCycle) for value in values):
        cycles: tuple[ExpirationCycle, ...] = values  # type: ignore[assignment]
    elif len(values) == 1 and isinstance(values[0], OptionChain):
        cycles = expirations_from_chain(values[0], as_of)
    else:
        raise StrategyAdapterError(
            ScreeningOutcomeStatus.MISSING_DATA,
            f"live option expiration response for {symbol} was neither a clean "
            "expiration list nor a single option chain",
        )
    unique_by_date = {cycle.expiration_date: cycle for cycle in cycles}
    ordered = tuple(unique_by_date[expiration] for expiration in sorted(unique_by_date))
    if not ordered:
        raise StrategyAdapterError(
            ScreeningOutcomeStatus.MISSING_DATA,
            f"live provider returned zero option expirations for {symbol}",
        )
    return ordered
