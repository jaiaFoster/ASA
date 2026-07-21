"""Strategy Layer (ADR-003).

Owns deterministic Strategy evaluation and Opportunity production. Narrower
dependency rule (ADR-004, ASA-CORE-005): may depend on strategies,
indicators, facts, reconciliation, and domain — not observation or
providers, even though both sit below strategies in the general pipeline
order (Constitution Law 4: Strategies consume knowledge, they do not
gather it).
"""
from strategies.engine import (
    OPPORTUNITY_IDENTITY_NAMESPACE,
    OPPORTUNITY_IDENTITY_VERSION,
    evaluate_strategy,
    opportunity_identity,
)
from strategies.errors import (
    DuplicateStrategyRegistrationError,
    InvalidStrategyParameterError,
    MissingIndicatorInputError,
    NoContributingFactsError,
    StrategyError,
    UnknownStrategyIdError,
)
from strategies.registry import DEFAULT_REGISTRY, StrategyRegistry
from strategies.signal import StrategySignal

__all__ = [
    "DEFAULT_REGISTRY",
    "DuplicateStrategyRegistrationError",
    "InvalidStrategyParameterError",
    "MissingIndicatorInputError",
    "NoContributingFactsError",
    "OPPORTUNITY_IDENTITY_NAMESPACE",
    "OPPORTUNITY_IDENTITY_VERSION",
    "StrategyError",
    "StrategyRegistry",
    "StrategySignal",
    "UnknownStrategyIdError",
    "evaluate_strategy",
    "opportunity_identity",
]
