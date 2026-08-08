"""SPRINT-009/EPIC-3: shared data planning.

Uses market_data's own real, offline DeterministicFixtureProvider (via
market_data.load_market_data_config({}), which enables only the fixture
provider by its own documented default -- no live network, no fake
provider written for this test) to prove real, end-to-end request
deduplication through the actual CapabilityFulfillmentService machinery,
not merely that two dict lookups return the same Python object.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    Instrument,
    InstrumentKind,
    MarketCapability,
    MarketDataRequestContext,
    MarketDataSubject,
    MarketDataSubjectType,
    ProviderAddressProjection,
)
from market_data import CapabilityRequest, load_market_data_config
from market_data.rolling_window import ProviderRollingWindowTracker, RollingWindowPolicy
from strategy_runtime import (
    NO_LIFECYCLE,
    DataRequirement,
    OutputKind,
    RequirementCategory,
    RuntimeContext,
    StrategyContract,
    StrategyRegistry,
    StructureKind,
    build_provider_rolling_window_tracker,
    build_shared_market_data_access,
    declared_rolling_window_policies,
    run_strategies,
)
from strategy_runtime.market_data_planning import enabled_provider_configs

NOW = datetime(2026, 1, 1, tzinfo=UTC)
CAPABILITY = MarketCapability.REAL_TIME_QUOTE_V1
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "instrument-reference:AAPL"),)
INSTRUMENT = Instrument(
    CanonicalInstrumentIdentity("figi", "BBG000B9XRY4"), InstrumentKind.EQUITY, "AAPL", "USD"
)


@dataclass
class _FixedClock:
    value: datetime = NOW

    def now(self) -> datetime:
        return self.value


def _quote_request() -> CapabilityRequest:
    fields = ("last",)
    projection = ProviderAddressProjection(
        "deterministic_fixture", "v1", "symbol", "AAPL", NOW, None, EVIDENCE
    )
    subject = MarketDataSubject(
        INSTRUMENT,
        MarketDataSubjectType.INSTRUMENT,
        CAPABILITY,
        MarketDataRequestContext(NOW, NOW, fields, (projection,), EVIDENCE),
    )
    return CapabilityRequest(CAPABILITY, (subject,), NOW, NOW, fields, 60)


def _no_transport_needed(_provider_id: str) -> object:
    # DeterministicFixtureProvider never touches this -- it is fixture-driven,
    # not network-driven -- but ProviderDependencies still requires a value.
    return object()


class TestBuildSharedMarketDataAccess:
    def test_one_access_per_subject(self) -> None:
        config = load_market_data_config({})
        access = build_shared_market_data_access(
            config, _no_transport_needed, _FixedClock(), ("AAPL", "MSFT")
        )
        assert set(access) == {"AAPL", "MSFT"}
        assert access["AAPL"].fulfillment is not access["MSFT"].fulfillment
        assert access["AAPL"].budget_manager is not access["MSFT"].budget_manager

    def test_identical_request_is_fulfilled_once_per_shared_service(self) -> None:
        # This is the actual mechanism EPIC-3 relies on: real
        # CapabilityFulfillmentService memoization, not a test double.
        config = load_market_data_config({})
        access = build_shared_market_data_access(
            config, _no_transport_needed, _FixedClock(), ("AAPL",)
        )
        fulfillment = access["AAPL"].fulfillment
        request = _quote_request()

        first = fulfillment.fulfill(request)
        second = fulfillment.fulfill(request)

        assert first is second  # identical object back -- genuinely not re-fetched


class TestRunStrategiesWithSharedMarketData:
    def _contract(self, strategy_id: str) -> StrategyContract:
        return StrategyContract(
            strategy_id=strategy_id,
            version="1.0.0",
            category="test",
            description="A test contract needing a real-time quote.",
            requirements=(
                DataRequirement(RequirementCategory.MARKET_DATA, capabilities=(CAPABILITY,)),
            ),
            lifecycle=NO_LIFECYCLE,
            structure=StructureKind.NONE,
            outputs=(OutputKind.METRICS,),
        )

    def test_two_strategies_closed_over_the_same_fulfillment_share_one_result(
        self,
    ) -> None:
        """SPRINT-014 S14-PR-05A (Architect checkpoint: twelfth review, item
        2): run_strategies()/RuntimeContext no longer thread a
        fulfillment_by_subject mapping at all -- acquisition is bound by
        closure at registry-construction time instead (item 3). Two
        adapters both closed over the identical, already-shared
        CapabilityFulfillmentService instance still observe the same
        de-duplicated result, proven here by construction rather than by
        any run_strategies()-owned per-subject lookup.
        """
        request = _quote_request()
        config = load_market_data_config({})
        clock = _FixedClock()
        access = build_shared_market_data_access(config, _no_transport_needed, clock, ("AAPL",))
        fulfillment = access["AAPL"].fulfillment

        def _build_adapter() -> Callable[[RuntimeContext], object]:
            def _adapter(context: RuntimeContext) -> object:
                return fulfillment.fulfill(request)

            return _adapter

        registry = StrategyRegistry(
            (
                (self._contract("alpha"), _build_adapter()),
                (self._contract("beta"), _build_adapter()),
            )
        )

        results = run_strategies(registry, clock, subjects=("AAPL",))

        assert len(results) == 2
        alpha_result = next(item for item in results if item.strategy_id == "alpha").result
        beta_result = next(item for item in results if item.strategy_id == "beta").result
        assert alpha_result is beta_result  # both adapters actually shared one fulfillment

    def test_runtime_context_has_no_fulfillment_field_at_all(self) -> None:
        """Architect checkpoint: twelfth review, item 1 -- "do not replace
        it with a generic data, services, resources, or similar escape
        hatch". Checked directly against the dataclass's own fields, not
        merely that some value was None.
        """
        assert "fulfillment" not in RuntimeContext.__dataclass_fields__


def _quote_request_for(symbol: str) -> CapabilityRequest:
    instrument = Instrument(
        CanonicalInstrumentIdentity("figi", f"BBG-{symbol}"), InstrumentKind.EQUITY, symbol, "USD"
    )
    fields = ("last",)
    projection = ProviderAddressProjection(
        "deterministic_fixture", "v1", "symbol", symbol, NOW, None, EVIDENCE
    )
    item = MarketDataSubject(
        instrument,
        MarketDataSubjectType.INSTRUMENT,
        CAPABILITY,
        MarketDataRequestContext(NOW, NOW, fields, (projection,), EVIDENCE),
    )
    return CapabilityRequest(CAPABILITY, (item,), NOW, NOW, fields, 60)


class TestProviderRollingWindowWiring:
    """SPRINT-013 S13-03A: build_shared_market_data_access's own
    rolling_window parameter, threaded through to every pair-scoped
    RequestBudgetManager it builds.
    """

    def _window(self, clock: _FixedClock, limit: int = 2) -> ProviderRollingWindowTracker:
        return ProviderRollingWindowTracker(
            (RollingWindowPolicy("deterministic_fixture", 60, limit, "test"),), clock
        )

    def test_two_different_pairs_consume_one_shared_provider_window(self) -> None:
        config = load_market_data_config({})
        clock = _FixedClock()
        window = self._window(clock, limit=2)
        access = build_shared_market_data_access(
            config, _no_transport_needed, clock, ("AAPL", "MSFT"), rolling_window=window
        )
        access["AAPL"].fulfillment.fulfill(_quote_request_for("AAPL"))
        access["MSFT"].fulfillment.fulfill(_quote_request_for("MSFT"))
        assert window.summary()["deterministic_fixture"] == 2

    def test_a_third_pair_is_refused_when_the_declared_window_is_full(self) -> None:
        from market_data import FulfillmentStatus

        config = load_market_data_config({})
        clock = _FixedClock()
        window = self._window(clock, limit=2)
        access = build_shared_market_data_access(
            config,
            _no_transport_needed,
            clock,
            ("AAPL", "MSFT", "GOOG"),
            rolling_window=window,
        )
        access["AAPL"].fulfillment.fulfill(_quote_request_for("AAPL"))
        access["MSFT"].fulfillment.fulfill(_quote_request_for("MSFT"))
        third = access["GOOG"].fulfillment.fulfill(_quote_request_for("GOOG"))
        assert third.status is FulfillmentStatus.FAILED
        assert third.attempts[0].error is not None
        assert third.attempts[0].error.code.value == "provider_rolling_window_exhausted"

    def test_per_pair_totals_and_retries_remain_isolated_under_a_shared_window(self) -> None:
        config = load_market_data_config({})
        clock = _FixedClock()
        window = self._window(clock, limit=100)  # generous -- isolates pair-local accounting
        access = build_shared_market_data_access(
            config, _no_transport_needed, clock, ("AAPL", "MSFT"), rolling_window=window
        )
        access["AAPL"].fulfillment.fulfill(_quote_request_for("AAPL"))
        access["MSFT"].fulfillment.fulfill(_quote_request_for("MSFT"))
        # Each pair's own RequestBudgetManager stays a distinct instance
        # with its own accounting, unaffected by the other pair's usage.
        assert access["AAPL"].budget_manager is not access["MSFT"].budget_manager
        assert len(access["AAPL"].budget_manager.accounting) == 1
        assert len(access["MSFT"].budget_manager.accounting) == 1

    def test_cache_hit_consumes_no_provider_unit(self) -> None:
        config = load_market_data_config({})
        clock = _FixedClock()
        window = self._window(clock, limit=1)
        access = build_shared_market_data_access(
            config, _no_transport_needed, clock, ("AAPL",), rolling_window=window
        )
        request = _quote_request_for("AAPL")
        first = access["AAPL"].fulfillment.fulfill(request)
        second = access["AAPL"].fulfillment.fulfill(request)  # memoized, no new authorize()
        assert first is second
        assert window.summary()["deterministic_fixture"] == 1  # only the first call reserved


class TestDeclaredRollingWindowPolicies:
    """No limit is ever invented for a provider without a typed, declared
    one (SPRINT-013 S13-03A) -- alpha_vantage today.
    """

    def test_alpha_vantage_gets_no_invented_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ASA_ALPHA_VANTAGE_ENABLED", "true")
        monkeypatch.setenv("ASA_ALPHA_VANTAGE_API_KEY", "test-key")
        config = load_market_data_config(
            {"ASA_ALPHA_VANTAGE_ENABLED": "true", "ASA_ALPHA_VANTAGE_API_KEY": "test-key"}
        )
        policies, undeclared = declared_rolling_window_policies(enabled_provider_configs(config))
        assert "alpha_vantage" in undeclared
        assert not any(item.provider_id == "alpha_vantage" for item in policies)

    def test_tradier_and_finnhub_get_their_own_declared_policies(self) -> None:
        config = load_market_data_config(
            {
                "ASA_TRADIER_ENABLED": "true",
                "ASA_TRADIER_ACCESS_TOKEN": "x",
                "ASA_FINNHUB_ENABLED": "true",
                "ASA_FINNHUB_API_KEY": "x",
            }
        )
        policies, undeclared = declared_rolling_window_policies(enabled_provider_configs(config))
        provider_ids = {item.provider_id for item in policies}
        assert {"tradier", "finnhub"} <= provider_ids
        assert "tradier" not in undeclared
        assert "finnhub" not in undeclared


class TestBuildProviderRollingWindowTracker:
    def test_scheduled_screening_constructs_one_tracker_per_cycle_not_per_pair(self) -> None:
        """The same tracker instance -- built once here -- is what a
        caller (asa/scheduled_screening.py) must reuse across every pair
        in one cycle; this proves the construction itself does not create
        new state per call within what should be a single invocation.
        """
        config = load_market_data_config(
            {"ASA_TRADIER_ENABLED": "true", "ASA_TRADIER_ACCESS_TOKEN": "x"}
        )
        clock = _FixedClock()
        tracker, undeclared = build_provider_rolling_window_tracker(config, clock)
        tracker.try_reserve("tradier")
        tracker.try_reserve("tradier")
        # Reusing the SAME instance (not rebuilding it) accumulates state,
        # exactly the property asa/scheduled_screening.py's per-pair loop
        # relies on for real cross-pair enforcement.
        assert tracker.summary()["tradier"] == 2
        # deterministic_fixture is enabled by default (load_market_data_config's
        # own safety default) and has no declared external rate limit --
        # correctly reported as undeclared, not silently dropped.
        assert undeclared == ("deterministic_fixture",)

    def test_a_new_cycle_receives_fresh_cycle_scoped_state(self) -> None:
        config = load_market_data_config(
            {"ASA_TRADIER_ENABLED": "true", "ASA_TRADIER_ACCESS_TOKEN": "x"}
        )
        clock = _FixedClock()
        first_tracker, _ = build_provider_rolling_window_tracker(config, clock)
        first_tracker.try_reserve("tradier")
        first_tracker.try_reserve("tradier")

        second_tracker, _ = build_provider_rolling_window_tracker(config, clock)

        assert second_tracker is not first_tracker
        assert second_tracker.summary()["tradier"] == 0  # fresh state, not inherited
