"""Provider-blind Cboe BXM production contract."""

from domain import MarketCapability
from strategies.bxm_manifest import STRATEGY_ID, STRATEGY_VERSION
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

BXM_CONTRACT = StrategyContract(
    strategy_id=STRATEGY_ID,
    version=STRATEGY_VERSION,
    category="index_buywrite",
    description="Cboe monthly S&P 500 BuyWrite methodology.",
    requirements=(
        DataRequirement(
            RequirementCategory.MARKET_DATA,
            (
                MarketCapability.REAL_TIME_QUOTE_V1,
                MarketCapability.TRADING_CALENDAR_V1,
                MarketCapability.INDEX_DIVIDEND_POINTS_V1,
            ),
        ),
        DataRequirement(
            RequirementCategory.OPTION_DATA,
            (
                MarketCapability.OPTION_CHAIN_V1,
                MarketCapability.OPTION_TRADE_TAPE_V1,
                MarketCapability.INDEX_SETTLEMENT_VALUE_V1,
            ),
        ),
    ),
    lifecycle=LifecycleDeclaration(
        LifecycleModel.OPPORTUNITY, ("identified", "entered", "expired"), "monthly_buywrite"
    ),
    structure=StructureKind.CUSTOM,
    outputs=(OutputKind.METRICS, OutputKind.ECONOMICS, OutputKind.LIFECYCLE),
    capabilities=(
        StrategyCapability.LIFECYCLE,
        StrategyCapability.HISTORY,
        StrategyCapability.ECONOMICS,
        StrategyCapability.OPTION_STRUCTURES,
    ),
)
