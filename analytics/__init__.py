"""Canonical derived analytics framework (SPRINT-007, ANALYTICS-001).

A reusable, provider-neutral subsystem that derives canonical financial
features from already-canonical market data. Implements no strategy logic,
never references providers directly, and never duplicates market data
acquisition -- it only computes and canonically records derived values from
whatever canonical inputs a caller supplies.
"""

from __future__ import annotations

from analytics.atm_selection import select_atm_strike
from analytics.clock import Clock
from analytics.derived_facts import (
    DERIVED_FACT_DEFINITIONS,
    DERIVED_FACT_REGISTRY,
    compute_bid_ask_spread_ratio,
    compute_cross_sectional_momentum,
    compute_days_to_earnings,
    compute_earnings_inside_trade_window,
    compute_expiration_gap_days,
    compute_expiration_gap_distance,
    compute_forward_factor,
    compute_historical_percentile,
    compute_historical_zscore,
    compute_implied_forward_volatility,
    compute_iv_realized_spread,
    compute_momentum_dimensions,
    compute_no_confirmed_earnings_through_expiration,
    compute_normalized_skew,
    compute_open_interest_quality,
    compute_option_volume_band,
    compute_sector_relative_momentum,
    compute_skew_stretch_distributions,
)
from analytics.engine import FeatureComputation, compute_feature
from analytics.errors import (
    AnalyticsError,
    DuplicateFeatureRegistrationError,
    MissingImpliedVolatilityError,
    NoMatchingContractError,
    UnknownFeatureIdError,
)
from analytics.expiration_selection import (
    ExpirationCandidate,
    select_earnings_relative_expiration_pair,
    select_expiration_pair,
)
from analytics.features import (
    DerivedFact,
    DerivedFactQualityStatus,
    DerivedFactSet,
    DerivedFactValue,
)
from analytics.forward_factor import (
    FORWARD_FACTOR_ANALYTICS_COMPUTATIONS,
    FORWARD_FACTOR_ANALYTICS_REGISTRY,
    compute_days_to_expiration,
    compute_option_implied_volatility,
)
from analytics.option_selection import select_canonical_contract
from analytics.realized_volatility import (
    InsufficientPriceHistoryError,
    compute_log_returns,
    compute_realized_volatility,
    compute_trailing_return,
)
from analytics.registry import AnalyticsFeatureDefinition, AnalyticsRegistry

__all__ = [
    "FORWARD_FACTOR_ANALYTICS_COMPUTATIONS",
    "FORWARD_FACTOR_ANALYTICS_REGISTRY",
    "AnalyticsError",
    "AnalyticsFeatureDefinition",
    "AnalyticsRegistry",
    "Clock",
    "DerivedFact",
    "DERIVED_FACT_DEFINITIONS",
    "DERIVED_FACT_REGISTRY",
    "DerivedFactQualityStatus",
    "DerivedFactSet",
    "DerivedFactValue",
    "DuplicateFeatureRegistrationError",
    "ExpirationCandidate",
    "FeatureComputation",
    "InsufficientPriceHistoryError",
    "MissingImpliedVolatilityError",
    "NoMatchingContractError",
    "UnknownFeatureIdError",
    "compute_days_to_expiration",
    "compute_cross_sectional_momentum",
    "compute_days_to_earnings",
    "compute_earnings_inside_trade_window",
    "compute_expiration_gap_days",
    "compute_expiration_gap_distance",
    "compute_feature",
    "compute_forward_factor",
    "compute_historical_percentile",
    "compute_historical_zscore",
    "compute_implied_forward_volatility",
    "compute_iv_realized_spread",
    "compute_log_returns",
    "compute_option_implied_volatility",
    "compute_option_volume_band",
    "compute_open_interest_quality",
    "compute_realized_volatility",
    "compute_sector_relative_momentum",
    "compute_skew_stretch_distributions",
    "compute_trailing_return",
    "compute_bid_ask_spread_ratio",
    "compute_momentum_dimensions",
    "compute_normalized_skew",
    "compute_no_confirmed_earnings_through_expiration",
    "select_atm_strike",
    "select_canonical_contract",
    "select_earnings_relative_expiration_pair",
    "select_expiration_pair",
]
