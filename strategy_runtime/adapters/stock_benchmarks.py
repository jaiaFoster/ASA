"""Provider-blind stock benchmark contracts for STOCK-RUNTIME-001."""

from __future__ import annotations

from domain import MarketCapability
from strategy_runtime.contract import (
    NO_LIFECYCLE,
    DataRequirement,
    OutputKind,
    RequirementCategory,
    StrategyContract,
    StructureKind,
)

B001_CONTRACT = StrategyContract(
    strategy_id="B001",
    version="1.0.0",
    category="stock_benchmark",
    description="SPY buy-and-hold benchmark over usable current price evidence.",
    requirements=(
        DataRequirement(
            RequirementCategory.MARKET_DATA,
            capabilities=(MarketCapability.REAL_TIME_QUOTE_V1,),
        ),
    ),
    lifecycle=NO_LIFECYCLE,
    structure=StructureKind.NONE,
    outputs=(OutputKind.METRICS,),
)

B002_CONTRACT = StrategyContract(
    strategy_id="B002",
    version="1.0.0",
    category="stock_benchmark",
    description="SPY 10-month trend benchmark over completed-month adjusted closes.",
    requirements=(
        DataRequirement(
            RequirementCategory.MARKET_DATA,
            capabilities=(
                MarketCapability.REAL_TIME_QUOTE_V1,
                MarketCapability.HISTORICAL_BARS_V1,
            ),
        ),
    ),
    lifecycle=NO_LIFECYCLE,
    structure=StructureKind.NONE,
    outputs=(OutputKind.METRICS,),
)

STOCK_BENCHMARK_CONTRACTS = (B001_CONTRACT, B002_CONTRACT)
