"""Screening framework (SPRINT-006).

Registers, executes, isolates, and ranks existing ASA analytical strategies
through one common bounded contract, without changing their trading logic.
"""

from __future__ import annotations

from screening.adapters import TARGET_STRATEGY_ADAPTERS, TARGET_STRATEGY_REGISTRY
from screening.clock import Clock
from screening.errors import (
    DuplicateScreeningRegistrationError,
    ScreeningError,
    UnknownScreeningStrategyIdError,
)
from screening.registry import ScreeningRegistry, ScreeningStrategyDefinition
from screening.results import ScreeningOutcomeStatus, ScreeningResult, bounded_failure_detail
from screening.runner import StrategyAdapter, StrategyAdapterError, run_screening

__all__ = [
    "TARGET_STRATEGY_ADAPTERS",
    "TARGET_STRATEGY_REGISTRY",
    "Clock",
    "DuplicateScreeningRegistrationError",
    "ScreeningError",
    "ScreeningOutcomeStatus",
    "ScreeningRegistry",
    "ScreeningResult",
    "ScreeningStrategyDefinition",
    "StrategyAdapter",
    "StrategyAdapterError",
    "UnknownScreeningStrategyIdError",
    "bounded_failure_detail",
    "run_screening",
]
