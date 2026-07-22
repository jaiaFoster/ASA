"""Canonical derived analytics framework (SPRINT-007, ANALYTICS-001).

A reusable, provider-neutral subsystem that derives canonical financial
features from already-canonical market data. Implements no strategy logic,
never references providers directly, and never duplicates market data
acquisition -- it only computes and canonically records derived values from
whatever canonical inputs a caller supplies.
"""

from __future__ import annotations

from analytics.clock import Clock
from analytics.engine import FeatureComputation, compute_feature
from analytics.errors import (
    AnalyticsError,
    DuplicateFeatureRegistrationError,
    UnknownFeatureIdError,
)
from analytics.features import DerivedFeatureResult
from analytics.registry import AnalyticsFeatureDefinition, AnalyticsRegistry

__all__ = [
    "AnalyticsError",
    "AnalyticsFeatureDefinition",
    "AnalyticsRegistry",
    "Clock",
    "DerivedFeatureResult",
    "DuplicateFeatureRegistrationError",
    "FeatureComputation",
    "UnknownFeatureIdError",
    "compute_feature",
]
