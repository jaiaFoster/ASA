"""S001 declaration; cohort composition is provider-blind and strategy-owned."""

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

S001_CONTRACT = StrategyContract(
    strategy_id="S001",
    version="1.0.0",
    category="sector_momentum",
    description="Point-in-time sector momentum with a completed-month trend gate.",
    requirements=(
        DataRequirement(
            RequirementCategory.MARKET_DATA,
            capabilities=(MarketCapability.HISTORICAL_BARS_V1,),
        ),
        DataRequirement(
            RequirementCategory.CUSTOM,
            identifier="trailing_12m_total_return@1.0.0",
        ),
        DataRequirement(
            RequirementCategory.CUSTOM,
            identifier="sma_10m_completed_months@1.0.0",
        ),
    ),
    lifecycle=NO_LIFECYCLE,
    structure=StructureKind.NONE,
    outputs=(OutputKind.METRICS,),
)
