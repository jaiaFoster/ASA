"""Derived analytics framework errors (ANALYTICS-001)."""

from __future__ import annotations


class AnalyticsError(Exception):
    """Base error for all derived analytics operations."""


class DuplicateFeatureRegistrationError(AnalyticsError):
    """A feature_id was registered more than once in an AnalyticsRegistry."""

    def __init__(self, feature_id: str) -> None:
        super().__init__(f"feature_id already registered: {feature_id!r}")
        self.feature_id = feature_id


class UnknownFeatureIdError(AnalyticsError):
    """No derived feature is registered for the requested feature_id."""

    def __init__(self, feature_id: str) -> None:
        super().__init__(f"no derived feature registered for id: {feature_id!r}")
        self.feature_id = feature_id
