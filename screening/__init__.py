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
from screening.live_acquisition import (
    APPROVED_LIVE_UNIVERSE,
    EARNINGS_CALENDAR_UNIVERSE,
    acquire_capability,
    build_capability_registry,
    build_fulfillment_service,
    build_fulfillment_service_with_accounting,
    build_request_budget_manager,
    enabled_provider_configs,
    live_only_config,
)
from screening.live_adapters import build_live_adapters
from screening.registry import (
    ScreeningRegistry,
    ScreeningStrategyDefinition,
)
from screening.results import ScreeningOutcomeStatus, ScreeningResult, bounded_failure_detail
from screening.runner import StrategyAdapter, StrategyAdapterError, run_screening

__all__ = [
    "APPROVED_LIVE_UNIVERSE",
    "EARNINGS_CALENDAR_UNIVERSE",
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
    "acquire_capability",
    "bounded_failure_detail",
    "build_capability_registry",
    "build_fulfillment_service",
    "build_fulfillment_service_with_accounting",
    "build_live_adapters",
    "build_request_budget_manager",
    "enabled_provider_configs",
    "live_only_config",
    "run_screening",
]
