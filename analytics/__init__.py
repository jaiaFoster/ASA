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
from analytics.features import DerivedFeatureResult
from analytics.forward_factor import (
    FORWARD_FACTOR_ANALYTICS_COMPUTATIONS,
    FORWARD_FACTOR_ANALYTICS_REGISTRY,
    compute_days_to_expiration,
    compute_option_implied_volatility,
)
from analytics.registry import AnalyticsFeatureDefinition, AnalyticsRegistry

__all__ = [
    "FORWARD_FACTOR_ANALYTICS_COMPUTATIONS",
    "FORWARD_FACTOR_ANALYTICS_REGISTRY",
    "AnalyticsError",
    "AnalyticsFeatureDefinition",
    "AnalyticsRegistry",
    "Clock",
    "DerivedFeatureResult",
    "DuplicateFeatureRegistrationError",
    "ExpirationCandidate",
    "FeatureComputation",
    "MissingImpliedVolatilityError",
    "NoMatchingContractError",
    "UnknownFeatureIdError",
    "compute_days_to_expiration",
    "compute_feature",
    "compute_option_implied_volatility",
    "select_atm_strike",
    "select_earnings_relative_expiration_pair",
    "select_expiration_pair",
]
