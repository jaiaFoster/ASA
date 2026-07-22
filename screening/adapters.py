"""Target strategy adapters (SCREEN-004).

Connects each ready target strategy (Forward Factor, Earnings Calendar,
Skew Momentum -- confirmed present and fully implemented by SCREEN-001) to
the screening framework, without changing any threshold, formula, entry
logic, or scoring. Every adapter here is pure composition glue: it builds
the manifest's required execution context from fixed, deterministic
screening/fixtures.py data, executes the existing, unmodified manifest via
strategies.compile_strategy_graph/execute_strategy_graph, and wraps the
strategy-native verdict/score/evidence into a canonical ScreeningResult --
it re-implements none of the strategy's own logic.

A strategy's own PASS/WATCH/FAIL verdict is always preserved verbatim in
ScreeningResult.signal_classification. outcome_status is a coarser,
framework-level view: PASS/WATCH both mean "worth reporting" (PASS);
FAIL means nothing actionable for this run (NO_SIGNAL). No exception
handling is done here -- an unexpected failure propagates to the runner's
own STRATEGY_EXCEPTION isolation boundary (SCREEN-003), which is exactly
where that isolation is supposed to happen.
"""

from __future__ import annotations

from decimal import Decimal

from domain import ExpirationCollection, MarketCapability, OptionType
from screening import fixtures
from screening.clock import Clock
from screening.registry import ScreeningRegistry, ScreeningStrategyDefinition
from screening.results import ScreeningOutcomeStatus, ScreeningResult
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
from strategies.stonk_components import (
    D,
    DATE,
    DECIMAL_LIST,
    EARNINGS_EVENT,
    EXPIRATION_COLLECTION,
    EXPIRATION_CYCLE,
    OPTION_CHAIN,
    OPTION_CONTRACT,
)
from strategies.type_system import ComponentValues, StrategyTypeReference, TypedValue

_COMPONENT_REGISTRY = build_plugin_registry(CORE_COMPONENTS, STONK_STRATEGY_PLUGINS)
_SUBJECT_IDENTITY = f"figi:figi-{fixtures.SAFE_SYMBOL}"

_NON_FAIL_VERDICTS = frozenset({"PASS", "WATCH"})


def _context(**items: tuple[StrategyTypeReference, object]) -> ComponentValues:
    return ComponentValues(
        tuple((name, TypedValue(type_ref, value)) for name, (type_ref, value) in items.items())
    )


def _outcome_status_for_verdict(verdict: str) -> ScreeningOutcomeStatus:
    return (
        ScreeningOutcomeStatus.PASS
        if verdict in _NON_FAIL_VERDICTS
        else ScreeningOutcomeStatus.NO_SIGNAL
    )


def run_forward_factor(
    definition: ScreeningStrategyDefinition, clock: Clock, run_id: str
) -> ScreeningResult:
    chain = fixtures.forward_factor_chain()
    expirations = fixtures.forward_factor_expirations()
    context = _context(
        **{
            "expiration_select.expirations": (EXPIRATION_COLLECTION, expirations),
            "double_calendar.chain": (OPTION_CHAIN, chain),
            "forward_iv.front_iv": (D, Decimal("0.48")),
            "forward_iv.back_iv": (D, Decimal("0.4548992562461861547567860943472296")),
            "forward_iv.front_dte": (D, 61),
            "forward_iv.back_dte": (D, 91),
            "factor.front_ex_earnings_iv": (D, Decimal("0.48")),
        }
    )
    graph = compile_strategy_graph(FORWARD_FACTOR_CALENDAR_MANIFEST, _COMPONENT_REGISTRY)
    result = execute_strategy_graph(graph, context)
    verdict = str(result.outputs.get("verdict").value)
    score = result.outputs.get("forward_factor").value
    return ScreeningResult(
        run_id,
        definition.strategy_id,
        definition.strategy_version,
        _SUBJECT_IDENTITY,
        clock.now(),
        _outcome_status_for_verdict(verdict),
        verdict,
        score if isinstance(score, Decimal) else None,
        fixtures.EVIDENCE,
        fixtures.EVIDENCE,
        None,
        None,
    )


