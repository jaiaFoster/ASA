"""Skew Momentum Vertical migrated onto the universal runtime
(SPRINT-009/EPIC-7).

Reuses screening.adapters.TARGET_STRATEGY_REGISTRY and
screening.live_adapters.build_live_skew_momentum_adapter directly --
this sprint's own quality.preserve rule for "execution graph" means
Skew Momentum's actual financial logic (compile_strategy_graph/
execute_strategy_graph, strategies/stonk_manifests.py's own
SKEW_MOMENTUM_VERTICAL_MANIFEST) is reused unmodified, never
reimplemented. skew_momentum_adapter() is the thin translation layer
strategies_own_thesis exists for. No lifecycle: skew_momentum has never
tracked one, matching its own registered contract declaring
lifecycle=NO_LIFECYCLE.

Requirements match SPRINT-008D/PROD-004's own confirmed data-requirement
audit exactly: real_time_quote_v1 for spot price plus option_chain_v1
for the vertical structure, both actually used by the live adapter even
though screening/registry.py's own required_capabilities under-declares
this.
"""

from __future__ import annotations

from domain import MarketCapability
from screening import run_screening
from screening.adapters import TARGET_STRATEGY_REGISTRY
from screening.live_adapters import build_live_skew_momentum_adapter
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

SKEW_MOMENTUM_VERTICAL_CONTRACT = StrategyContract(
    strategy_id="skew_momentum",
    version="1.0.0",
    category="options_momentum",
    description=(
        "Delta-selected vertical with explicit liquidity inputs, debit, score, and verdict."
    ),
    requirements=(
        DataRequirement(
            RequirementCategory.MARKET_DATA, capabilities=(MarketCapability.REAL_TIME_QUOTE_V1,)
        ),
        DataRequirement(
            RequirementCategory.OPTION_DATA, capabilities=(MarketCapability.OPTION_CHAIN_V1,)
        ),
    ),
    lifecycle=NO_LIFECYCLE,
    structure=StructureKind.VERTICAL,
    outputs=(OutputKind.METRICS, OutputKind.ECONOMICS),
)


def skew_momentum_adapter(context: RuntimeContext) -> UniversalScreeningResult:
    if context.fulfillment is None:
        raise RuntimeError(
            "skew_momentum requires shared market data access "
            "(strategy_runtime.market_data_planning, EPIC-3) -- RuntimeContext.fulfillment is None"
        )
    live_adapter = build_live_skew_momentum_adapter(context.subject, context.fulfillment)
    (result,) = run_screening(
        TARGET_STRATEGY_REGISTRY,
        {"skew_momentum": live_adapter},
        context.clock,
        strategy_ids=("skew_momentum",),
    )
    observation_id = compute_observation_id(context.run_id, "skew_momentum", context.subject)
    return translate_screening_result(
        result,
        symbol=context.subject,
        observation_id=observation_id,
        opportunity_id=None,
        lifecycle_stage=None,
    )
