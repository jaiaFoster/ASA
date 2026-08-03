"""Live target strategy adapters (LIVE-002, PATCH-007A/TRADIER-PATCH-003/004).

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

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import cast

from analytics.derived_facts import (
    compute_iv_realized_spread,
    compute_no_confirmed_earnings_through_expiration,
    compute_normalized_skew,
)
from analytics.expiration_selection import (
    ExpirationCandidate,
    rank_expiration_pairs,
    select_earnings_relative_expiration_pair,
)
from analytics.realized_volatility import compute_realized_volatility, compute_trailing_return
from domain import (
    DomainInvariantError,
    EarningsEvent,
    MarketCapability,
    OHLCVBar,
    OptionChain,
    OptionType,
    Quote,
)
from market_data import (
    CapabilityFulfillmentService,
    FulfillmentStatus,
    ProviderErrorCode,
)
from market_data.session_calendar import MarketSessionStatus, UsEquitySessionCalendar
from market_data.temporal import (
    DEFAULT_FRESHNESS_REQUIREMENT,
    FreshnessRequirement,
    UsabilityStatus,
    evaluate_temporal_usability,
)
from screening.clock import Clock
from screening.context_builders import (
    FORWARD_FACTOR_DTE_POLICY,
    build_earnings_calendar_context,
    build_forward_factor_context,
    build_skew_momentum_context,
)
from screening.explanations import build_graph_explanation
from screening.live_acquisition import acquire_capability
from screening.live_context import (
    acquire_expirations,
    build_capability_subject,
    classify_domain_invariant_error,
    combine_option_chains,
    select_atm_strike_at_expiration,
    select_nearest_delta_contract,
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
from strategies.manifest import StrategyManifest
from strategies.plugins import build_plugin_registry
from strategies.scoring import normalize_richness
from strategies.type_system import ComponentValues

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
    "target_gap_days": 30,
    "gap_tolerance_days": 5,
}
EARNINGS_CALENDAR_LOOKAHEAD_DAYS = EARNINGS_CALENDAR_DTE_POLICY["back_max_dte"]
MAX_FORWARD_FACTOR_PAIR_ATTEMPTS = 5


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
    manifest: StrategyManifest,
    outputs: ComponentValues,
    score_name: str,
    evidence: tuple[object, ...],
) -> ScreeningResult:
    verdict = outputs.get("verdict").value
    score = outputs.get(score_name).value
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
        build_graph_explanation(manifest, outputs),
    )


def _acquire_or_raise(
    fulfillment: CapabilityFulfillmentService,
    symbol: str,
    capability: MarketCapability,
    now: datetime,
    required_fields: tuple[str, ...],
    *,
    expiration: date | None = None,
    effective_start: datetime | None = None,
    effective_end: datetime | None = None,
    freshness_requirement: FreshnessRequirement = DEFAULT_FRESHNESS_REQUIREMENT,
) -> object:
    request_start = effective_start or now
    request_end = effective_end or now
    subject = build_capability_subject(
        symbol,
        capability,
        now,
        effective_start=request_start,
        effective_end=request_end,
        required_fields=required_fields,
        expiration=expiration,
    )
    try:
        result = acquire_capability(
            fulfillment,
            capability,
            subject,
            effective_start=request_start,
            effective_end=request_end,
            required_fields=required_fields,
            maximum_age_seconds=3600,
        )
    except DomainInvariantError as exc:
        raise StrategyAdapterError(
            ScreeningOutcomeStatus.MISSING_DATA,
            classify_domain_invariant_error(exc, capability, symbol),
        ) from exc
    if result.status is FulfillmentStatus.FAILED or not result.observations:
        attempt_summary = ", ".join(
            f"{attempt.provider_id}:{attempt.error.code.value}"
            for attempt in result.attempts
            if attempt.error is not None
        )
        detail = (
            f"a valid request for live {capability.value} for {symbol} "
            "could not be completed or normalized"
        )
        if attempt_summary:
            detail += f"; provider outcomes: {attempt_summary}"
        if expiration is not None:
            detail += f" at expiration {expiration.isoformat()}"
        raise StrategyAdapterError(ScreeningOutcomeStatus.MISSING_DATA, detail)
    observation = result.observations[0]
    market_is_open = UsEquitySessionCalendar().status_at(now) is MarketSessionStatus.OPEN
    usability = evaluate_temporal_usability(
        observation.freshness,
        freshness_requirement,
        market_is_open=market_is_open,
    )
    if usability.status is UsabilityStatus.REJECTED:
        raise StrategyAdapterError(
            ScreeningOutcomeStatus.MISSING_DATA,
            f"{capability.value} for {symbol} is not usable: {usability.reason}",
        )
    return observation.value


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
            fulfillment,
            symbol,
            MarketCapability.OPTION_CHAIN_V1,
            now,
            ("contracts",),
            expiration=expiration,
        )
        for expiration in unique_expirations
    )
    return combine_option_chains(chains, observed_at=now)  # type: ignore[arg-type]


def _acquire_optional_earnings(
    fulfillment: CapabilityFulfillmentService,
    symbol: str,
    now: datetime,
    back_expiration: date,
) -> EarningsEvent | None:
    """Return the earliest event or explicit no-data; reject every other failure."""

    effective_end = now + timedelta(days=max(0, (back_expiration - now.date()).days))
    subject = build_capability_subject(
        symbol,
        MarketCapability.EARNINGS_CALENDAR_V1,
        now,
        effective_start=now,
        effective_end=effective_end,
        required_fields=("earnings_date", "confirmed"),
    )
    result = acquire_capability(
        fulfillment,
        MarketCapability.EARNINGS_CALENDAR_V1,
        subject,
        effective_start=now,
        effective_end=effective_end,
        required_fields=("earnings_date", "confirmed"),
        maximum_age_seconds=3600,
        required=False,
    )
    if result.observations:
        events = tuple(cast(EarningsEvent, item.value) for item in result.observations)
        return min(events, key=lambda item: item.earnings_date)
    errors = tuple(attempt.error.code for attempt in result.attempts if attempt.error is not None)
    if errors and all(code is ProviderErrorCode.NO_DATA for code in errors):
        return None
    summary = ", ".join(code.value for code in errors) or "unknown_provider_error"
    raise StrategyAdapterError(
        ScreeningOutcomeStatus.MISSING_DATA,
        f"earnings exclusion evidence for {symbol} is unavailable: {summary}",
    )


def _spot_price(quote: Quote) -> Decimal:
    if quote.last is not None:
        return quote.last
    if quote.bid is not None and quote.ask is not None:
        return (quote.bid + quote.ask) / 2
    raise StrategyAdapterError(
        ScreeningOutcomeStatus.MISSING_DATA, "live quote has no last price or bid/ask midpoint"
    )


# SPRINT-011-CLOSEOUT/CLOSE-002: real, live-data-derived score inputs for
# Earnings Calendar and Skew Momentum, replacing what were unconditional
# hardcoded constants (identical for every symbol) since this ticket's
# original authorship. See project/reports/SPRINT-011.md for the full
# defect writeup and cited sources for each strategy's own thesis.
_HISTORICAL_LOOKBACK_DAYS = 45  # calendar days -- ~30 trading days


def _acquire_daily_closes(
    fulfillment: CapabilityFulfillmentService, symbol: str, now: datetime
) -> tuple[Decimal, ...]:
    """Oldest-first daily close series over a fixed lookback window, for
    realized-volatility and momentum computation. Unlike every other
    capability this module acquires, a historical-bars request fulfils as
    *one MarketObservation per day* (market_data/tradier.py's own
    _normalize()) -- this reads every observation, not just the first, and
    skips the single-observation freshness/usability gate _acquire_or_raise
    applies elsewhere: "freshness" for a completed prior trading day's
    close is not the same concept as for a live quote or chain.
    """
    lookback_start = now - timedelta(days=_HISTORICAL_LOOKBACK_DAYS)
    subject = build_capability_subject(
        symbol,
        MarketCapability.HISTORICAL_BARS_V1,
        now,
        effective_start=lookback_start,
        effective_end=now,
        required_fields=("close",),
    )
    try:
        result = acquire_capability(
            fulfillment,
            MarketCapability.HISTORICAL_BARS_V1,
            subject,
            effective_start=lookback_start,
            effective_end=now,
            required_fields=("close",),
            maximum_age_seconds=int(timedelta(days=_HISTORICAL_LOOKBACK_DAYS + 1).total_seconds()),
        )
    except DomainInvariantError as exc:
        raise StrategyAdapterError(
            ScreeningOutcomeStatus.MISSING_DATA,
            classify_domain_invariant_error(exc, MarketCapability.HISTORICAL_BARS_V1, symbol),
        ) from exc
    if result.status is FulfillmentStatus.FAILED or not result.observations:
        raise StrategyAdapterError(
            ScreeningOutcomeStatus.MISSING_DATA,
            f"a valid request for live {MarketCapability.HISTORICAL_BARS_V1.value} for "
            f"{symbol} could not be completed or normalized",
        )
    ordered = sorted(result.observations, key=lambda item: item.effective_time)
    closes = tuple(cast(OHLCVBar, item.value).close for item in ordered)
    if len(closes) < 2:
        raise StrategyAdapterError(
            ScreeningOutcomeStatus.MISSING_DATA,
            f"fewer than two historical daily closes available for {symbol}",
        )
    return closes


def build_live_forward_factor_adapter(
    symbol: str,
    fulfillment: CapabilityFulfillmentService,
    *,
    freshness_requirement: FreshnessRequirement = DEFAULT_FRESHNESS_REQUIREMENT,
) -> StrategyAdapter:
    def _run(definition: ScreeningStrategyDefinition, clock: Clock, run_id: str) -> ScreeningResult:
        now = clock.now()
        as_of = now.date()
        quote = _acquire_or_raise(
            fulfillment,
            symbol,
            MarketCapability.REAL_TIME_QUOTE_V1,
            now,
            ("last",),
            freshness_requirement=freshness_requirement,
        )
        spot_price = _spot_price(quote)  # type: ignore[arg-type]
        available_expirations = acquire_expirations(fulfillment, symbol, now)
        candidates = tuple(
            ExpirationCandidate(cycle.expiration_date, cycle.days_to_expiration)
            for cycle in available_expirations
        )
        ranked_pairs = rank_expiration_pairs(candidates, **FORWARD_FACTOR_DTE_POLICY)
        if not ranked_pairs:
            raise StrategyAdapterError(
                ScreeningOutcomeStatus.MISSING_DATA,
                f"no expiration pair for {symbol} satisfies Forward Factor's DTE policy",
            )
        attempted: list[str] = []
        chain = None
        selected = None
        for front, back in ranked_pairs[:MAX_FORWARD_FACTOR_PAIR_ATTEMPTS]:
            attempted.append(
                f"{front.expiration_date.isoformat()}/{back.expiration_date.isoformat()}"
            )
            try:
                chain = _acquire_combined_chain(
                    fulfillment, symbol, now, (front.expiration_date, back.expiration_date)
                )
            except StrategyAdapterError:
                continue
            selected = (front, back)
            break
        if chain is None or selected is None:
            raise StrategyAdapterError(
                ScreeningOutcomeStatus.MISSING_DATA,
                f"no listed Forward Factor expiration pair for {symbol} returned usable chains; "
                f"attempted {', '.join(attempted)}",
            )
        front, back = selected
        earnings_event = _acquire_optional_earnings(fulfillment, symbol, now, back.expiration_date)
        earnings_eligible = (
            True
            if earnings_event is None
            else compute_no_confirmed_earnings_through_expiration(
                confirmed=earnings_event.confirmed,
                earnings_date=earnings_event.earnings_date,
                as_of=as_of,
                back_expiration=back.expiration_date,
            )
        )
        # SPRINT-011-CLOSEOUT/CLOSE-001: selected independently per
        # expiration, not one shared strike reused at both -- see
        # build_forward_factor_context's own docstring for why.
        front_strike = select_atm_strike_at_expiration(
            chain, front.expiration_date, spot_price, OptionType.CALL
        )
        back_strike = select_atm_strike_at_expiration(
            chain, back.expiration_date, spot_price, OptionType.CALL
        )
        selected_expirations = tuple(
            cycle
            for cycle in available_expirations
            if cycle.expiration_date in {front.expiration_date, back.expiration_date}
        )
        context = build_forward_factor_context(
            chain,
            selected_expirations,
            as_of,
            front_strike=front_strike,
            back_strike=back_strike,
            earnings_eligible=earnings_eligible,
            confirmed_earnings_date=(
                earnings_event.earnings_date
                if earnings_event is not None and earnings_event.confirmed
                else None
            ),
            option_type=OptionType.CALL,
        )
        graph = compile_strategy_graph(FORWARD_FACTOR_CALENDAR_MANIFEST, _COMPONENT_REGISTRY)
        result = execute_strategy_graph(graph, context)
        return _live_result(
            definition,
            clock,
            run_id,
            symbol,
            FORWARD_FACTOR_CALENDAR_MANIFEST,
            result.outputs,
            "forward_factor",
            chain.evidence + (() if earnings_event is None else earnings_event.evidence),
        )

    return _run


def build_live_earnings_calendar_adapter(
    symbol: str,
    fulfillment: CapabilityFulfillmentService,
    *,
    freshness_requirement: FreshnessRequirement = DEFAULT_FRESHNESS_REQUIREMENT,
) -> StrategyAdapter:
    def _run(definition: ScreeningStrategyDefinition, clock: Clock, run_id: str) -> ScreeningResult:
        now = clock.now()
        as_of = now.date()
        event = _acquire_or_raise(
            fulfillment,
            symbol,
            MarketCapability.EARNINGS_CALENDAR_V1,
            now,
            ("earnings_date",),
            effective_end=now + timedelta(days=EARNINGS_CALENDAR_LOOKAHEAD_DAYS),
        )
        quote = _acquire_or_raise(
            fulfillment,
            symbol,
            MarketCapability.REAL_TIME_QUOTE_V1,
            now,
            ("last",),
            freshness_requirement=freshness_requirement,
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
            target_gap_days=EARNINGS_CALENDAR_DTE_POLICY["target_gap_days"],
            gap_tolerance_days=EARNINGS_CALENDAR_DTE_POLICY["gap_tolerance_days"],
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
        back_strike = select_atm_strike_at_expiration(
            chain, back_cycle.expiration_date, spot_price, OptionType.CALL
        )
        (front_contract,) = chain.find(
            expiration=front_cycle.expiration_date,
            strike=target_strike,
            option_type=OptionType.CALL,
        )
        (back_contract,) = chain.find(
            expiration=back_cycle.expiration_date, strike=back_strike, option_type=OptionType.CALL
        )
        if front_contract.implied_volatility is None or back_contract.implied_volatility is None:
            raise StrategyAdapterError(
                ScreeningOutcomeStatus.MISSING_DATA,
                f"front or back at-the-money contract for {symbol} has no implied_volatility",
            )
        # Term-structure richness (Karl Domm, "This Option Strategy Turned
        # $10k Into $1 Million In One Year", ~06:45): the single strongest
        # predictor in that video's own 72,500-event study was a steep
        # negative term-structure slope, i.e. front-month IV meaningfully
        # richer than the ~45-day-out expiration -- approximated here as
        # this strategy's own already-selected front/back ATM IVs, not a
        # separately-fetched fixed 45-day point (this system selects
        # front/back via its own earnings-relative DTE policy, not a fixed
        # calendar pin).
        term_richness = normalize_richness(
            front_contract.implied_volatility - back_contract.implied_volatility
        )
        closes = _acquire_daily_closes(fulfillment, symbol, now)
        realized_vol = compute_realized_volatility(closes)
        # iv30/rv30-style richness (same source, ~09:40): front-month IV
        # priced above what has actually realized -- the second predictor
        # that video's own decile analysis found correlated with returns.
        iv_rv_richness = normalize_richness(
            compute_iv_realized_spread(front_contract.implied_volatility, realized_vol)
        )
        context = build_earnings_calendar_context(
            chain,
            event,  # type: ignore[arg-type]
            front_cycle,
            back_cycle,
            as_of,
            target_strike=target_strike,
            term_structure_richness=term_richness,
            iv_realized_volatility_richness=iv_rv_richness,
        )
        graph = compile_strategy_graph(EARNINGS_CALENDAR_MANIFEST, _COMPONENT_REGISTRY)
        result = execute_strategy_graph(graph, context)
        return _live_result(
            definition,
            clock,
            run_id,
            symbol,
            EARNINGS_CALENDAR_MANIFEST,
            result.outputs,
            "score",
            chain.evidence,
        )

    return _run


def build_live_skew_momentum_adapter(
    symbol: str,
    fulfillment: CapabilityFulfillmentService,
    *,
    freshness_requirement: FreshnessRequirement = DEFAULT_FRESHNESS_REQUIREMENT,
) -> StrategyAdapter:
    def _run(definition: ScreeningStrategyDefinition, clock: Clock, run_id: str) -> ScreeningResult:
        now = clock.now()
        as_of = now.date()
        quote = _acquire_or_raise(
            fulfillment,
            symbol,
            MarketCapability.REAL_TIME_QUOTE_V1,
            now,
            ("last",),
            freshness_requirement=freshness_requirement,
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
        chain = cast(
            OptionChain,
            _acquire_or_raise(
                fulfillment,
                symbol,
                MarketCapability.OPTION_CHAIN_V1,
                now,
                ("contracts",),
                expiration=nearest.expiration_date,
            ),
        )
        call_strike = select_atm_strike_at_expiration(
            chain,
            nearest.expiration_date,
            spot_price,
            OptionType.CALL,
        )
        put_strike = select_atm_strike_at_expiration(
            chain,
            nearest.expiration_date,
            spot_price,
            OptionType.PUT,
        )
        (call_atm,) = chain.find(
            expiration=nearest.expiration_date,
            strike=call_strike,
            option_type=OptionType.CALL,
        )
        (put_atm,) = chain.find(
            expiration=nearest.expiration_date,
            strike=put_strike,
            option_type=OptionType.PUT,
        )
        call_wing = select_nearest_delta_contract(
            chain,
            nearest.expiration_date,
            OptionType.CALL,
            Decimal("0.25"),
            exclude_strike=call_strike,
        )
        put_wing = select_nearest_delta_contract(
            chain,
            nearest.expiration_date,
            OptionType.PUT,
            Decimal("-0.25"),
            exclude_strike=put_strike,
        )
        contracts = (call_atm, put_atm, call_wing, put_wing)
        if any(contract.implied_volatility is None for contract in contracts):
            raise StrategyAdapterError(
                ScreeningOutcomeStatus.MISSING_DATA,
                f"at-the-money or 25-delta wing contract for {symbol} has no implied_volatility",
            )
        call_atm_iv = cast(Decimal, call_atm.implied_volatility)
        put_atm_iv = cast(Decimal, put_atm.implied_volatility)
        call_wing_iv = cast(Decimal, call_wing.implied_volatility)
        put_wing_iv = cast(Decimal, put_wing.implied_volatility)
        normalized_call_skew = compute_normalized_skew(call_atm_iv, call_wing_iv)
        normalized_put_skew = compute_normalized_skew(put_atm_iv, put_wing_iv)
        closes = _acquire_daily_closes(fulfillment, symbol, now)
        realized_vol = compute_realized_volatility(closes)
        if len(closes) < 21:
            raise StrategyAdapterError(
                ScreeningOutcomeStatus.MISSING_DATA,
                "Skew Momentum requires 21 closes for a 20-session return",
            )
        time_series_return = compute_trailing_return(closes[-21:])
        context = build_skew_momentum_context(
            chain,
            nearest.expiration_date,
            normalized_call_skew=normalized_call_skew,
            normalized_put_skew=normalized_put_skew,
            # No canonical live history/universe source is wired yet.
            # Founder policy requires UNKNOWN, never a proxy fallback.
            call_skew_zscore=None,
            put_skew_zscore=None,
            historical_valid_observations=0,
            call_atm_iv_minus_rv=compute_iv_realized_spread(call_atm_iv, realized_vol),
            put_atm_iv_minus_rv=compute_iv_realized_spread(put_atm_iv, realized_vol),
            call_wing_iv_minus_rv=compute_iv_realized_spread(call_wing_iv, realized_vol),
            put_wing_iv_minus_rv=compute_iv_realized_spread(put_wing_iv, realized_vol),
            call_wing_iv_minus_atm_iv=call_wing_iv - call_atm_iv,
            put_wing_iv_minus_atm_iv=put_wing_iv - put_atm_iv,
            time_series_return=time_series_return,
            cross_sectional_percentile=None,
            comparison_peer_count=0,
            sector_relative_return=None,
        )
        graph = compile_strategy_graph(SKEW_MOMENTUM_VERTICAL_MANIFEST, _COMPONENT_REGISTRY)
        result = execute_strategy_graph(graph, context)
        return _live_result(
            definition,
            clock,
            run_id,
            symbol,
            SKEW_MOMENTUM_VERTICAL_MANIFEST,
            result.outputs,
            "score",
            chain.evidence,
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
