"""Provider-blind Heston production contract."""

from domain import MarketCapability
from strategies.heston_manifest import STRATEGY_ID, STRATEGY_VERSION
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

HESTON_CONTRACT = StrategyContract(
    strategy_id=STRATEGY_ID,
    version=STRATEGY_VERSION,
    category="cross_sectional_options",
    description="Monthly low-cost zero-delta straddle momentum decile portfolio.",
    requirements=(
        DataRequirement(RequirementCategory.MARKET_DATA, (MarketCapability.TRADING_CALENDAR_V1,)),
        DataRequirement(
            RequirementCategory.OPTION_DATA,
            (MarketCapability.OPTION_CHAIN_V1, MarketCapability.HISTORICAL_OPTION_PANEL_V1),
        ),
    ),
    lifecycle=LifecycleDeclaration(
        LifecycleModel.OPPORTUNITY,
        ("identified", "entered", "closed"),
        "monthly_cross_sectional_straddle_portfolio",
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
