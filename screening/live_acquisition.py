"""Live market data integration (LIVE-001).

Reuses the completed Market Data Platform (market_data/) to acquire only
the canonical capability a requested strategy actually needs, through a
capability-driven, provider-independent API that respects existing
request-budget ceilings. Builds no new acquisition machinery -- every
piece here composes market_data's own ProviderFactory / ProviderRegistry /
CapabilityRegistry / RequestBudgetManager / CapabilityFulfillmentService
exactly as market_data/'s own tests already prove correct
(tests/market_data/test_sprint_005b_integration.py).

No editorial provider preference is encoded here: every enabled provider
that declares a capability serves it, in deterministic provider_id order.
Which provider *should* be preferred for a given capability is a Founder/
business decision, not this ticket's to invent.

Transport construction is injected, never hardcoded here: screening/'s own
architecture boundary (tests/architecture/test_screening_boundaries.py)
forbids importing urllib or performing network I/O directly, so a real
network transport is the caller's responsibility to supply -- this module
only orchestrates.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime

from domain import MarketCapability, MarketDataSubject
from market_data import (
    BudgetScope,
    CapabilityFulfillmentResult,
    CapabilityFulfillmentService,
    CapabilityRegistry,
    CapabilityRequest,
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
from screening.clock import Clock

PRIORITY_POLICY_VERSION = "screening-live-v1"
BUDGET_POLICY_VERSION = "screening-live-v1"


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


APPROVED_LIVE_UNIVERSE = ("AAPL", "MSFT", "NVDA", "AMD", "SPY", "QQQ")
"""The SPRINT-007 Founder-approved live validation_universe. Both
screening/cli.py's --live flag and asa/'s POST .../refresh endpoint bound
live acquisition to this same set -- neither widens it independently."""

_FIXTURE_PROVIDER_ID = "deterministic_fixture"


def live_only_config(config: MarketDataConfig) -> MarketDataConfig:
    """deterministic_fixture defaults to enabled (market_data/config.py's own
    safety default) and, being alphabetically first among enabled providers,
    would otherwise be tried before any real provider by
    CapabilityRegistry's deterministic priority order -- silently serving
    every live request from offline fixture data instead of a real
    provider. Live must mean live, so the fixture provider is always
    force-disabled here, regardless of environment configuration. Shared by
    screening/cli.py's --live flag and asa/'s live refresh endpoint -- ported
    from screening/cli.py's own original private _live_only_config, not
    reimplemented, so both callers apply exactly the same safety rule.
    """
    providers = tuple(
        replace(item, enabled=False) if item.provider_id == _FIXTURE_PROVIDER_ID else item
        for item in config.providers
    )
    return replace(config, providers=providers)


def build_capability_registry(provider_registry: ProviderRegistry) -> CapabilityRegistry:
    """Every enabled provider serves every capability it declares, in
    deterministic provider_id order.
    """
    capabilities: dict[MarketCapability, list[str]] = {}
    for provider in provider_registry.providers:
        for capability in provider.capabilities:
            capabilities.setdefault(capability, []).append(provider.provider_id)
    priorities = tuple(
        ProviderPriority(capability, tuple(sorted(provider_ids)))
        for capability, provider_ids in sorted(capabilities.items(), key=lambda item: item[0].value)
    )
    policy = ProviderPriorityPolicy(PRIORITY_POLICY_VERSION, priorities)
    return CapabilityRegistry(provider_registry, policy)


def build_request_budget_manager(
    enabled_configs: tuple[ProviderConfig, ...], clock: Clock
) -> RequestBudgetManager:
    """One RequestBudgetPolicy per enabled provider, derived from its own
    ProviderConfig.request_budget -- never widened, never invented.
    """
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


def build_fulfillment_service_with_accounting(
    config: MarketDataConfig,
    transport_factory: Callable[[str], object],
    clock: Clock,
) -> tuple[CapabilityFulfillmentService, RequestBudgetManager]:
    """Construct a fully-wired CapabilityFulfillmentService for every
    enabled provider in ``config``, and return its RequestBudgetManager
    alongside it -- CapabilityFulfillmentService itself never exposes the
    budget manager it was built with (a private, unreachable attribute), so
    a caller that needs post-hoc request accounting (asa/'s own refresh
    endpoint, API-004's "request_accounting" requirement) has no way to
    read it back from build_fulfillment_service()'s own return value alone.
    The same RequestBudgetManager instance is shared by every provider's
    dependencies, so budget consumption is tracked correctly across all of
    them, not per-provider in isolation.
    """
    enabled_configs = enabled_provider_configs(config)
    budget_manager = build_request_budget_manager(enabled_configs, clock)
    factory = _provider_factory()
    providers = tuple(
        factory.create(
            item,
            ProviderDependencies(transport_factory(item.provider_id), clock, budget_manager),
        )
        for item in enabled_configs
    )
    provider_registry = ProviderRegistry(providers)
    capability_registry = build_capability_registry(provider_registry)
    service = CapabilityFulfillmentService(provider_registry, capability_registry, budget_manager)
    return service, budget_manager


def build_fulfillment_service(
    config: MarketDataConfig,
    transport_factory: Callable[[str], object],
    clock: Clock,
) -> CapabilityFulfillmentService:
    """Construct a fully-wired CapabilityFulfillmentService for every
    enabled provider in ``config``. The same RequestBudgetManager instance
    is shared by every provider's dependencies, so budget consumption is
    tracked correctly across all of them, not per-provider in isolation.
    """
    service, _ = build_fulfillment_service_with_accounting(config, transport_factory, clock)
    return service


def acquire_capability(
    fulfillment: CapabilityFulfillmentService,
    capability: MarketCapability,
    subject: MarketDataSubject,
    *,
    effective_start: datetime,
    effective_end: datetime,
    required_fields: tuple[str, ...],
    maximum_age_seconds: int,
    required: bool = True,
) -> CapabilityFulfillmentResult:
    """Acquire exactly one capability for one subject -- the only
    acquisition surface a caller needs; provider selection, budget
    authorization, and fallback all happen inside CapabilityFulfillmentService
    itself, unchanged.
    """
    request = CapabilityRequest(
        capability, (subject,), effective_start, effective_end, required_fields, maximum_age_seconds
    )
    return fulfillment.fulfill(request, required=required)
