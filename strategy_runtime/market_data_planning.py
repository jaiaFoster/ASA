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
    ProviderMetadata,
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
from market_data.finnhub import finnhub_rolling_window_policy
from market_data.resolution import ResolutionPolicy
from market_data.rolling_window import ProviderRollingWindowTracker, RollingWindowPolicy
from market_data.tradier import tradier_rolling_window_policy
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
    enabled_configs: tuple[ProviderConfig, ...],
    clock: Clock,
    *,
    rolling_window: ProviderRollingWindowTracker | None = None,
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
    return RequestBudgetManager(policies, clock, rolling_window=rolling_window)


# Providers with no typed, declared rolling rate limit in this codebase.
# alpha_vantage: the installed key's plan tier is not knowable from
# configuration (free vs paid), so no limit is invented here (SPRINT-013
# S13-03A) -- only market_data/tradier.py and market_data/finnhub.py
# currently export a rolling_window_policy factory, sourced from their own
# ProviderMetadata.declared_limits. deterministic_fixture is not a real
# external provider and carries no quota concern.
NO_DECLARED_ROLLING_LIMIT_DIAGNOSTIC = "no_declared_rolling_limit"


def declared_rolling_window_policies(
    enabled_configs: tuple[ProviderConfig, ...],
) -> tuple[tuple[RollingWindowPolicy, ...], tuple[str, ...]]:
    """Rolling-window policies built only from each provider's own typed,
    declared limit (ProviderMetadata.declared_limits, exposed via
    tradier_rolling_window_policy()/finnhub_rolling_window_policy()) and
    the configured provider endpoint environment -- never invented, never
    inferred from external documentation. Returns (policies,
    provider_ids_without_a_declared_limit) so callers can record the safe
    no_declared_rolling_limit diagnostic instead of silently omitting
    enforcement.
    """
    policies: list[RollingWindowPolicy] = []
    undeclared: list[str] = []
    for item in enabled_configs:
        if item.provider_id == "tradier":
            policies.append(tradier_rolling_window_policy(item.endpoint_environment))
        elif item.provider_id == "finnhub":
            policies.append(finnhub_rolling_window_policy())
        else:
            undeclared.append(item.provider_id)
    return tuple(policies), tuple(undeclared)


def build_provider_rolling_window_tracker(
    config: MarketDataConfig, clock: Clock
) -> tuple[ProviderRollingWindowTracker, tuple[str, ...]]:
    """Construct exactly one ProviderRollingWindowTracker for one
    screening cycle -- callers mint this once, beside screening_cycle_id,
    never per pair and never as a module-global singleton (SPRINT-013
    S13-03A). Returns the tracker plus provider_ids with no declared
    limit, for the caller's own no_declared_rolling_limit diagnostic.
    """
    policies, undeclared = declared_rolling_window_policies(enabled_provider_configs(config))
    return ProviderRollingWindowTracker(policies, clock), undeclared


@dataclass(frozen=True, slots=True)
class SubjectMarketDataAccess:
    fulfillment: CapabilityFulfillmentService
    budget_manager: RequestBudgetManager
    # SPRINT-014 S14-PR-05A (Architect checkpoint: fourteenth review):
    # exposed so a subject-first caller can build a SubjectAcquisitionPlan's
    # own provider_metadata/resolution_policy_by_capability arguments from
    # this SAME already-built registry -- never a second, independently
    # constructed ProviderRegistry/CapabilityRegistry, and never a
    # hand-copied provider-priority list in asa/ or a strategy adapter.
    capability_registry: CapabilityRegistry
    # Architect checkpoint: fifteenth review, corrective item 3 --
    # prepare_subject_shadow_knowledge()'s own provider_metadata argument
    # (consumed by screening.subject_planning.run_subject_plan while
    # sealing) needs this subject's own real ProviderMetadata tuple.
    # CapabilityRegistry itself exposes no public metadata() of its own;
    # the ProviderRegistry already built alongside it does -- populated
    # from that exact same registry below, never reconstructed in asa/.
    provider_metadata: tuple[ProviderMetadata, ...]


def build_shared_market_data_access(
    config: MarketDataConfig,
    transport_factory: Callable[[str], object],
    clock: Clock,
    subjects: tuple[str, ...],
    *,
    budget_clock: Clock | None = None,
    rolling_window: ProviderRollingWindowTracker | None = None,
) -> dict[str, SubjectMarketDataAccess]:
    """One SubjectMarketDataAccess per subject in ``subjects`` -- never one
    shared across subjects (no request in this sprint's migration targets
    is ever shared between two different subjects, so there is no
    deduplication opportunity there to capture), and never one per
    (strategy, subject) pair.

    ``rolling_window``, when supplied, is consulted (never constructed
    here) by every subject's own RequestBudgetManager -- the caller mints
    one ProviderRollingWindowTracker per screening cycle and passes the
    same instance across every call this function makes within that
    cycle, so cross-pair provider-quota enforcement is real while each
    subject's own RequestBudgetManager stays independently pair-isolated
    (SPRINT-013 S13-03A).
    """
    enabled_configs = enabled_provider_configs(config)
    result: dict[str, SubjectMarketDataAccess] = {}
    for subject in subjects:
        budget_manager = _build_request_budget_manager(
            enabled_configs, budget_clock or clock, rolling_window=rolling_window
        )
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
        result[subject] = SubjectMarketDataAccess(
            fulfillment, budget_manager, capability_registry, provider_registry.metadata()
        )
    return result


def resolution_policy_for_capabilities(
    capability_registry: CapabilityRegistry,
    field_requirements: dict[MarketCapability, tuple[tuple[str, ...], int]],
) -> dict[MarketCapability, ResolutionPolicy]:
    """Build one ResolutionPolicy per capability in ``field_requirements``,
    reading ``provider_priority``/``policy_version`` from this subject's
    own already-built CapabilityRegistry -- never a second, hand-copied
    provider-priority list (SPRINT-014 S14-PR-05A, Architect checkpoint:
    fourteenth review, "provider metadata and resolution policies must be
    constructed from existing market-data configuration/registry
    ownership").

    ``field_requirements`` supplies only what a market-data registry
    cannot know on its own -- each capability's own required_fields and
    freshness_threshold_seconds for a *sealed, resolved* observation of
    that capability (not necessarily every field any one raw demand for it
    requests: strategies/earnings_calendar_planning.py's own
    earnings_calendar_resolved_field_requirements() is the one example
    today, documenting why OPTION_CHAIN_V1 uses its chain demand's own
    ("contracts",) here, never the expiration-discovery demand's
    ("expirations",) -- market_data.capability_coalescing.
    reduce_option_chain_results() always seals the combined OptionChain,
    never the discovery-only ExpirationCollection, so a resolution policy
    checking for "expirations" here would never be satisfiable). This
    function itself never branches on or imports a strategy identity --
    ``field_requirements`` is caller-supplied data, not a lookup.
    """
    policy = capability_registry.policy
    return {
        capability: ResolutionPolicy(
            policy.policy_version,
            policy.for_capability(capability).provider_ids,
            freshness_threshold_seconds,
            required_fields,
        )
        for capability, (
            required_fields,
            freshness_threshold_seconds,
        ) in field_requirements.items()
    }
