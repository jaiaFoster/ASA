"""SPRINT-009/EPIC-3: shared data planning.

Uses market_data's own real, offline DeterministicFixtureProvider (via
market_data.load_market_data_config({}), which enables only the fixture
provider by its own documented default -- no live network, no fake
provider written for this test) to prove real, end-to-end request
deduplication through the actual CapabilityFulfillmentService machinery,
not merely that two dict lookups return the same Python object.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

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
from strategy_runtime import (
    NO_LIFECYCLE,
    DataRequirement,
    OutputKind,
    RequirementCategory,
    RuntimeContext,
    StrategyContract,
    StrategyRegistry,
    StructureKind,
    build_shared_market_data_access,
    run_strategies,
)

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

    def test_two_strategies_sharing_a_subject_get_the_same_fulfillment_result_object(
        self,
    ) -> None:
        request = _quote_request()

        def _adapter(context: RuntimeContext) -> object:
            assert context.fulfillment is not None
            return context.fulfillment.fulfill(request)

        registry = StrategyRegistry(
            ((self._contract("alpha"), _adapter), (self._contract("beta"), _adapter))
        )
        config = load_market_data_config({})
        clock = _FixedClock()
        access = build_shared_market_data_access(config, _no_transport_needed, clock, ("AAPL",))
        fulfillment_by_subject = {symbol: item.fulfillment for symbol, item in access.items()}

        results = run_strategies(
            registry, clock, subjects=("AAPL",), fulfillment_by_subject=fulfillment_by_subject
        )

        assert len(results) == 2
        alpha_result = next(item for item in results if item.strategy_id == "alpha").result
        beta_result = next(item for item in results if item.strategy_id == "beta").result
        assert alpha_result is beta_result  # both adapters actually shared one fulfillment

    def test_no_fulfillment_by_subject_leaves_context_fulfillment_none(self) -> None:
        seen: list[object] = []

        def _adapter(context: RuntimeContext) -> str:
            seen.append(context.fulfillment)
            return "ok"

        registry = StrategyRegistry(((self._contract("alpha"), _adapter),))
        clock = _FixedClock()

        run_strategies(registry, clock, subjects=("AAPL",))  # no fulfillment_by_subject at all

        assert seen == [None]
