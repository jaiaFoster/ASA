"""Provider-blind Earnings Calendar production contract."""

from __future__ import annotations

from domain import MarketCapability
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

EARNINGS_CALENDAR_CONTRACT = StrategyContract(
    strategy_id="earnings_calendar",
    version="1.2.0",
    category="options_earnings",
    description=(
        "Confirmed earnings calendar targeting a 30-day expiration gap with liquidity evidence."
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
        DataRequirement(
            RequirementCategory.MARKET_DATA,
            capabilities=(MarketCapability.HISTORICAL_BARS_V1,),
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
