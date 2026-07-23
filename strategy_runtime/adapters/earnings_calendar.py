"""Earnings Calendar migrated onto the universal runtime
(SPRINT-009/EPIC-7) -- the lifecycle-tracking migration target EPIC-5's
generic engine (strategy_runtime.lifecycle) is proven against.

Reuses screening.adapters.TARGET_STRATEGY_REGISTRY and
screening.live_adapters.build_live_earnings_calendar_adapter directly --
this sprint's own quality.preserve rule for "execution graph" means
Earnings Calendar's actual financial logic is reused unmodified, never
reimplemented.

Lifecycle scope, deliberately narrower than a full state machine and
recorded as such, not silently: screening.live_adapters's own earnings
calendar adapter is itself stateless (one evaluation, no memory of prior
observations) -- it has never tracked lifecycle, and this ticket's own
scope is migrating that existing evaluation logic onto the new runtime,
not adding brand-new stateful behavior to screening/'s own execution
graph (which quality.preserve rules out touching). What this migration
adds is real, not simulated: every successful observation is assigned a
real opportunity_id (strategy_runtime.lifecycle.compute_opportunity_id())
and a real lifecycle_stage, validated against this contract's own
declared states (strategy_runtime.lifecycle.validate_lifecycle_stage()) --
proving EPIC-5's engine is genuinely usable by a real strategy, which is
this ticket's own acceptance criterion. The stage assigned reflects only
the current observation's own outcome (PASS -> "confirmed", NO_SIGNAL ->
"watching") -- a true multi-observation transition function (e.g. "was
watching, earnings just got confirmed, now assign 'confirmed'") requires
reading prior persisted history through EPIC-8's own
ObservationHistoryRepository, which is production-integration work for
whichever ticket actually wires a live repository into a live adapter --
properly scoped to EPIC-9 or a SPRINT-010 follow-up, not this one.

Opportunity identity is also deliberately simplified: (strategy_id,
symbol) only, treating "the AAPL earnings calendar opportunity" as one
evolving identity per symbol rather than distinguishing separate
earnings cycles (Q1 vs Q2, etc.) as separate opportunities. Distinguishing
cycles requires the confirmed earnings date itself, which
screening.live_adapters's own ScreeningResult does not currently expose
in an extractable, structured field -- exposing it would mean changing
that existing, preserved execution graph's own output shape, out of
this ticket's scope. Recorded as a known limitation and a concrete
recommendation for a follow-up sprint, not silently accepted.
"""

from __future__ import annotations

from domain import MarketCapability
from screening import run_screening
from screening.adapters import TARGET_STRATEGY_REGISTRY
from screening.live_adapters import build_live_earnings_calendar_adapter
from screening.results import ScreeningOutcomeStatus
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
from strategy_runtime.lifecycle import compute_opportunity_id, validate_lifecycle_stage
from strategy_runtime.result import UniversalScreeningResult, compute_observation_id

EARNINGS_CALENDAR_CONTRACT = StrategyContract(
    strategy_id="earnings_calendar",
    version="1.0.0",
    category="options_earnings",
    description=(
        "Confirmed earnings window with a nearest-common-strike calendar and explicit debit."
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


def earnings_calendar_adapter(context: RuntimeContext) -> UniversalScreeningResult:
    if context.fulfillment is None:
        raise RuntimeError(
            "earnings_calendar requires shared market data access "
            "(strategy_runtime.market_data_planning, EPIC-3) -- RuntimeContext.fulfillment is None"
        )
    live_adapter = build_live_earnings_calendar_adapter(context.subject, context.fulfillment)
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
