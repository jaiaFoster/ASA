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
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from domain import (
    EarningsEvent,
    MarketDataSubject,
    OHLCVBar,
    OptionChain,
    Quote,
)
from domain.references import EvidenceReference
from market_data import (
    CapabilityFulfillmentService,
    CapabilityRequest,
    FixtureScenario,
    ProviderDependencies,
    ProviderFetchResult,
    RequestBudgetAuthorization,
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


class WatchEarningsFixtureProvider(MultiExpirationFixtureProvider):
    """MultiExpirationFixtureProvider with its front/back-month contracts'
    own implied_volatility retuned so Earnings Calendar's own real
    DTE-window selection (front 7-21 DTE, back 22-75 DTE, ~30-day target
    gap -- the base fixture's own day-10/day-40 pair is the only
    unambiguous match for those windows) lands in WATCH's own score band
    instead of PASS's (Architect checkpoint: eighteenth review, "WATCH:
    not yet exercised through either real production root").

    Confirmed empirically against the real live adapter's own scoring
    formula, not assumed from reading the code alone: the base fixture's
    own front=0.55/back=0.50 scores 73.75 (PASS, >= pass_threshold=70);
    front=0.50/back=0.48 scores 67.00 (WATCH, in [watch_threshold=55,
    pass_threshold=70)) -- mirrors this session's own established
    strategy_runtime/adapters/earnings_calendar_subject_first.py pinned
    WATCH fixture pattern (front=0.33/back=0.24 there), just re-derived
    for THIS fixture's own real multi-capability acquisition shape rather
    than a hand-built snapshot.
    """

    _FRONT_DAYS_OUT = 10
    _BACK_DAYS_OUT = 40
    _FRONT_IV = Decimal("0.50")
    _BACK_IV = Decimal("0.48")

    def _value(
        self,
        subject: MarketDataSubject,
        address: str,
        observed_at: datetime,
        evidence: tuple[EvidenceReference, ...],
    ) -> Quote | OHLCVBar | OptionChain | EarningsEvent:
        value: Quote | OHLCVBar | OptionChain | EarningsEvent = super()._value(  # type: ignore[no-untyped-call]
            subject, address, observed_at, evidence
        )
        if not isinstance(value, OptionChain):
            return value
        front_expiration = observed_at.date() + timedelta(days=self._FRONT_DAYS_OUT)
        back_expiration = observed_at.date() + timedelta(days=self._BACK_DAYS_OUT)
        contracts = tuple(
            dataclasses.replace(contract, implied_volatility=self._FRONT_IV)
            if contract.expiration == front_expiration
            else (
                dataclasses.replace(contract, implied_volatility=self._BACK_IV)
                if contract.expiration == back_expiration
                else contract
            )
            for contract in value.contracts
        )
        return dataclasses.replace(value, contracts=contracts)


class DuplicateEarningsFixtureProvider(MultiExpirationFixtureProvider):
    """Reproduces Finnhub returning competing events for one subject."""

    def fetch(
        self, request: CapabilityRequest, budget: RequestBudgetAuthorization
    ) -> ProviderFetchResult:
        fetched: ProviderFetchResult = super().fetch(  # type: ignore[no-untyped-call]
            request, budget
        )
        if request.capability.value != "earnings_calendar_v1" or fetched.error is not None:
            return fetched
        return dataclasses.replace(
            fetched,
            observations=(fetched.observations[0], fetched.observations[0]),
        )


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
    clock: Clock,
    scenario: FixtureScenario,
    provider_cls: type[MultiExpirationFixtureProvider] = MultiExpirationFixtureProvider,
) -> tuple[SubjectMarketDataAccess, CapabilityRegistry]:
    config = load_market_data_config({})
    (fixture_config,) = tuple(item for item in config.providers if item.enabled)
    fixture_config = dataclasses.replace(
        fixture_config,
        request_budget=dataclasses.replace(fixture_config.request_budget, burst_limit=BURST_LIMIT),
    )
    budget_manager = build_request_budget_manager((fixture_config,), clock)
    fixture_provider = provider_cls(
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
    provider_cls_by_symbol: dict[str, type[MultiExpirationFixtureProvider]] | None = None,
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
    capability failure); ``provider_cls_by_symbol`` likewise lets a test
    inject a deliberate per-symbol provider variant (e.g.
    WatchEarningsFixtureProvider). A symbol with no entry in either gets
    the fully successful default scenario / base provider.
    """
    scenarios = scenario_by_symbol or {}
    provider_classes = provider_cls_by_symbol or {}

    def _build(
        _config: Any,
        _transport_factory: Any,
        clock: Clock,
        subjects: tuple[str, ...],
        *,
        budget_clock: Any = None,
        rolling_window: Any = None,
    ) -> dict[str, SubjectMarketDataAccess]:
        result: dict[str, SubjectMarketDataAccess] = {}
        for symbol in subjects:
            access, _capability_registry = build_fixture_access(
                clock,
                scenarios.get(symbol, FixtureScenario()),
                provider_classes.get(symbol, MultiExpirationFixtureProvider),
            )
            result[symbol] = access
        return result

    return _build


def capturing_market_data_access_factory(
    factory: Callable[..., dict[str, SubjectMarketDataAccess]],
) -> tuple[Callable[..., dict[str, SubjectMarketDataAccess]], dict[str, SubjectMarketDataAccess]]:
    """Wraps an already-built build_shared_market_data_access replacement
    (e.g. from build_fixture_market_data_access_factory) so a test can
    inspect the SubjectMarketDataAccess objects a real production-root
    cycle/invocation actually used afterwards -- run_scheduled_refresh's
    own return value (a tuple of PairOutcome) exposes only each pair's own
    request_count delta, never the whole cycle's own total per symbol,
    which "bounded once, not doubled" for a shared subject plan requires
    comparing against shadow_alone_call_count's own isolated baseline.

    Returns ``(wrapped_factory, captured)`` -- monkeypatch in
    ``wrapped_factory`` exactly where ``factory`` itself would go;
    ``captured`` is populated (symbol -> its own SubjectMarketDataAccess)
    the moment the production root itself calls it, in place, so the
    SAME dict a test already holds a reference to reflects real state
    once the run completes.
    """
    captured: dict[str, SubjectMarketDataAccess] = {}

    def _wrapped(
        config: Any,
        transport_factory: Any,
        clock: Clock,
        subjects: tuple[str, ...],
        *,
        budget_clock: Any = None,
        rolling_window: Any = None,
    ) -> dict[str, SubjectMarketDataAccess]:
        result = factory(
            config,
            transport_factory,
            clock,
            subjects,
            budget_clock=budget_clock,
            rolling_window=rolling_window,
        )
        captured.update(result)
        return result

    return _wrapped, captured


def shadow_alone_call_count(
    symbol: str,
    now: datetime,
    scenario: FixtureScenario | None = None,
    provider_cls: type[MultiExpirationFixtureProvider] = MultiExpirationFixtureProvider,
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
    access, capability_registry = build_fixture_access(
        clock, scenario or FixtureScenario(), provider_cls
    )
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
        strategy_ids=("earnings_calendar",),
    )
    return len(access.budget_manager.accounting)
