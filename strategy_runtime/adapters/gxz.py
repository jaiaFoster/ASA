"""Provider-blind production contract for the GXZ event-volatility strategy."""

from domain import MarketCapability
from strategies.gxz_manifest import GXZ_STRATEGY_ID, GXZ_STRATEGY_VERSION
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

GXZ_CONTRACT = StrategyContract(
    strategy_id=GXZ_STRATEGY_ID,
    version=GXZ_STRATEGY_VERSION,
    category="event_volatility",
    description="GXZ delta-neutral ATM straddles entered three sessions before earnings.",
    requirements=(
        DataRequirement(
            RequirementCategory.MARKET_DATA,
            (MarketCapability.REAL_TIME_QUOTE_V1, MarketCapability.TRADING_CALENDAR_V1),
        ),
        DataRequirement(RequirementCategory.EARNINGS, (MarketCapability.EARNINGS_CALENDAR_V1,)),
        DataRequirement(RequirementCategory.OPTION_DATA, (MarketCapability.OPTION_CHAIN_V1,)),
    ),
    lifecycle=LifecycleDeclaration(
        LifecycleModel.OPPORTUNITY,
        ("identified", "entered", "expired"),
        "earnings_straddle",
    ),
    structure=StructureKind.STRADDLE,
    outputs=(OutputKind.METRICS, OutputKind.ECONOMICS, OutputKind.LIFECYCLE),
    capabilities=(
        StrategyCapability.LIFECYCLE,
        StrategyCapability.HISTORY,
        StrategyCapability.ECONOMICS,
        StrategyCapability.OPTION_STRUCTURES,
        StrategyCapability.MULTIPLE_RESULTS,
    ),
)
