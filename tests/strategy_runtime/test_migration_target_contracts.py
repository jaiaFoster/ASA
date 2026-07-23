"""SPRINT-009/EPIC-2: draft StrategyContract declarations for the three
migration-target strategies (forward_factor, skew_momentum_vertical,
earnings_calendar).

These prove the contract schema is sufficient to describe all three real
strategies EPIC-7 will eventually migrate -- EPIC-2's own acceptance
criterion. They are drafts, not production wiring: nothing here is
registered with any runtime (EPIC-1 does not exist yet), and none of it
replaces screening/registry.py's existing ScreeningStrategyDefinition,
which continues to drive the currently-shipped screening/ and asa/ surface
unchanged until EPIC-7 actually migrates each strategy.

Capability requirements are drawn directly from
screening/live_adapters.py's real live-acquisition code (confirmed during
SPRINT-008D/PROD-004's own data-requirement audit,
project/reports/SPRINT-008D-PROVIDER-VALIDATION.md): every one of the
three strategies acquires a real-time quote for spot price *and* an
option chain, even though screening/registry.py's own
required_capabilities today under-declares this (PROD-004 recommended,
but did not implement, fixing that declaration -- this draft reflects the
corrected, complete requirement set from the start).

earnings_calendar's lifecycle states below are a provisional placeholder
(watching -> confirmed -> active -> closed, with expired as a terminal
state a calendar spread can reach without ever becoming active) -- a
defensible first draft, not yet reconciled against the mature Stonk
Calendar implementation's own actual state vocabulary
(/Users/jaiafoster/Claude/stonk/app/services/). That reconciliation is
EPIC-5's own job (Universal Opportunity Model); this test only proves the
*shape* (LifecycleModel.OPPORTUNITY with named states and an
observation_type) is sufficient to describe calendar's lifecycle, not
that these exact five states are the final, authoritative set.
"""

from __future__ import annotations

from domain import MarketCapability
from strategy_runtime import (
    NO_LIFECYCLE,
    DataRequirement,
    LifecycleDeclaration,
    LifecycleModel,
    OutputKind,
    RequirementCategory,
    StrategyContract,
    StructureKind,
)

FORWARD_FACTOR_CONTRACT = StrategyContract(
    strategy_id="forward_factor",
    version="1.1.0",
    category="options_volatility",
    description="Source-qualified forward factor with a delta-selected double calendar.",
    requirements=(
        DataRequirement(
            RequirementCategory.MARKET_DATA, capabilities=(MarketCapability.REAL_TIME_QUOTE_V1,)
        ),
        DataRequirement(
            RequirementCategory.OPTION_DATA, capabilities=(MarketCapability.OPTION_CHAIN_V1,)
        ),
    ),
    lifecycle=NO_LIFECYCLE,
    structure=StructureKind.CALENDAR,
    outputs=(OutputKind.METRICS, OutputKind.ECONOMICS),
)

SKEW_MOMENTUM_VERTICAL_CONTRACT = StrategyContract(
    strategy_id="skew_momentum",
    version="1.0.0",
    category="options_momentum",
    description=(
        "Delta-selected vertical with explicit liquidity inputs, debit, score, and verdict."
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
)

EARNINGS_CALENDAR_CONTRACT = StrategyContract(
    strategy_id="earnings_calendar",
    version="1.0.0",
    category="options_earnings",
    description=(
        "Confirmed earnings window with a nearest-common-strike calendar and explicit debit."
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
    ),
    lifecycle=LifecycleDeclaration(
        LifecycleModel.OPPORTUNITY,
        supported_states=("watching", "confirmed", "active", "closed", "expired"),
        observation_type="earnings_calendar_spread",
    ),
    structure=StructureKind.CALENDAR,
    outputs=(OutputKind.METRICS, OutputKind.ECONOMICS, OutputKind.LIFECYCLE),
)


def test_forward_factor_contract_is_valid() -> None:
    assert FORWARD_FACTOR_CONTRACT.structure is StructureKind.CALENDAR
    assert FORWARD_FACTOR_CONTRACT.required_capabilities() == (
        MarketCapability.OPTION_CHAIN_V1,
        MarketCapability.REAL_TIME_QUOTE_V1,
    )


def test_skew_momentum_vertical_contract_is_valid() -> None:
    assert SKEW_MOMENTUM_VERTICAL_CONTRACT.structure is StructureKind.VERTICAL
    assert SKEW_MOMENTUM_VERTICAL_CONTRACT.required_capabilities() == (
        MarketCapability.OPTION_CHAIN_V1,
        MarketCapability.REAL_TIME_QUOTE_V1,
    )


def test_earnings_calendar_contract_is_valid() -> None:
    assert EARNINGS_CALENDAR_CONTRACT.lifecycle.lifecycle_model is LifecycleModel.OPPORTUNITY
    assert OutputKind.LIFECYCLE in EARNINGS_CALENDAR_CONTRACT.outputs
    assert EARNINGS_CALENDAR_CONTRACT.required_capabilities() == (
        MarketCapability.EARNINGS_CALENDAR_V1,
        MarketCapability.OPTION_CHAIN_V1,
        MarketCapability.REAL_TIME_QUOTE_V1,
    )


def test_all_three_contracts_share_the_same_market_data_and_option_data_requirements() -> None:
    # Confirms EPIC-3's own shared-data-planning premise at the contract
    # level: these three strategies genuinely do overlap in what they
    # need, which is exactly what makes cross-strategy request
    # deduplication worth building.
    for contract in (
        FORWARD_FACTOR_CONTRACT,
        SKEW_MOMENTUM_VERTICAL_CONTRACT,
        EARNINGS_CALENDAR_CONTRACT,
    ):
        assert MarketCapability.REAL_TIME_QUOTE_V1 in contract.required_capabilities()
        assert MarketCapability.OPTION_CHAIN_V1 in contract.required_capabilities()
