"""Provider-blind Skew Momentum Vertical production contract."""

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

SKEW_MOMENTUM_VERTICAL_CONTRACT = StrategyContract(
    strategy_id="skew_momentum",
    version="2.0.1-research",
    category="options_momentum",
    description=(
        "Two-sided skew and volatility-value gates with three-dimension momentum alignment."
    ),
    requirements=(
        DataRequirement(
            RequirementCategory.MARKET_DATA, capabilities=(MarketCapability.REAL_TIME_QUOTE_V1,)
        ),
        DataRequirement(
            RequirementCategory.OPTION_DATA, capabilities=(MarketCapability.OPTION_CHAIN_V1,)
        ),
        DataRequirement(
            RequirementCategory.MARKET_DATA,
            capabilities=(MarketCapability.HISTORICAL_BARS_V1,),
        ),
    ),
    lifecycle=NO_LIFECYCLE,
    structure=StructureKind.VERTICAL,
    outputs=(OutputKind.METRICS, OutputKind.ECONOMICS),
    capabilities=(StrategyCapability.ECONOMICS, StrategyCapability.OPTION_STRUCTURES),
)
