"""Provider-blind SPY 30-DTE put credit spread production contract (SL-02)."""

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

SPY_PUT_CREDIT_SPREAD_CONTRACT = StrategyContract(
    strategy_id="spy_put_credit_spread",
    version="1.0.0",
    category="options_premium",
    description=(
        "Option Alpha SPY put credit spread (backtest 1): 30 DTE, short 0.30 / long 0.10 "
        "delta puts, no entry filter, held to expiration."
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
    capabilities=(StrategyCapability.ECONOMICS, StrategyCapability.OPTION_STRUCTURES),
)
