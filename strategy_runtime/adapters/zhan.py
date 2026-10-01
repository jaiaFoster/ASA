"""Provider-blind production contract for the Zhan cross-sectional strategy."""

from domain import MarketCapability
from strategies.zhan_manifest import STRATEGY_ID, STRATEGY_VERSION
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

ZHAN_CONTRACT = StrategyContract(
    strategy_id=STRATEGY_ID,
    version=STRATEGY_VERSION,
    category="cross_sectional_options",
    description="Monthly delta-neutral call writing sorted on negative log stock price.",
    requirements=(
        DataRequirement(
            RequirementCategory.MARKET_DATA,
            (
                MarketCapability.HISTORICAL_BARS_V1,
                MarketCapability.TRADING_CALENDAR_V1,
                MarketCapability.RATE_OBSERVATION_V1,
                MarketCapability.SECURITY_MASTER_V1,
            ),
        ),
        DataRequirement(
            RequirementCategory.OPTION_DATA,
            (MarketCapability.OPTION_CHAIN_V1,),
        ),
    ),
    lifecycle=LifecycleDeclaration(
        LifecycleModel.OPPORTUNITY,
        ("identified", "entered", "closed"),
        "monthly_cross_sectional_portfolio",
    ),
    structure=StructureKind.CUSTOM,
    outputs=(OutputKind.METRICS, OutputKind.ECONOMICS, OutputKind.LIFECYCLE),
    capabilities=(
        StrategyCapability.LIFECYCLE,
        StrategyCapability.HISTORY,
        StrategyCapability.ECONOMICS,
        StrategyCapability.OPTION_STRUCTURES,
        StrategyCapability.MULTIPLE_RESULTS,
    ),
)
