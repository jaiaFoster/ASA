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


class MissingImpliedVolatilityError(AnalyticsError):
    """A matched option contract has no implied_volatility value."""

    def __init__(self, expiration: str, strike: str) -> None:
        super().__init__(
            f"no implied_volatility on the contract matching expiration={expiration!r} "
            f"strike={strike!r}"
        )


class NoMatchingContractError(AnalyticsError):
    """No contract in the chain matched the requested expiration/strike/type."""

    def __init__(self, expiration: str, strike: str) -> None:
        super().__init__(
            f"no contract found matching expiration={expiration!r} strike={strike!r}"
        )
