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

Requirements match SPRINT-008D/PROD-004's own confirmed data-requirement
audit exactly (project/reports/SPRINT-008D-PROVIDER-VALIDATION.md):
real_time_quote_v1 for spot price plus option_chain_v1 for the calendar
structure, both actually used by the live adapter even though
screening/registry.py's own required_capabilities under-declares this
(PROD-004 recommended, but did not implement, fixing that declaration --
this contract reflects the corrected, complete requirement set).
"""

from __future__ import annotations

from domain import MarketCapability
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
    StrategyContract,
    StructureKind,
)
from strategy_runtime.result import UniversalScreeningResult, compute_observation_id

FORWARD_FACTOR_CONTRACT = StrategyContract(
    strategy_id="forward_factor",
    version="1.1.0",
    category="options_volatility",
    description="Source-qualified forward factor with a delta-selected double calendar.",
    requirements=(
        DataRequirement(
            RequirementCategory.MARKET_DATA, capabilities=(MarketCapability.REAL_TIME_QUOTE_V1,)
        ),
        DataRequirement(
            RequirementCategory.OPTION_DATA, capabilities=(MarketCapability.OPTION_CHAIN_V1,)
        ),
    ),
    lifecycle=NO_LIFECYCLE,
    structure=StructureKind.CALENDAR,
    outputs=(OutputKind.METRICS, OutputKind.ECONOMICS),
)


def forward_factor_adapter(context: RuntimeContext) -> UniversalScreeningResult:
    if context.fulfillment is None:
        raise RuntimeError(
            "forward_factor requires shared market data access "
            "(strategy_runtime.market_data_planning, EPIC-3) -- RuntimeContext.fulfillment is None"
        )
    live_adapter = build_live_forward_factor_adapter(context.subject, context.fulfillment)
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
