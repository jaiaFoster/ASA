"""Provider-blind Forward Factor production contract."""

from __future__ import annotations

from domain import MarketCapability
from strategy_runtime.contract import (
    NO_LIFECYCLE,
    DataRequirement,
    OutputKind,
    RequirementCategory,
    StrategyCapability,
    StrategyContract,
    StructureKind,
)

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
