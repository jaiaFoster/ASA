"""API-001: shared screening service (get_state/refresh) tests.

refresh() is exercised against the same zero-network deterministic_fixture
provider LIVE-002's own tests use -- proving the service correctly drives
the existing, unmodified run_screening()/build_live_adapters() machinery
end to end, not just that it's importable.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from market_data import CapabilityFulfillmentService, ProviderDependencies, ProviderRegistry
from market_data.config import load_market_data_config
from market_data.fixture import DeterministicFixtureProvider
from screening.adapters import TARGET_STRATEGY_REGISTRY
from screening.live_acquisition import build_capability_registry, build_request_budget_manager
from screening.service import get_state, refresh
from screening.state import ScreeningStateRecord, ScreeningStateRepository

NOW = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
SYMBOL = "AAPL"


class FixedClock:
    def __init__(self, start: datetime = NOW) -> None:
        self._next = start

    def now(self) -> datetime:
        current = self._next
        self._next = current + timedelta(microseconds=1)
        return current


class InMemoryScreeningStateRepository(ScreeningStateRepository):
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], ScreeningStateRecord] = {}

    def upsert(self, record: ScreeningStateRecord) -> None:
        self._records[(record.signal_id, record.symbol)] = record

    def get_all(self) -> tuple[ScreeningStateRecord, ...]:
        return tuple(sorted(self._records.values(), key=lambda item: (item.signal_id, item.symbol)))

    def get_for_signal(self, signal_id: str) -> tuple[ScreeningStateRecord, ...]:
        return tuple(
            sorted(
                (record for record in self._records.values() if record.signal_id == signal_id),
                key=lambda item: item.symbol,
            )
        )

    def get_one(self, signal_id: str, symbol: str) -> ScreeningStateRecord | None:
        return self._records.get((signal_id, symbol))


def _fulfillment() -> tuple[CapabilityFulfillmentService, FixedClock]:
    clock = FixedClock()
    config = load_market_data_config({})
    (fixture_config,) = tuple(item for item in config.providers if item.enabled)
    budget_manager = build_request_budget_manager((fixture_config,), clock)
    provider = DeterministicFixtureProvider(
        fixture_config, ProviderDependencies(object(), clock, budget_manager)
    )
    registry = ProviderRegistry((provider,))
    capability_registry = build_capability_registry(registry)
    return CapabilityFulfillmentService(registry, capability_registry, budget_manager), clock


class TestGetState:
    def test_returns_nothing_for_an_empty_repository(self) -> None:
        assert get_state(InMemoryScreeningStateRepository()) == ()

    def test_filters_by_strategy_and_symbol_together(self) -> None:
        repository = InMemoryScreeningStateRepository()
        wanted = ScreeningStateRecord("forward_factor", "1.0.0", "AAPL", "pass", "PASS", {}, NOW, {})
        other = ScreeningStateRecord("forward_factor", "1.0.0", "MSFT", "pass", "PASS", {}, NOW, {})
        repository.upsert(wanted)
        repository.upsert(other)
        assert get_state(repository, signal_id="forward_factor", symbol="AAPL") == (wanted,)

    def test_filters_by_strategy_only(self) -> None:
        repository = InMemoryScreeningStateRepository()
        a = ScreeningStateRecord("forward_factor", "1.0.0", "AAPL", "pass", "PASS", {}, NOW, {})
        b = ScreeningStateRecord("skew_momentum", "1.0.0", "AAPL", "pass", "PASS", {}, NOW, {})
        repository.upsert(a)
        repository.upsert(b)
        assert get_state(repository, signal_id="forward_factor") == (a,)

    def test_no_filters_returns_everything(self) -> None:
        repository = InMemoryScreeningStateRepository()
        a = ScreeningStateRecord("forward_factor", "1.0.0", "AAPL", "pass", "PASS", {}, NOW, {})
        b = ScreeningStateRecord("skew_momentum", "1.0.0", "MSFT", "pass", "PASS", {}, NOW, {})
        repository.upsert(a)
        repository.upsert(b)
        assert sorted(get_state(repository), key=lambda item: item.signal_id) == [a, b]


class TestRefresh:
    def test_computes_and_persists_exactly_one_strategy_and_symbol(self) -> None:
        fulfillment, clock = _fulfillment()
        repository = InMemoryScreeningStateRepository()
        record = refresh(
            repository,
            TARGET_STRATEGY_REGISTRY,
            fulfillment,
            clock,
            signal_id="earnings_calendar",
            symbol=SYMBOL,
        )
        assert record.signal_id == "earnings_calendar"
        assert record.symbol == SYMBOL
        assert repository.get_one("earnings_calendar", SYMBOL) == record

    def test_does_not_touch_other_strategies(self) -> None:
        fulfillment, clock = _fulfillment()
        repository = InMemoryScreeningStateRepository()
        refresh(
            repository,
            TARGET_STRATEGY_REGISTRY,
            fulfillment,
            clock,
            signal_id="earnings_calendar",
            symbol=SYMBOL,
        )
        assert repository.get_one("forward_factor", SYMBOL) is None
        assert repository.get_one("skew_momentum", SYMBOL) is None

    def test_a_second_refresh_overwrites_rather_than_accumulates(self) -> None:
        fulfillment, clock = _fulfillment()
        repository = InMemoryScreeningStateRepository()
        refresh(
            repository, TARGET_STRATEGY_REGISTRY, fulfillment, clock,
            signal_id="earnings_calendar", symbol=SYMBOL,
        )
        refresh(
            repository, TARGET_STRATEGY_REGISTRY, fulfillment, clock,
            signal_id="earnings_calendar", symbol=SYMBOL,
        )
        assert len(repository.get_all()) == 1
