"""Shared data planning (SPRINT-009/EPIC-3).

Builds one market_data.CapabilityFulfillmentService (and its own
RequestBudgetManager) per subject for one run -- shared by every strategy
that evaluates that subject within the run, rather than one fresh instance
per (strategy, subject) pair the way asa/api/screening_routes.py and
asa/scheduled_screening.py both currently build it (SPRINT-008/SPRINT-008D).
Sharing one instance is the entire mechanism: CapabilityFulfillmentService
already memoizes an identical CapabilityRequest within its own lifetime
(market_data/fulfillment.py's own _results dict) -- this module does not
reimplement that caching, it only makes sure strategies actually share one
instance long enough for it to matter, which they never have before this
ticket. Provider fallback and budget enforcement are entirely
market_data.fulfillment's own, unmodified.

Deliberately built from market_data/'s own public exports only, not
imported from screening/live_acquisition.py's near-identical wiring
(build_fulfillment_service_with_accounting) -- strategy_runtime is meant
to be more foundational than screening (screening becomes one of its
consumers once EPIC-7 migrates), so importing the other way around would
be backwards, and screening/live_acquisition.py is already live,
already-tested production code (POST /api/v1/screening/*/refresh) this
ticket has no reason to touch. The small amount of provider-wiring logic
duplicated here is a deliberate, documented tradeoff, not an oversight --
EPIC-7's own migration is the natural point to fully unify them, once
screening/'s own callers are moving onto this runtime anyway.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from domain import MarketCapability
from market_data import (
    CapabilityFulfillmentService,
    CapabilityRegistry,
    MarketDataConfig,
    ProviderConfig,
    ProviderDependencies,
    ProviderFactory,
    ProviderPriority,
    ProviderPriorityPolicy,
    ProviderRegistry,
    RequestBudgetManager,
    RequestBudgetPolicy,
    alpha_vantage_provider_registration,
    finnhub_provider_registration,
    fixture_provider_registration,
    tradier_provider_registration,
)
from market_data.budget import BudgetScope
from strategy_runtime.clock import Clock

PRIORITY_POLICY_VERSION = "strategy-runtime-shared-plan-v1"
BUDGET_POLICY_VERSION = "strategy-runtime-shared-plan-v1"


def _provider_factory() -> ProviderFactory:
    return ProviderFactory(
        (
            tradier_provider_registration(),
            finnhub_provider_registration(),
            alpha_vantage_provider_registration(),
            fixture_provider_registration(),
        )
    )


def enabled_provider_configs(config: MarketDataConfig) -> tuple[ProviderConfig, ...]:
    return tuple(item for item in config.providers if item.enabled)


def _build_capability_registry(provider_registry: ProviderRegistry) -> CapabilityRegistry:
    """Every enabled provider serves every capability it declares, in
    deterministic provider_id order -- no editorial preference encoded
    here, matching screening/live_acquisition.py's own identical policy.
    """
    capabilities: dict[MarketCapability, list[str]] = {}
    for provider in provider_registry.providers:
        for capability in provider.capabilities:
            capabilities.setdefault(capability, []).append(provider.provider_id)
    priorities = tuple(
        ProviderPriority(capability, tuple(sorted(provider_ids)))
        for capability, provider_ids in sorted(
            capabilities.items(), key=lambda item: item[0].value
        )
    )
    policy = ProviderPriorityPolicy(PRIORITY_POLICY_VERSION, priorities)
    return CapabilityRegistry(provider_registry, policy)


def _build_request_budget_manager(
    enabled_configs: tuple[ProviderConfig, ...], clock: Clock
) -> RequestBudgetManager:
    policies = tuple(
        RequestBudgetPolicy(
            item.provider_id,
            BudgetScope.RUNTIME,
            item.request_budget.max_requests_per_run,
            item.request_budget.burst_limit,
            item.retry.max_retries,
            BUDGET_POLICY_VERSION,
        )
        for item in enabled_configs
    )
    return RequestBudgetManager(policies, clock)


@dataclass(frozen=True, slots=True)
class SubjectMarketDataAccess:
    fulfillment: CapabilityFulfillmentService
    budget_manager: RequestBudgetManager


def build_shared_market_data_access(
    config: MarketDataConfig,
    transport_factory: Callable[[str], object],
    clock: Clock,
    subjects: tuple[str, ...],
) -> dict[str, SubjectMarketDataAccess]:
    """One SubjectMarketDataAccess per subject in ``subjects`` -- never one
    shared across subjects (no request in this sprint's migration targets
    is ever shared between two different subjects, so there is no
    deduplication opportunity there to capture), and never one per
    (strategy, subject) pair.
    """
    enabled_configs = enabled_provider_configs(config)
    result: dict[str, SubjectMarketDataAccess] = {}
    for subject in subjects:
        budget_manager = _build_request_budget_manager(enabled_configs, clock)
        factory = _provider_factory()
        providers = tuple(
            factory.create(
                item,
                ProviderDependencies(transport_factory(item.provider_id), clock, budget_manager),
            )
            for item in enabled_configs
        )
        provider_registry = ProviderRegistry(providers)
        capability_registry = _build_capability_registry(provider_registry)
        fulfillment = CapabilityFulfillmentService(
            provider_registry, capability_registry, budget_manager
        )
        result[subject] = SubjectMarketDataAccess(fulfillment, budget_manager)
    return result
