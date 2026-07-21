"""Derived Indicator Layer (ADR-006).

Owns shared, reusable indicator calculations, deriving Indicators from
Canonical Facts only. Narrower dependency rule (ADR-004, ASA-CORE-004):
may depend on indicators, facts, reconciliation, and domain — not
observation or providers, even though both sit below indicators in the
general pipeline order.
"""
from indicators.engine import (
    INDICATOR_IDENTITY_NAMESPACE,
    INDICATOR_IDENTITY_VERSION,
    compute_indicator,
    indicator_identity,
)
from indicators.errors import (
    DuplicateIndicatorError,
    DuplicateIndicatorRegistrationError,
    InconsistentFactGroupError,
    InconsistentIndicatorGroupError,
    IndicatorCalculationError,
    IndicatorError,
    IndicatorIdentityCollisionError,
    IndicatorNotFoundError,
    IndicatorRepositoryError,
    InsufficientDataError,
    InvalidIndicatorParameterError,
    NonMonotonicIndicatorVersionError,
    UnknownIndicatorTypeError,
)
from indicators.registry import DEFAULT_REGISTRY, IndicatorRegistry
from indicators.repository import InMemoryIndicatorRepository

__all__ = [
    "DEFAULT_REGISTRY",
    "DuplicateIndicatorError",
    "DuplicateIndicatorRegistrationError",
    "INDICATOR_IDENTITY_NAMESPACE",
    "INDICATOR_IDENTITY_VERSION",
    "InconsistentFactGroupError",
    "InconsistentIndicatorGroupError",
    "IndicatorCalculationError",
    "IndicatorError",
    "IndicatorIdentityCollisionError",
    "IndicatorNotFoundError",
    "IndicatorRegistry",
    "IndicatorRepositoryError",
    "InMemoryIndicatorRepository",
    "InsufficientDataError",
    "InvalidIndicatorParameterError",
    "NonMonotonicIndicatorVersionError",
    "UnknownIndicatorTypeError",
    "compute_indicator",
    "indicator_identity",
]