def run_earnings_calendar(
    definition: ScreeningStrategyDefinition, clock: Clock, run_id: str
) -> ScreeningResult:
    front, back = fixtures.earnings_calendar_expirations()
    event = fixtures.earnings_calendar_event()
    chain = fixtures.earnings_calendar_chain()
    context = _context(
        **{
            "event_window.event": (EARNINGS_EVENT, event),
            "event_window.front": (EXPIRATION_CYCLE, front),
            "event_window.back": (EXPIRATION_CYCLE, back),
            "expiration_select.expirations": (
                EXPIRATION_COLLECTION,
                ExpirationCollection(fixtures.AS_OF_DATE, (back, front)),
            ),
            "expiration_select.event": (EARNINGS_EVENT, event),
            "calendar.chain": (OPTION_CHAIN, chain),
            "calendar.target_strike": (D, Decimal("100")),
            "score.values": (DECIMAL_LIST, (Decimal("80"), Decimal("60"))),
            "score.weights": (DECIMAL_LIST, (Decimal("3"), Decimal("1"))),
        }
    )
    graph = compile_strategy_graph(EARNINGS_CALENDAR_MANIFEST, _COMPONENT_REGISTRY)
    result = execute_strategy_graph(graph, context)
    verdict = str(result.outputs.get("verdict").value)
    score = result.outputs.get("score").value
    return ScreeningResult(
        run_id,
        definition.strategy_id,
        definition.strategy_version,
        _SUBJECT_IDENTITY,
        clock.now(),
        _outcome_status_for_verdict(verdict),
        verdict,
        score if isinstance(score, Decimal) else None,
        fixtures.EVIDENCE,
        fixtures.EVIDENCE,
        None,
        None,
    )


def run_skew_momentum(
    definition: ScreeningStrategyDefinition, clock: Clock, run_id: str
) -> ScreeningResult:
    chain = fixtures.skew_momentum_chain()
    (call_contract,) = chain.find(
        expiration=fixtures.SKEW_EXPIRATION,
        strike=Decimal("100"),
        option_type=OptionType.CALL,
    )
    context = _context(
        **{
            "vertical.chain": (OPTION_CHAIN, chain),
            "vertical.expiration": (DATE, fixtures.SKEW_EXPIRATION),
            "liquidity.contract": (OPTION_CONTRACT, call_contract),
            "score.values": (DECIMAL_LIST, (Decimal("80"), Decimal("70"))),
            "score.weights": (DECIMAL_LIST, (Decimal("2"), Decimal("1"))),
        }
    )
    graph = compile_strategy_graph(SKEW_MOMENTUM_VERTICAL_MANIFEST, _COMPONENT_REGISTRY)
    result = execute_strategy_graph(graph, context)
    verdict = str(result.outputs.get("verdict").value)
    score = result.outputs.get("score").value
    return ScreeningResult(
        run_id,
        definition.strategy_id,
        definition.strategy_version,
        _SUBJECT_IDENTITY,
        clock.now(),
        _outcome_status_for_verdict(verdict),
        verdict,
        score if isinstance(score, Decimal) else None,
        fixtures.EVIDENCE,
        fixtures.EVIDENCE,
        None,
        None,
    )


TARGET_STRATEGY_DEFINITIONS: tuple[ScreeningStrategyDefinition, ...] = (
    ScreeningStrategyDefinition(
        "forward_factor",
        FORWARD_FACTOR_CALENDAR_MANIFEST.strategy_version,
        FORWARD_FACTOR_CALENDAR_MANIFEST.manifest_id,
        (MarketCapability.OPTION_CHAIN_V1,),
    ),
    ScreeningStrategyDefinition(
        "earnings_calendar",
        EARNINGS_CALENDAR_MANIFEST.strategy_version,
        EARNINGS_CALENDAR_MANIFEST.manifest_id,
        (MarketCapability.EARNINGS_CALENDAR_V1, MarketCapability.OPTION_CHAIN_V1),
    ),
    ScreeningStrategyDefinition(
        "skew_momentum",
        SKEW_MOMENTUM_VERTICAL_MANIFEST.strategy_version,
        SKEW_MOMENTUM_VERTICAL_MANIFEST.manifest_id,
        (MarketCapability.OPTION_CHAIN_V1,),
    ),
)

TARGET_STRATEGY_REGISTRY = ScreeningRegistry(TARGET_STRATEGY_DEFINITIONS)

TARGET_STRATEGY_ADAPTERS = {
    "forward_factor": run_forward_factor,
    "earnings_calendar": run_earnings_calendar,
    "skew_momentum": run_skew_momentum,
}
