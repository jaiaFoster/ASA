"""Earnings Calendar migrated onto the universal runtime
(SPRINT-009/EPIC-7) -- cut over to the subject-first evidence path by
SPRINT-014 S14-PR-05, the lifecycle-tracking migration target EPIC-5's
generic engine (strategy_runtime.lifecycle) is proven against.

This adapter performs zero acquisition of any kind: it reads only
context.sealed_evidence (strategy_runtime.evidence.SubjectSealedEvidence),
assembled by the composition root before this adapter ever runs
(screening.sealed_earnings_calendar.acquire_sealed_earnings_calendar_evidence,
called from asa/scheduled_screening.py) -- never a CapabilityFulfillment
Service, never a provider, never a transport (I-09). Financial logic
(compile_strategy_graph/execute_strategy_graph over
strategies/stonk_manifests.py's own EARNINGS_CALENDAR_MANIFEST, and every
compute_* function the sealed evidence's own derived facts were built
from) is unchanged and reused verbatim -- this ticket's own quality.
preserve rule.

Lifecycle scope, deliberately narrower than a full state machine and
recorded as such, not silently: the underlying execution graph is
stateless (one evaluation, no memory of prior observations) -- it has
never tracked lifecycle, and this ticket's own scope is migrating
existing evaluation logic onto the subject-first path, not adding
brand-new stateful behavior to the execution graph. What this adapter
adds is real, not simulated: every successful observation is assigned a
real opportunity_id (strategy_runtime.lifecycle.compute_opportunity_id())
and a real lifecycle_stage, validated against this contract's own
declared states.

Opportunity identity is deliberately simplified: (strategy_id, symbol)
only, unchanged from the pre-cutover behavior -- not a regression
introduced by this ticket.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

from analytics.derived_fact_materialization import derived_fact_id
from domain import EarningsEvent, ExpirationCycle, MarketCapability, OptionChain
from market_data import CapabilityFulfillmentService
from screening import run_screening
from screening.adapters import TARGET_STRATEGY_REGISTRY
from screening.clock import Clock as ScreeningClock
from screening.context_builders import build_earnings_calendar_context
from screening.earnings_calendar_fact_ids import (
    BACK_DAYS_TO_EXPIRATION_FACT,
    BACK_EXPIRATION_DATE_FACT,
    FRONT_DAYS_TO_EXPIRATION_FACT,
    FRONT_EXPIRATION_DATE_FACT,
    IV_REALIZED_RICHNESS_FACT,
    TARGET_STRIKE_FACT,
    TERM_STRUCTURE_RICHNESS_FACT,
)
from screening.live_adapters import (
    _COMPONENT_REGISTRY,
    _live_result,
    build_live_earnings_calendar_adapter,
)
from screening.live_context import _is_monthly_expiration
from screening.registry import ScreeningStrategyDefinition
from screening.results import ScreeningOutcomeStatus, ScreeningResult
from screening.runner import StrategyAdapter, StrategyAdapterError
from strategies import compile_strategy_graph, execute_strategy_graph
from strategies.stonk_manifests import EARNINGS_CALENDAR_MANIFEST
from strategy_runtime.adapters._screening_bridge import translate_screening_result
from strategy_runtime.context import RuntimeContext
from strategy_runtime.contract import (
    DataRequirement,
    LifecycleDeclaration,
    LifecycleModel,
    OutputKind,
    RequirementCategory,
    StrategyCapability,
    StrategyContract,
    StructureKind,
)
from strategy_runtime.evidence import SubjectSealedEvidence
from strategy_runtime.lifecycle import compute_opportunity_id, validate_lifecycle_stage
from strategy_runtime.result import UniversalScreeningResult, compute_observation_id

EARNINGS_CALENDAR_CONTRACT = StrategyContract(
    strategy_id="earnings_calendar",
    version="1.2.0",
    category="options_earnings",
    description=(
        "Confirmed earnings calendar targeting a 30-day expiration gap with liquidity evidence."
    ),
    requirements=(
        DataRequirement(
            RequirementCategory.MARKET_DATA, capabilities=(MarketCapability.REAL_TIME_QUOTE_V1,)
        ),
        DataRequirement(
            RequirementCategory.OPTION_DATA, capabilities=(MarketCapability.OPTION_CHAIN_V1,)
        ),
        DataRequirement(
            RequirementCategory.EARNINGS, capabilities=(MarketCapability.EARNINGS_CALENDAR_V1,)
        ),
        DataRequirement(
            RequirementCategory.MARKET_DATA,
            capabilities=(MarketCapability.HISTORICAL_BARS_V1,),
        ),
    ),
    lifecycle=LifecycleDeclaration(
        LifecycleModel.OPPORTUNITY,
        supported_states=("watching", "confirmed"),
        observation_type="earnings_calendar_spread",
    ),
    structure=StructureKind.CALENDAR,
    outputs=(OutputKind.METRICS, OutputKind.ECONOMICS, OutputKind.LIFECYCLE),
    capabilities=(
        StrategyCapability.LIFECYCLE,
        StrategyCapability.ECONOMICS,
        StrategyCapability.OPTION_STRUCTURES,
    ),
)

_STAGE_BY_OUTCOME = {
    ScreeningOutcomeStatus.PASS: "confirmed",
    ScreeningOutcomeStatus.NO_SIGNAL: "watching",
}


def _reconstruct_expiration_cycle(
    expiration_date: date, days_to_expiration: int, *, as_of: date, evidence: tuple[object, ...]
) -> ExpirationCycle:
    """monthly/weekly are never read by any strategy component or context
    builder (confirmed by grep across strategies/stonk_components.py and
    screening/context_builders.py) -- graph output never depends on which
    value they carry. ExpirationCycle.__post_init__ still requires exactly
    the same classification the pre-cutover path computes (a bare False,
    False pair fails its "requires a monthly or weekly classification"
    invariant), so the exact same third-Friday check screening/live_context.py
    already uses to build every other ExpirationCycle in this codebase is
    reused here rather than reinvented. evidence/as_of are
    provenance/traceability fields, unread by any comparison or filtering
    logic in the graph.
    """
    monthly = _is_monthly_expiration(expiration_date)
    return ExpirationCycle(
        expiration_date=expiration_date,
        days_to_expiration=days_to_expiration,
        monthly=monthly,
        weekly=not monthly,
        as_of=as_of,
        evidence=evidence,  # type: ignore[arg-type]
    )


def _sealed_earnings_calendar_adapter(
    symbol: str, sealed_evidence: SubjectSealedEvidence
) -> StrategyAdapter:
    def _run(
        definition: ScreeningStrategyDefinition, clock: ScreeningClock, run_id: str
    ) -> ScreeningResult:
        snapshot = sealed_evidence.snapshot
        as_of = snapshot.as_of.date()
        resolution_by_capability = {item.capability: item for item in snapshot.resolution_results}

        chain_resolution = resolution_by_capability.get(MarketCapability.OPTION_CHAIN_V1)
        event_resolution = resolution_by_capability.get(MarketCapability.EARNINGS_CALENDAR_V1)
        if (
            chain_resolution is None
            or chain_resolution.selected_observation is None
            or event_resolution is None
            or event_resolution.selected_observation is None
        ):
            raise StrategyAdapterError(
                ScreeningOutcomeStatus.MISSING_DATA,
                f"sealed evidence for {symbol} has no resolved option chain or earnings event",
            )
        chain = cast(OptionChain, chain_resolution.selected_observation.value)
        event = cast(EarningsEvent, event_resolution.selected_observation.value)

        def _fact(feature_id: str) -> object | None:
            fact_id = derived_fact_id(feature_id, symbol, snapshot.snapshot_digest)
            try:
                return sealed_evidence.derived_facts.get(fact_id).value
            except KeyError:
                return None

        front_date = _fact(FRONT_EXPIRATION_DATE_FACT)
        front_dte = _fact(FRONT_DAYS_TO_EXPIRATION_FACT)
        back_date = _fact(BACK_EXPIRATION_DATE_FACT)
        back_dte = _fact(BACK_DAYS_TO_EXPIRATION_FACT)
        target_strike = _fact(TARGET_STRIKE_FACT)
        term_richness = _fact(TERM_STRUCTURE_RICHNESS_FACT)
        iv_rv_richness = _fact(IV_REALIZED_RICHNESS_FACT)
        if (
            front_date is None
            or front_dte is None
            or back_date is None
            or back_dte is None
            or target_strike is None
            or term_richness is None
            or iv_rv_richness is None
        ):
            raise StrategyAdapterError(
                ScreeningOutcomeStatus.MISSING_DATA,
                f"sealed evidence for {symbol} has no expiration selection or richness facts "
                "-- no expiration pair spans its earnings date within policy, or an "
                "at-the-money contract had no implied_volatility",
            )

        front = _reconstruct_expiration_cycle(
            cast(date, front_date), cast(int, front_dte), as_of=as_of, evidence=chain.evidence
        )
        back = _reconstruct_expiration_cycle(
            cast(date, back_date), cast(int, back_dte), as_of=as_of, evidence=chain.evidence
        )
        context = build_earnings_calendar_context(
            chain,
            event,
            front,
            back,
            as_of,
            target_strike=cast(Decimal, target_strike),
            term_structure_richness=cast(Decimal, term_richness),
            iv_realized_volatility_richness=cast(Decimal, iv_rv_richness),
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


def earnings_calendar_adapter(context: RuntimeContext) -> UniversalScreeningResult:
    if context.sealed_evidence is None:
        raise RuntimeError(
            "earnings_calendar requires sealed subject-first evidence "
            "(screening.sealed_earnings_calendar, SPRINT-014 S14-PR-05) -- "
            "RuntimeContext.sealed_evidence is None"
        )
    adapter = _sealed_earnings_calendar_adapter(context.subject, context.sealed_evidence)
    (result,) = run_screening(
        TARGET_STRATEGY_REGISTRY,
        {"earnings_calendar": adapter},
        context.clock,
        strategy_ids=("earnings_calendar",),
    )
    observation_id = compute_observation_id(context.run_id, "earnings_calendar", context.subject)

    stage = _STAGE_BY_OUTCOME.get(result.outcome_status)
    opportunity_id = None
    if stage is not None:
        validate_lifecycle_stage(EARNINGS_CALENDAR_CONTRACT, stage)
        opportunity_id = compute_opportunity_id("earnings_calendar", context.subject)

    return translate_screening_result(
        result,
        symbol=context.subject,
        observation_id=observation_id,
        opportunity_id=opportunity_id,
        lifecycle_stage=stage,
    )


def legacy_earnings_calendar_adapter(
    context: RuntimeContext, fulfillment: CapabilityFulfillmentService | None
) -> UniversalScreeningResult:
    """The pre-cutover imperative acquisition path (build_live_earnings_
    calendar_adapter, screening.live_adapters -- untouched by S14-PR-05),
    kept reachable only as S14-PR-05's own required rollback switch
    (asa.scheduled_screening.run_scheduled_refresh's
    earnings_calendar_cutover_enabled=False). Two-argument, matching
    forward_factor_adapter's/skew_momentum_adapter's own legacy-binding
    shape, NOT registered by default -- build_migrated_strategy_registry()
    only wires this in when the caller explicitly disables the cutover.

    Deletion condition: delete this function together with
    screening.live_adapters.build_live_earnings_calendar_adapter and
    every other superseded acquisition path, in S14-PR-07 -- not before.
    """
    if fulfillment is None:
        raise RuntimeError(
            "earnings_calendar (legacy path) requires shared market data access "
            "(strategy_runtime.market_data_planning, EPIC-3) -- fulfillment is None"
        )
    live_adapter = build_live_earnings_calendar_adapter(
        context.subject,
        fulfillment,
        freshness_requirement=context.contract.freshness_requirement,
    )
    (result,) = run_screening(
        TARGET_STRATEGY_REGISTRY,
        {"earnings_calendar": live_adapter},
        context.clock,
        strategy_ids=("earnings_calendar",),
    )
    observation_id = compute_observation_id(context.run_id, "earnings_calendar", context.subject)

    stage = _STAGE_BY_OUTCOME.get(result.outcome_status)
    opportunity_id = None
    if stage is not None:
        validate_lifecycle_stage(EARNINGS_CALENDAR_CONTRACT, stage)
        opportunity_id = compute_opportunity_id("earnings_calendar", context.subject)

    return translate_screening_result(
        result,
        symbol=context.subject,
        observation_id=observation_id,
        opportunity_id=opportunity_id,
        lifecycle_stage=stage,
    )
