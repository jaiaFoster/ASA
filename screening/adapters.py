"""Target strategy adapters (SCREEN-004, updated by ANALYTICS-003).

Connects each ready target strategy (Forward Factor, Earnings Calendar,
Skew Momentum -- confirmed present and fully implemented by SCREEN-001) to
the screening framework, without changing any threshold, formula, entry
logic, or scoring. Every adapter here is pure composition glue: it builds
the manifest's required execution context (via screening.context_builders,
using screening/fixtures.py data), executes the existing, unmodified
manifest via strategies.compile_strategy_graph/execute_strategy_graph, and
wraps the strategy-native verdict/score/evidence into a canonical
ScreeningResult -- it re-implements none of the strategy's own logic.

Forward Factor's context now comes from real analytics computation
(ANALYTICS-002) instead of a hardcoded external implied-volatility
constant -- see screening/context_builders.py.

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

from domain import MarketCapability, OptionType
from screening import fixtures
from screening.clock import Clock
from screening.context_builders import (
    build_earnings_calendar_context,
    build_forward_factor_context,
    build_skew_momentum_context,
)
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

_COMPONENT_REGISTRY = build_plugin_registry(CORE_COMPONENTS, STONK_STRATEGY_PLUGINS)
_SUBJECT_IDENTITY = f"figi:figi-{fixtures.SAFE_SYMBOL}"

_NON_FAIL_VERDICTS = frozenset({"PASS", "WATCH"})


def _outcome_status_for_verdict(verdict: str) -> ScreeningOutcomeStatus:
    return (
        ScreeningOutcomeStatus.PASS
        if verdict in _NON_FAIL_VERDICTS
        else ScreeningOutcomeStatus.NO_SIGNAL
    )


def _result_from_graph_execution(
    definition: ScreeningStrategyDefinition,
    clock: Clock,
    run_id: str,
    verdict: object,
    score: object,
) -> ScreeningResult:
    verdict_text = str(verdict)
    return ScreeningResult(
        run_id,
        definition.strategy_id,
        definition.strategy_version,
        _SUBJECT_IDENTITY,
        clock.now(),
        _outcome_status_for_verdict(verdict_text),
        verdict_text,
        score if isinstance(score, Decimal) else None,
        fixtures.EVIDENCE,
        fixtures.EVIDENCE,
        None,
        None,
    )


def run_forward_factor(
    definition: ScreeningStrategyDefinition, clock: Clock, run_id: str
) -> ScreeningResult:
    chain = fixtures.forward_factor_chain()
    expirations = fixtures.forward_factor_expirations()
    context = build_forward_factor_context(
        chain, expirations.cycles, fixtures.AS_OF_DATE, strike=Decimal("105")
    )
    graph = compile_strategy_graph(FORWARD_FACTOR_CALENDAR_MANIFEST, _COMPONENT_REGISTRY)
    result = execute_strategy_graph(graph, context)
    return _result_from_graph_execution(
        definition,
        clock,
        run_id,
        result.outputs.get("verdict").value,
        result.outputs.get("forward_factor").value,
    )


def run_earnings_calendar(
    definition: ScreeningStrategyDefinition, clock: Clock, run_id: str
) -> ScreeningResult:
    front, back = fixtures.earnings_calendar_expirations()
    event = fixtures.earnings_calendar_event()
    chain = fixtures.earnings_calendar_chain()
    context = build_earnings_calendar_context(
        chain, event, front, back, fixtures.AS_OF_DATE, target_strike=Decimal("100")
    )
    graph = compile_strategy_graph(EARNINGS_CALENDAR_MANIFEST, _COMPONENT_REGISTRY)
    result = execute_strategy_graph(graph, context)
    return _result_from_graph_execution(
        definition,
        clock,
        run_id,
        result.outputs.get("verdict").value,
        result.outputs.get("score").value,
    )


def run_skew_momentum(
    definition: ScreeningStrategyDefinition, clock: Clock, run_id: str
) -> ScreeningResult:
    chain = fixtures.skew_momentum_chain()
    context = build_skew_momentum_context(
        chain, fixtures.SKEW_EXPIRATION, strike=Decimal("100"), option_type=OptionType.CALL
    )
    graph = compile_strategy_graph(SKEW_MOMENTUM_VERTICAL_MANIFEST, _COMPONENT_REGISTRY)
    result = execute_strategy_graph(graph, context)
    return _result_from_graph_execution(
        definition,
        clock,
        run_id,
        result.outputs.get("verdict").value,
        result.outputs.get("score").value,
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
