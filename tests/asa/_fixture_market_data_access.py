"""Shared fixture-backed replacement for
strategy_runtime.market_data_planning.build_shared_market_data_access(),
reusing tests/screening/test_live_adapters.py's own proven
MultiExpirationFixtureProvider (SPRINT-014 S14-PR-05A, Architect
checkpoint: seventeenth review: "reuse the already-established
multi-capability fixture access and inject/monkeypatch it at
build_shared_market_data_access() so the real root -> plan -> preparation
-> legacy adapter -> shadow comparator executes end-to-end").

Not a test module itself (no ``test_`` prefix, not collected by pytest) --
a support module both tests/asa/test_scheduled_screening.py and
tests/asa/test_screening_refresh_route.py import from, so a real
asa/scheduled_screening.py / asa/api/screening_routes.py invocation runs
against a genuine, multi-capability, multi-expiration
CapabilityFulfillmentService with zero network and zero new HTTP fixture
work -- never a hand-scripted Tradier/Finnhub HTTP transport.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from market_data import (
    CapabilityFulfillmentService,
    FixtureScenario,
    ProviderDependencies,
    load_market_data_config,
)
from market_data.attempts import InMemoryAcquisitionAttemptRepository
from market_data.registry import CapabilityRegistry, ProviderRegistry
from screening.live_acquisition import build_capability_registry, build_request_budget_manager
from strategy_runtime.adapters import (
    build_migrated_shadow_registry,
    migrated_shadow_capability_reducers,
    migrated_shadow_resolution_policy,
)
from strategy_runtime.clock import Clock
from strategy_runtime.market_data_planning import SubjectMarketDataAccess
from strategy_runtime.orchestration import (
    build_subject_acquisition_access,
    prepare_subject_shadow_knowledge,
)
from tests.screening.test_live_adapters import MultiExpirationFixtureProvider

# Generous enough that a single frozen clock reading for every request in
# one cycle/invocation never collides on RequestBudgetPolicy's own burst
# key, matching tests/strategy_runtime/test_orchestration.py's own
# established rationale for this exact fixture provider.
BURST_LIMIT = 30


@dataclass(frozen=True, slots=True)
class _FrozenClock:
    """A truly frozen clock -- the same reading on every call. Both the
    provider-dependency clock and the strategy/plan-level ``now`` must be
    this exact same frozen instant: every observation's own recorded_time
    must never exceed the sealed snapshot's own as_of (MarketSnapshot's
    own invariant), which only holds for certain when nothing here reads
    a fresh, independently-advancing wall clock mid-resolution.
    """

    value: datetime

    def now(self) -> datetime:
        return self.value


def build_fixture_access(
    clock: Clock, scenario: FixtureScenario
) -> tuple[SubjectMarketDataAccess, CapabilityRegistry]:
    config = load_market_data_config({})
    (fixture_config,) = tuple(item for item in config.providers if item.enabled)
    fixture_config = dataclasses.replace(
        fixture_config,
        request_budget=dataclasses.replace(fixture_config.request_budget, burst_limit=BURST_LIMIT),
    )
    budget_manager = build_request_budget_manager((fixture_config,), clock)
    fixture_provider = MultiExpirationFixtureProvider(
        fixture_config, ProviderDependencies(object(), clock, budget_manager), scenario
    )
    provider_registry = ProviderRegistry((fixture_provider,))
    capability_registry = build_capability_registry(provider_registry)
    fulfillment = CapabilityFulfillmentService(
        provider_registry, capability_registry, budget_manager
    )
    access = SubjectMarketDataAccess(
        fulfillment, budget_manager, capability_registry, provider_registry.metadata()
    )
    return access, capability_registry


def build_fixture_market_data_access_factory(
    scenario_by_symbol: dict[str, FixtureScenario] | None = None,
) -> Callable[..., dict[str, SubjectMarketDataAccess]]:
    """A drop-in replacement matching
    strategy_runtime.market_data_planning.build_shared_market_data_access's
    own signature exactly -- monkeypatch it in at the production-root
    module's own imported name (``asa.scheduled_screening.
    build_shared_market_data_access`` / ``asa.api.screening_routes.
    build_shared_market_data_access``) so the caller's own production-root
    code runs completely unmodified against this fixture instead.

    One fresh CapabilityFulfillmentService (and its own budget manager)
    per requested subject, never shared cross-symbol -- matching the real
    function's own established invariant. ``scenario_by_symbol`` lets a
    test inject a deliberate per-symbol FixtureScenario (e.g. a forced
    capability failure); a symbol with no entry gets the fully successful
    default scenario.
    """
    scenarios = scenario_by_symbol or {}

    def _build(
        _config: Any,
        _transport_factory: Any,
        clock: Clock,
        subjects: tuple[str, ...],
        *,
        rolling_window: Any = None,
    ) -> dict[str, SubjectMarketDataAccess]:
        result: dict[str, SubjectMarketDataAccess] = {}
        for symbol in subjects:
            access, _capability_registry = build_fixture_access(
                clock, scenarios.get(symbol, FixtureScenario())
            )
            result[symbol] = access
        return result

    return _build


def shadow_alone_call_count(
    symbol: str, now: datetime, scenario: FixtureScenario | None = None
) -> int:
    """The exact number of provider calls Earnings Calendar's own
    subject-first shadow preparation makes in complete isolation, against
    a FRESH fixture-backed access built the same way
    build_fixture_market_data_access_factory's own replacement would --
    the correct baseline a real production-root request's own total
    request_count must equal for "legacy execution added zero calls
    beyond what the shared plan already resolved" to be a true,
    apples-to-apples comparison (Architect checkpoint: seventeenth
    review). Legacy Earnings' own acquisition style is not a valid
    baseline for this comparison: unlike subject-first preparation, which
    unconditionally resolves every one of its four bootstrap demands
    every time, legacy short-circuits on its own first failure -- a
    real, pre-existing, unrelated difference that would make a
    legacy-alone baseline read as a false "extra calls" gap.

    Uses one internally-built _FrozenClock(now) for everything -- the
    provider-dependency clock, the plan's own clock, and preparation's own
    ``now`` -- never a caller-supplied, potentially-advancing clock.
    """
    clock = _FrozenClock(now)
    access, capability_registry = build_fixture_access(clock, scenario or FixtureScenario())
    acquisition = build_subject_acquisition_access(
        symbol,
        access.fulfillment,
        attempt_repository=InMemoryAcquisitionAttemptRepository(),
        plan_id=f"shadow-alone-baseline:{symbol}",
        clock=clock,
    )
    prepare_subject_shadow_knowledge(
        acquisition.plan,
        now,
        build_migrated_shadow_registry(now),
        subject=symbol,
        provider_metadata=access.provider_metadata,
        resolution_policy_by_capability=migrated_shadow_resolution_policy(capability_registry),
        capability_reducer_by_capability=migrated_shadow_capability_reducers(),
    )
    return len(access.budget_manager.accounting)
