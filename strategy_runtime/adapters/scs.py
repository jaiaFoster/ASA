"""Provider-blind SCS production contract."""

from domain import MarketCapability
from strategies.scs_manifest import STRATEGY_ID, STRATEGY_VERSION
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

SCS_CONTRACT = StrategyContract(
    strategy_id=STRATEGY_ID,
    version=STRATEGY_VERSION,
    category="index_short_volatility",
    description="Monthly short near-maturity ATM standard SPX straddle.",
    requirements=(
        DataRequirement(
            RequirementCategory.MARKET_DATA,
            (
                MarketCapability.REAL_TIME_QUOTE_V1,
                MarketCapability.TRADING_CALENDAR_V1,
                MarketCapability.RATE_OBSERVATION_V1,
            ),
        ),
        DataRequirement(
            RequirementCategory.OPTION_DATA,
            (MarketCapability.OPTION_CHAIN_V1, MarketCapability.INDEX_SETTLEMENT_VALUE_V1),
        ),
    ),
    lifecycle=LifecycleDeclaration(
        LifecycleModel.OPPORTUNITY, ("identified", "entered", "expired"), "monthly_short_straddle"
    ),
    structure=StructureKind.STRADDLE,
    outputs=(OutputKind.METRICS, OutputKind.ECONOMICS, OutputKind.LIFECYCLE),
    capabilities=(
        StrategyCapability.LIFECYCLE,
        StrategyCapability.HISTORY,
        StrategyCapability.ECONOMICS,
        StrategyCapability.OPTION_STRUCTURES,
    ),
)
