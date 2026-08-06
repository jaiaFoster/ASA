"""Forward Factor migrated onto the universal runtime (SPRINT-009/EPIC-7).

Reuses screening.adapters.TARGET_STRATEGY_REGISTRY and
screening.live_adapters.build_live_forward_factor_adapter directly --
this sprint's own quality.preserve rule for "execution graph" means
Forward Factor's actual financial logic (compile_strategy_graph/
execute_strategy_graph, strategies/stonk_manifests.py's own
FORWARD_FACTOR_CALENDAR_MANIFEST) is reused unmodified, never
reimplemented. forward_factor_adapter() is the thin translation layer
strategies_own_thesis exists for: build the screening-style adapter for
this run's own subject and shared fulfillment service, call it once, and
translate its ScreeningResult into UniversalScreeningResult -- nothing
else. No lifecycle: forward_factor has never tracked one, matching its
own registered contract declaring lifecycle=NO_LIFECYCLE.

Requirements are mechanically aligned with the canonical manifest:
real-time quote for spot, option chains for the calendar, and earnings
calendar evidence for the confirmed-event exclusion gate.
"""

from __future__ import annotations

from domain import MarketCapability
from market_data import CapabilityFulfillmentService
from screening import run_screening
from screening.adapters import TARGET_STRATEGY_REGISTRY
from screening.live_adapters import build_live_forward_factor_adapter
from strategy_runtime.adapters._screening_bridge import translate_screening_result
from strategy_runtime.context import RuntimeContext
from strategy_runtime.contract import (
    NO_LIFECYCLE,
    DataRequirement,
    OutputKind,
    RequirementCategory,
    StrategyCapability,
    StrategyContract,
    StructureKind,
)
from strategy_runtime.result import UniversalScreeningResult, compute_observation_id

FORWARD_FACTOR_CONTRACT = StrategyContract(
    strategy_id="forward_factor",
    version="1.3.0",
    category="options_volatility",
    description=(
        "Raw-front-IV forward factor with confirmed-earnings exclusion and "
        "a common-strike, liquidity-complete delta-selected double calendar."
    ),
    requirements=(
        DataRequirement(
            RequirementCategory.MARKET_DATA, capabilities=(MarketCapability.REAL_TIME_QUOTE_V1,)
        ),
        DataRequirement(
            RequirementCategory.OPTION_DATA, capabilities=(MarketCapability.OPTION_CHAIN_V1,)
        ),
        DataRequirement(
            RequirementCategory.EARNINGS,
            capabilities=(MarketCapability.EARNINGS_CALENDAR_V1,),
        ),
    ),
    lifecycle=NO_LIFECYCLE,
    structure=StructureKind.CALENDAR,
    outputs=(OutputKind.METRICS, OutputKind.ECONOMICS),
    capabilities=(StrategyCapability.ECONOMICS, StrategyCapability.OPTION_STRUCTURES),
)


def forward_factor_adapter(
    context: RuntimeContext, fulfillment: CapabilityFulfillmentService | None
) -> UniversalScreeningResult:
    """``fulfillment`` is Forward Factor's own legacy composition binding
    (SPRINT-014 S14-PR-05) -- supplied by strategy_runtime.adapters.
    build_migrated_strategy_registry()'s own registry-construction-time
    closure, never carried on RuntimeContext (I-09). See that module's own
    docstring for this binding's owner and deletion condition.
    """
    if fulfillment is None:
        raise RuntimeError(
            "forward_factor requires shared market data access "
            "(strategy_runtime.adapters, legacy fulfillment binding) -- fulfillment is None"
        )
    live_adapter = build_live_forward_factor_adapter(
        context.subject,
        fulfillment,
        freshness_requirement=context.contract.freshness_requirement,
    )
    (result,) = run_screening(
        TARGET_STRATEGY_REGISTRY,
        {"forward_factor": live_adapter},
        context.clock,
        strategy_ids=("forward_factor",),
    )
    observation_id = compute_observation_id(context.run_id, "forward_factor", context.subject)
    return translate_screening_result(
        result,
        symbol=context.subject,
        observation_id=observation_id,
        opportunity_id=None,
        lifecycle_stage=None,
    )
