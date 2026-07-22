"""Live target strategy adapters (LIVE-002, PATCH-007A/TRADIER-PATCH-003).

Live-data counterparts of screening/adapters.py's fixture-backed run_*
functions: same manifests, same context_builders, same result
construction -- only the source of canonical market data changes, from
screening/fixtures.py to screening/live_acquisition.py. No strategy logic
is reimplemented here, same as SCREEN-004/ANALYTICS-003.

Each factory function closes over one symbol and one already-constructed
CapabilityFulfillmentService, returning a StrategyAdapter-conforming
callable. A missing or unfulfillable live capability, or no expiration
pair satisfying a strategy's DTE policy, raises StrategyAdapterError with
MISSING_DATA -- an expected, isolated, non-crashing outcome (SCREEN-003),
never a raw exception escaping to the runner's more generic
STRATEGY_EXCEPTION handling.

Option-chain acquisition is a two-step flow (TRADIER-PATCH-003, #156):
Tradier's real endpoint is scoped to one expiration per request, so a
strategy needing two expirations (Forward Factor, Earnings Calendar)
discovers available expirations first (acquire_expirations,
TRADIER-PATCH-001), selects the required pair via the same canonical
selection functions screening/context_builders.py already uses, acquires
one chain per selected expiration with an expiration-aware subject
(TRADIER-PATCH-002), and combines them into one chain
(combine_option_chains) before handing it to the unmodified context
builders and strategy graphs -- never assuming one chain response covers
every expiration.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from analytics.expiration_selection import (
    ExpirationCandidate,
    select_earnings_relative_expiration_pair,
    select_expiration_pair,
)
from domain import DomainInvariantError, EarningsEvent, MarketCapability, OptionChain, OptionType, Quote
from market_data import CapabilityFulfillmentService, FulfillmentStatus
from screening.clock import Clock
from screening.context_builders import (
    FORWARD_FACTOR_DTE_POLICY,
    build_earnings_calendar_context,
    build_forward_factor_context,
    build_skew_momentum_context,
)
from screening.live_acquisition import acquire_capability
from screening.live_context import (
    acquire_expirations,
    build_capability_subject,
    combine_option_chains,
    select_atm_strike_at_expiration,
)
from screening.registry import ScreeningStrategyDefinition
from screening.results import ScreeningOutcomeStatus, ScreeningResult
from screening.runner import StrategyAdapter, StrategyAdapterError
from strategies import (
    CORE_COMPONENTS,
    EARNINGS_CALENDAR_MANIFEST,
    FORWARD_FACTOR_CALENDAR_MANIFEST,
    SKEW_MOMENTUM_VERTICAL_MANIFEST,
    STONK_STRATEGY_PLUGINS,
    compile_strategy_graph,
    execute_strategy_graph,
)
from strategies.plugins import build_plugin_registry

_COMPONENT_REGISTRY = build_plugin_registry(CORE_COMPONENTS, STONK_STRATEGY_PLUGINS)
_NON_FAIL_VERDICTS = frozenset({"PASS", "WATCH"})

# Earnings Calendar's own frozen expiration_pair_selector node parameters
# (strategies/stonk_manifests.py) -- duplicated here for the same reason
# FORWARD_FACTOR_DTE_POLICY is: this ticket's data still needs an
# externally-selected pair for the parts of each manifest not connected to
# expiration_select via a graph edge.
EARNINGS_CALENDAR_DTE_POLICY = {
    "front_min_dte": 7,
    "front_max_dte": 21,
    "back_min_dte": 22,
    "back_max_dte": 75,
}


def _outcome_status_for_verdict(verdict: str) -> ScreeningOutcomeStatus:
    return (
        ScreeningOutcomeStatus.PASS
        if verdict in _NON_FAIL_VERDICTS
        else ScreeningOutcomeStatus.NO_SIGNAL
    )


def _live_result(
    definition: ScreeningStrategyDefinition,
    clock: Clock,
    run_id: str,
    symbol: str,
    verdict: object,
    score: object,
    evidence: tuple[object, ...],
) -> ScreeningResult:
    verdict_text = str(verdict)
    return ScreeningResult(
        run_id,
        definition.strategy_id,
        definition.strategy_version,
        f"symbol:{symbol}",
        clock.now(),
        _outcome_status_for_verdict(verdict_text),
        verdict_text,
        score if isinstance(score, Decimal) else None,
        evidence,  # type: ignore[arg-type]
        evidence,  # type: ignore[arg-type]
        None,
        None,
    )


def _acquire_or_raise(
    fulfillment: CapabilityFulfillmentService,
    symbol: str,
    capability: MarketCapability,
    now: datetime,
    required_fields: tuple[str, ...],
    *,
    expiration: date | None = None,
) -> object:
    subject = build_capability_subject(
        symbol, capability, now, required_fields=required_fields, expiration=expiration
    )
    try:
        result = acquire_capability(
            fulfillment,
            capability,
            subject,
            effective_start=now,
            effective_end=now,
            required_fields=required_fields,
            maximum_age_seconds=3600,
        )
    except DomainInvariantError as exc:
        # No enabled provider declares this capability at all (e.g. only
        # Tradier is configured and Tradier doesn't serve earnings data) --
        # CapabilityRegistry.lookup() raises rather than returning a
        # not-fulfilled result. A live-configuration gap, not an adapter
        # bug: same MISSING_DATA outcome as any other unfulfillable request.
        raise StrategyAdapterError(
            ScreeningOutcomeStatus.MISSING_DATA,
            f"no enabled live provider offers {capability.value} for {symbol}: {exc}",
        ) from exc
    if result.status is not FulfillmentStatus.FULFILLED or not result.observations:
        detail = f"could not acquire live {capability.value} for {symbol}"
        if expiration is not None:
            detail += f" at expiration {expiration.isoformat()}"
        raise StrategyAdapterError(ScreeningOutcomeStatus.MISSING_DATA, detail)
    return result.observations[0].value


def _acquire_combined_chain(
    fulfillment: CapabilityFulfillmentService,
    symbol: str,
    now: datetime,
    expirations: tuple[date, ...],
) -> OptionChain:
    """Acquire one option chain per distinct expiration in `expirations`
    (deduplicated, order preserved) and combine them into a single chain --
    the two-step live counterpart of a single, all-expirations fixture
    chain fetch (TRADIER-PATCH-003).
    """
    unique_expirations = tuple(dict.fromkeys(expirations))
    chains = tuple(
        _acquire_or_raise(
            fulfillment, symbol, MarketCapability.OPTION_CHAIN_V1, now, ("contracts",),
            expiration=expiration,
        )
        for expiration in unique_expirations
    )
    return combine_option_chains(chains, observed_at=now)  # type: ignore[arg-type]


def _spot_price(quote: Quote) -> Decimal:
    if quote.last is not None:
        return quote.last
    if quote.bid is not None and quote.ask is not None:
        return (quote.bid + quote.ask) / 2
    raise StrategyAdapterError(
        ScreeningOutcomeStatus.MISSING_DATA, "live quote has no last price or bid/ask midpoint"
    )


def build_live_forward_factor_adapter(
    symbol: str, fulfillment: CapabilityFulfillmentService
) -> StrategyAdapter:
    def _run(
        definition: ScreeningStrategyDefinition, clock: Clock, run_id: str
    ) -> ScreeningResult:
        now = clock.now()
        as_of = now.date()
        quote = _acquire_or_raise(
            fulfillment, symbol, MarketCapability.REAL_TIME_QUOTE_V1, now, ("last",)
        )
        spot_price = _spot_price(quote)  # type: ignore[arg-type]
        available_expirations = acquire_expirations(fulfillment, symbol, now)
        candidates = tuple(
            ExpirationCandidate(cycle.expiration_date, cycle.days_to_expiration)
            for cycle in available_expirations
        )
        selected = select_expiration_pair(candidates, **FORWARD_FACTOR_DTE_POLICY)
        if selected is None:
            raise StrategyAdapterError(
                ScreeningOutcomeStatus.MISSING_DATA,
                f"no expiration pair for {symbol} satisfies Forward Factor's DTE policy",
            )
        front, back = selected
        chain = _acquire_combined_chain(
            fulfillment, symbol, now, (front.expiration_date, back.expiration_date)
        )
        strike = select_atm_strike_at_expiration(chain, front.expiration_date, spot_price, OptionType.CALL)
        context = build_forward_factor_context(
            chain, available_expirations, as_of, strike=strike, option_type=OptionType.CALL
        )
        graph = compile_strategy_graph(FORWARD_FACTOR_CALENDAR_MANIFEST, _COMPONENT_REGISTRY)
        result = execute_strategy_graph(graph, context)
        return _live_result(
            definition,
            clock,
            run_id,
            symbol,
            result.outputs.get("verdict").value,
            result.outputs.get("forward_factor").value,
            chain.evidence,
        )

    return _run


def build_live_earnings_calendar_adapter(
    symbol: str, fulfillment: CapabilityFulfillmentService
) -> StrategyAdapter:
    def _run(
        definition: ScreeningStrategyDefinition, clock: Clock, run_id: str
    ) -> ScreeningResult:
        now = clock.now()
        as_of = now.date()
        event = _acquire_or_raise(
            fulfillment, symbol, MarketCapability.EARNINGS_CALENDAR_V1, now, ("earnings_date",)
        )
        quote = _acquire_or_raise(
            fulfillment, symbol, MarketCapability.REAL_TIME_QUOTE_V1, now, ("last",)
        )
        spot_price = _spot_price(quote)  # type: ignore[arg-type]
        available_expirations = acquire_expirations(fulfillment, symbol, now)
        candidates = tuple(
            ExpirationCandidate(cycle.expiration_date, cycle.days_to_expiration)
            for cycle in available_expirations
        )
        earnings_date = _earnings_date(event)  # type: ignore[arg-type]
        selected = select_earnings_relative_expiration_pair(
            candidates,
            earnings_date,
            front_min_dte=EARNINGS_CALENDAR_DTE_POLICY["front_min_dte"],
            front_max_dte=EARNINGS_CALENDAR_DTE_POLICY["front_max_dte"],
            back_min_dte=EARNINGS_CALENDAR_DTE_POLICY["back_min_dte"],
            back_max_dte=EARNINGS_CALENDAR_DTE_POLICY["back_max_dte"],
        )
        if selected is None:
            raise StrategyAdapterError(
                ScreeningOutcomeStatus.MISSING_DATA,
                f"no expiration pair for {symbol} spans its earnings date within policy",
            )
        front_candidate, back_candidate = selected
        front_cycle = next(
            cycle
            for cycle in available_expirations
            if cycle.expiration_date == front_candidate.expiration_date
        )
        back_cycle = next(
            cycle
            for cycle in available_expirations
            if cycle.expiration_date == back_candidate.expiration_date
        )
        chain = _acquire_combined_chain(
            fulfillment,
            symbol,
            now,
            (front_candidate.expiration_date, back_candidate.expiration_date),
        )
        target_strike = select_atm_strike_at_expiration(
            chain, front_cycle.expiration_date, spot_price, OptionType.CALL
        )
        context = build_earnings_calendar_context(
            chain, event, front_cycle, back_cycle, as_of, target_strike=target_strike  # type: ignore[arg-type]
        )
        graph = compile_strategy_graph(EARNINGS_CALENDAR_MANIFEST, _COMPONENT_REGISTRY)
        result = execute_strategy_graph(graph, context)
        return _live_result(
            definition,
            clock,
            run_id,
            symbol,
            result.outputs.get("verdict").value,
            result.outputs.get("score").value,
            chain.evidence,
        )

    return _run


def build_live_skew_momentum_adapter(
    symbol: str, fulfillment: CapabilityFulfillmentService
) -> StrategyAdapter:
    def _run(
        definition: ScreeningStrategyDefinition, clock: Clock, run_id: str
    ) -> ScreeningResult:
        now = clock.now()
        as_of = now.date()
        quote = _acquire_or_raise(
            fulfillment, symbol, MarketCapability.REAL_TIME_QUOTE_V1, now, ("last",)
        )
        spot_price = _spot_price(quote)  # type: ignore[arg-type]
        available_expirations = acquire_expirations(fulfillment, symbol, now)
        future_expirations = tuple(
            cycle for cycle in available_expirations if cycle.expiration_date > as_of
        )
        if not future_expirations:
            raise StrategyAdapterError(
                ScreeningOutcomeStatus.MISSING_DATA, f"no future expiration available for {symbol}"
            )
        # No dte_pair_selector node exists for Skew Momentum (it takes one
        # bare expiration, unlike the other two strategies) -- nearest
        # upcoming expiration ("front month") is the simplest, standard,
        # non-editorial default absent any other established policy.
        nearest = min(future_expirations, key=lambda cycle: cycle.expiration_date)
        chain = _acquire_or_raise(
            fulfillment,
            symbol,
            MarketCapability.OPTION_CHAIN_V1,
            now,
            ("contracts",),
            expiration=nearest.expiration_date,
        )
        strike = select_atm_strike_at_expiration(
            chain, nearest.expiration_date, spot_price, OptionType.CALL  # type: ignore[arg-type]
        )
        context = build_skew_momentum_context(
            chain, nearest.expiration_date, strike=strike, option_type=OptionType.CALL  # type: ignore[arg-type]
        )
        graph = compile_strategy_graph(SKEW_MOMENTUM_VERTICAL_MANIFEST, _COMPONENT_REGISTRY)
        result = execute_strategy_graph(graph, context)
        return _live_result(
            definition,
            clock,
            run_id,
            symbol,
            result.outputs.get("verdict").value,
            result.outputs.get("score").value,
            chain.evidence,  # type: ignore[attr-defined]
        )

    return _run


def _earnings_date(event: EarningsEvent) -> date:
    return event.earnings_date


LIVE_ADAPTER_FACTORIES = {
    "forward_factor": build_live_forward_factor_adapter,
    "earnings_calendar": build_live_earnings_calendar_adapter,
    "skew_momentum": build_live_skew_momentum_adapter,
}


def build_live_adapters(
    symbol: str, fulfillment: CapabilityFulfillmentService
) -> dict[str, StrategyAdapter]:
    """One live-driven adapter per target strategy, all bound to the same
    symbol and fulfillment service -- the live counterpart of
    screening.adapters.TARGET_STRATEGY_ADAPTERS.
    """
    return {
        strategy_id: factory(symbol, fulfillment)
        for strategy_id, factory in LIVE_ADAPTER_FACTORIES.items()
    }
