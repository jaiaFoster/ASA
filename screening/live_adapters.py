"""Live target strategy adapters (LIVE-002, PATCH-007A/TRADIER-PATCH-003/004).

Live-data counterparts of screening/adapters.py's fixture-backed run_*
functions: same manifests, same context_builders, same result
construction -- only the source of canonical market data changes, from
screening/fixtures.py to screening/live_acquisition.py. No strategy logic
is reimplemented here, same as SCREEN-004/ANALYTICS-003.

Each factory function closes over one symbol and one already-constructed
CapabilityFulfiller (market_data.subject_plan.CapabilityFulfiller --
either a raw CapabilityFulfillmentService or a PlanBackedFulfillment
wrapping one subject's own SubjectAcquisitionPlan, SPRINT-014 S14-PR-05A,
Architect checkpoint: twelfth review), returning a StrategyAdapter-
conforming callable. A missing or unfulfillable live capability, or no
expiration pair satisfying a strategy's DTE policy, raises
StrategyAdapterError with MISSING_DATA -- an expected, isolated,
non-crashing outcome (SCREEN-003), never a raw exception escaping to the
runner's more generic STRATEGY_EXCEPTION handling.

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
from typing import NamedTuple, Protocol, cast

from analytics.derived_facts import (
    compute_iv_realized_spread,
    compute_no_confirmed_earnings_through_expiration,
    compute_normalized_skew,
    compute_skew_stretch_distributions,
)
from analytics.expiration_selection import (
    ExpirationCandidate,
    rank_expiration_pairs,
    select_earnings_relative_expiration_pair,
)
from analytics.realized_volatility import compute_realized_volatility, compute_trailing_return
from domain import (
    CanonicalInstrumentIdentity,
    DomainInvariantError,
    EarningsEvent,
    HistoricalSkewObservation,
    HistoricalSkewObservations,
    MarketCapability,
    OHLCVBar,
    OHLCVSeries,
    OptionChain,
    OptionType,
    Quote,
)
from market_data import FulfillmentStatus, ProviderErrorCode
from market_data.capability_coalescing import combine_option_chains
from market_data.session_calendar import MarketSessionStatus, UsEquitySessionCalendar
from market_data.subject_plan import CapabilityFulfiller
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
    earnings_calendar_requirement,
    execute_strategy_graph,
)
from strategies.earnings_calendar_planning import (
    HISTORICAL_LOOKBACK_DAYS as EARNINGS_CALENDAR_HISTORICAL_LOOKBACK_DAYS,
)
from strategies.manifest import StrategyManifest
from strategies.plugins import build_plugin_registry
from strategies.scoring import normalize_richness
from strategies.type_system import ComponentValues

_COMPONENT_REGISTRY = build_plugin_registry(CORE_COMPONENTS, STONK_STRATEGY_PLUGINS)
_NON_FAIL_VERDICTS = frozenset({"PASS", "WATCH"})

# SPRINT-014 S14-PR-02: Earnings Calendar's own expiration_pair_selector
# node parameters are read directly from its manifest (the manifest is the
# only owner) via strategies.earnings_calendar_requirement() -- no second,
# independently maintained copy. Resolves SPRINT-013 S13-08's audit finding
# #1 (project/reports/SPRINT-013-S13-08-audit.md): this was previously a
# hand-duplicated dict with no accessor onto the manifest's own copy.
EARNINGS_CALENDAR_REQUIREMENT = earnings_calendar_requirement()
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
    fulfillment: CapabilityFulfiller,
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
    fulfillment: CapabilityFulfiller,
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
    fulfillment: CapabilityFulfiller,
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
#
# SPRINT-014 S14-PR-05A (Architect checkpoint, third review): this is now
# Skew Momentum's own value only -- Earnings Calendar's own lookback is
# strategy-owned at strategies.earnings_calendar_planning.
# HISTORICAL_LOOKBACK_DAYS (imported above as
# EARNINGS_CALENDAR_HISTORICAL_LOOKBACK_DAYS and passed explicitly at
# build_live_earnings_calendar_adapter's own _acquire_daily_closes() call
# site), never read from here. The two values are 45 today by
# coincidence, not by a shared source -- this module's own default below
# exists only for Skew Momentum's still-independent policy.
_HISTORICAL_LOOKBACK_DAYS = 45  # calendar days -- ~30 trading days

# SPRINT-013 S13-04D: mirrors strategies/stonk_manifests.py's own
# SKEW_MOMENTUM_VERTICAL_MANIFEST-declared historical_lookback_observations/
# minimum_valid_observations exactly (issue #255's approved research
# policy) -- duplicated here for the same reason EARNINGS_CALENDAR_DTE_
# POLICY/FORWARD_FACTOR_DTE_POLICY already are: this module's own
# acquisition-and-computation code needs these values directly, not only
# the manifest's own declarative record of them.
SKEW_HISTORICAL_LOOKBACK_OBSERVATIONS = 60
SKEW_MINIMUM_VALID_OBSERVATIONS = 40


class HistoricalSkewHistoryReader(Protocol):
    """Structural, read-only duplicate of strategy_runtime.historical_
    evidence.HistoricalSkewRepository's own history_for() method --
    screening must not import strategy_runtime (strategy_runtime is the
    more foundational layer, screening is one of its consumers, see
    strategy_runtime/market_data_planning.py's own docstring), so this
    file-local Protocol lets any conforming repository (in practice always
    that same concrete one, dependency-injected by whatever caller
    constructs it) be read from here structurally, with zero import
    coupling in either direction. Recording a new observation is
    deliberately not part of this Protocol -- see capture_skew_snapshot's
    own docstring for why the write path is never screening's own
    responsibility.
    """

    def history_for(
        self,
        instrument: CanonicalInstrumentIdentity,
        *,
        as_of: datetime | None = None,
        maximum_observations: int | None = None,
    ) -> tuple[HistoricalSkewObservation, ...]: ...


def _acquire_daily_closes(
    fulfillment: CapabilityFulfiller,
    symbol: str,
    now: datetime,
    *,
    lookback_days: int = _HISTORICAL_LOOKBACK_DAYS,
) -> tuple[Decimal, ...]:
    """Oldest-first daily close series over a fixed lookback window, for
    realized-volatility and momentum computation. Unlike every other
    capability this module acquires, a historical-bars request fulfils as
    *one MarketObservation per day* (market_data/tradier.py's own
    _normalize()) -- this reads every observation, not just the first, and
    skips the single-observation freshness/usability gate _acquire_or_raise
    applies elsewhere: "freshness" for a completed prior trading day's
    close is not the same concept as for a live quote or chain.

    ``lookback_days`` defaults to this module's own Skew-Momentum-owned
    constant; Earnings Calendar's own call site passes its strategy-owned
    value explicitly instead (SPRINT-014 S14-PR-05A, Architect checkpoint,
    third review) -- never a second, independently maintained copy.
    """
    lookback_start = now - timedelta(days=lookback_days)
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
            maximum_age_seconds=int(timedelta(days=lookback_days + 1).total_seconds()),
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
    # SPRINT-014 S14-PR-05A (Founder-approved bounded contract extension):
    # a provider-neutral, single-observation OHLCVSeries is now the
    # preferred normalized shape (market_data/tradier.py's own
    # historical-bars response). The older shape -- one OHLCVBar per
    # observation -- remains supported unchanged for any provider/fixture
    # not yet updated to emit the new series value.
    if len(result.observations) == 1 and isinstance(result.observations[0].value, OHLCVSeries):
        bars = result.observations[0].value.bars
    else:
        ordered = sorted(result.observations, key=lambda item: item.effective_time)
        bars = tuple(cast(OHLCVBar, item.value) for item in ordered)
    closes = tuple(bar.close for bar in bars)
    if len(closes) < 2:
        raise StrategyAdapterError(
            ScreeningOutcomeStatus.MISSING_DATA,
            f"fewer than two historical daily closes available for {symbol}",
        )
    return closes


def build_live_forward_factor_adapter(
    symbol: str,
    fulfillment: CapabilityFulfiller,
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
    fulfillment: CapabilityFulfiller,
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
            effective_end=now + timedelta(days=EARNINGS_CALENDAR_REQUIREMENT.lookahead_days),
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
            front_min_dte=EARNINGS_CALENDAR_REQUIREMENT.expiration_policy.front_min_dte,
            front_max_dte=EARNINGS_CALENDAR_REQUIREMENT.expiration_policy.front_max_dte,
            back_min_dte=EARNINGS_CALENDAR_REQUIREMENT.expiration_policy.back_min_dte,
            back_max_dte=EARNINGS_CALENDAR_REQUIREMENT.expiration_policy.back_max_dte,
            target_gap_days=EARNINGS_CALENDAR_REQUIREMENT.expiration_policy.target_gap_days,
            gap_tolerance_days=EARNINGS_CALENDAR_REQUIREMENT.expiration_policy.gap_tolerance_days,
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
        closes = _acquire_daily_closes(
            fulfillment,
            symbol,
            now,
            lookback_days=EARNINGS_CALENDAR_HISTORICAL_LOOKBACK_DAYS,
        )
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


class _SkewSnapshot(NamedTuple):
    normalized_call_skew: Decimal
    normalized_put_skew: Decimal
    call_atm_iv: Decimal
    put_atm_iv: Decimal
    call_wing_iv: Decimal
    put_wing_iv: Decimal
    chain: OptionChain
    expiration: date


def _acquire_skew_snapshot(
    fulfillment: CapabilityFulfiller,
    symbol: str,
    now: datetime,
    *,
    freshness_requirement: FreshnessRequirement = DEFAULT_FRESHNESS_REQUIREMENT,
) -> _SkewSnapshot:
    """Acquire the live quote and option chain and compute today's
    normalized call/put skew -- the one acquisition-and-computation path
    shared by the live Skew Momentum signal itself (build_live_skew_
    momentum_adapter) and by capture_skew_snapshot's own historical-
    accumulation use (SPRINT-013 S13-04D), so the two can never observe or
    compute a different value for what is supposed to be the exact same
    live snapshot.
    """
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
    return _SkewSnapshot(
        normalized_call_skew=compute_normalized_skew(call_atm_iv, call_wing_iv),
        normalized_put_skew=compute_normalized_skew(put_atm_iv, put_wing_iv),
        call_atm_iv=call_atm_iv,
        put_atm_iv=put_atm_iv,
        call_wing_iv=call_wing_iv,
        put_wing_iv=put_wing_iv,
        chain=chain,
        expiration=nearest.expiration_date,
    )


def capture_skew_snapshot(
    fulfillment: CapabilityFulfiller,
    symbol: str,
    now: datetime,
) -> HistoricalSkewObservation:
    """Acquire today's live skew snapshot for ``symbol`` and package it as
    an unrecorded HistoricalSkewObservation candidate (SPRINT-013 S13-04D).

    Pure acquisition and packaging only -- this module has no
    strategy_runtime import (screening must not depend on strategy_runtime,
    see strategy_runtime/market_data_planning.py's own docstring) and never
    decides whether, or how, this candidate may actually be recorded; only
    strategy_runtime.historical_evidence.record_prospective_skew_observation
    (the one entry point for that) may ever accept or reject it. The
    caller that actually calls it (asa/scheduled_screening.py) already
    legitimately imports strategy_runtime.

    Reuses _acquire_skew_snapshot, the exact same acquisition path the
    live Skew Momentum signal itself uses -- calling this immediately
    after that signal ran for the same symbol/now/fulfillment, as
    asa/scheduled_screening.py does, hits that fulfillment service's own
    per-cycle request cache (SPRINT-013 S13-03B) rather than issuing a
    second live provider request for data it just acquired moments ago.
    """
    snapshot = _acquire_skew_snapshot(fulfillment, symbol, now)
    return HistoricalSkewObservation(
        instrument=CanonicalInstrumentIdentity("symbol", symbol),
        call_skew=snapshot.normalized_call_skew,
        put_skew=snapshot.normalized_put_skew,
        effective_time=snapshot.chain.observed_at,
        evidence=snapshot.chain.evidence,
    )


def build_live_skew_momentum_adapter(
    symbol: str,
    fulfillment: CapabilityFulfiller,
    *,
    freshness_requirement: FreshnessRequirement = DEFAULT_FRESHNESS_REQUIREMENT,
    historical_skew_repository: HistoricalSkewHistoryReader | None = None,
) -> StrategyAdapter:
    def _run(definition: ScreeningStrategyDefinition, clock: Clock, run_id: str) -> ScreeningResult:
        now = clock.now()
        snapshot = _acquire_skew_snapshot(
            fulfillment, symbol, now, freshness_requirement=freshness_requirement
        )
        closes = _acquire_daily_closes(fulfillment, symbol, now)
        realized_vol = compute_realized_volatility(closes)
        if len(closes) < 21:
            raise StrategyAdapterError(
                ScreeningOutcomeStatus.MISSING_DATA,
                "Skew Momentum requires 21 closes for a 20-session return",
            )
        time_series_return = compute_trailing_return(closes[-21:])
        # SPRINT-013 S13-04D: real history once the repository has enough
        # of it, UNKNOWN (None) below the approved minimum or with no
        # repository at all -- never a partial-confidence proxy. Reads
        # only the most recently completed sessions already recorded
        # before this cycle; today's own not-yet-recorded snapshot is
        # never included in its own ranking.
        call_skew_zscore: Decimal | None = None
        put_skew_zscore: Decimal | None = None
        historical_valid_observations = 0
        if historical_skew_repository is not None:
            history = historical_skew_repository.history_for(
                CanonicalInstrumentIdentity("symbol", symbol),
                maximum_observations=SKEW_HISTORICAL_LOOKBACK_OBSERVATIONS,
            )
            historical_valid_observations = len(history)
            if historical_valid_observations >= SKEW_MINIMUM_VALID_OBSERVATIONS:
                _, call_zscore, _, put_zscore = compute_skew_stretch_distributions(
                    snapshot.normalized_call_skew,
                    snapshot.normalized_put_skew,
                    HistoricalSkewObservations(history),
                )
                call_skew_zscore = call_zscore
                put_skew_zscore = put_zscore
        context = build_skew_momentum_context(
            snapshot.chain,
            snapshot.expiration,
            normalized_call_skew=snapshot.normalized_call_skew,
            normalized_put_skew=snapshot.normalized_put_skew,
            call_skew_zscore=call_skew_zscore,
            put_skew_zscore=put_skew_zscore,
            historical_valid_observations=historical_valid_observations,
            call_atm_iv_minus_rv=compute_iv_realized_spread(snapshot.call_atm_iv, realized_vol),
            put_atm_iv_minus_rv=compute_iv_realized_spread(snapshot.put_atm_iv, realized_vol),
            call_wing_iv_minus_rv=compute_iv_realized_spread(snapshot.call_wing_iv, realized_vol),
            put_wing_iv_minus_rv=compute_iv_realized_spread(snapshot.put_wing_iv, realized_vol),
            call_wing_iv_minus_atm_iv=snapshot.call_wing_iv - snapshot.call_atm_iv,
            put_wing_iv_minus_atm_iv=snapshot.put_wing_iv - snapshot.put_atm_iv,
            time_series_return=time_series_return,
            # No canonical live comparison-universe/sector acquisition is
            # wired yet (S13-04C built the reusable functions; wiring them
            # here needs a cycle-wide, budget-aware multi-symbol return
            # acquisition this ticket deliberately does not build --
            # Founder policy requires UNKNOWN, never a proxy fallback).
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
            snapshot.chain.evidence,
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
    symbol: str, fulfillment: CapabilityFulfiller
) -> dict[str, StrategyAdapter]:
    """One live-driven adapter per target strategy, all bound to the same
    symbol and fulfillment service -- the live counterpart of
    screening.adapters.TARGET_STRATEGY_ADAPTERS.
    """
    return {
        strategy_id: factory(symbol, fulfillment)
        for strategy_id, factory in LIVE_ADAPTER_FACTORIES.items()
    }
