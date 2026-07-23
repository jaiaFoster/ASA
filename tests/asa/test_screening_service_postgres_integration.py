"""API-002: screening.service.get_state()/refresh() exercised end to end
against a real (test) Postgres instance, not the InMemoryScreeningStateRepository
fake tests/screening/test_service.py already covers.

tests/asa/test_screening_postgres.py proves PostgresScreeningStateRepository's
own CRUD behavior in isolation; tests/screening/test_service.py proves
get_state()/refresh()'s own orchestration logic against an in-memory fake.
Neither proves the two actually compose correctly -- that refresh()'s upsert
call and get_state()'s reads round-trip through the real repository's raw-SQL/
JSON-serialization layer without loss or type mismatch. This closes that gap.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from asa.integrations.screening_postgres import PostgresScreeningStateRepository
from market_data import CapabilityFulfillmentService, ProviderDependencies, ProviderRegistry
from market_data.budget import RequestBudgetManager
from market_data.config import load_market_data_config
from market_data.fixture import DeterministicFixtureProvider
from screening.adapters import TARGET_STRATEGY_REGISTRY
from screening.live_acquisition import build_capability_registry, build_request_budget_manager
from screening.service import get_state, refresh

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv("ASA_TEST_DATABASE_URL"),
        reason="ASA_TEST_DATABASE_URL not set",
    ),
]

SYMBOL = "AAPL"


class FixedClock:
    def __init__(self, start: datetime) -> None:
        self._next = start

    def now(self) -> datetime:
        current = self._next
        self._next = current + timedelta(microseconds=1)
        return current


@pytest.fixture
def repository() -> PostgresScreeningStateRepository:
    database_url = os.environ["ASA_TEST_DATABASE_URL"]
    os.environ["ASA_DATABASE_URL"] = database_url
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE screening_state"))
    return PostgresScreeningStateRepository(engine)


def _fulfillment() -> tuple[CapabilityFulfillmentService, FixedClock, RequestBudgetManager]:
    clock = FixedClock(datetime(2026, 7, 23, 16, 0, tzinfo=UTC))
    config = load_market_data_config({})
    (fixture_config,) = tuple(item for item in config.providers if item.enabled)
    budget_manager = build_request_budget_manager((fixture_config,), clock)
    provider = DeterministicFixtureProvider(
        fixture_config, ProviderDependencies(object(), clock, budget_manager)
    )
    registry = ProviderRegistry((provider,))
    capability_registry = build_capability_registry(registry)
    return (
        CapabilityFulfillmentService(registry, capability_registry, budget_manager),
        clock,
        budget_manager,
    )


def test_refresh_persists_to_real_postgres_and_get_state_reads_it_back(
    repository: PostgresScreeningStateRepository,
) -> None:
    fulfillment, clock, _ = _fulfillment()

    refreshed = refresh(
        repository,
        TARGET_STRATEGY_REGISTRY,
        fulfillment,
        clock,
        signal_id="earnings_calendar",
        symbol=SYMBOL,
    )

    (persisted,) = get_state(repository, signal_id="earnings_calendar", symbol=SYMBOL)
    assert persisted == refreshed
    assert persisted.signal_id == "earnings_calendar"
    assert persisted.symbol == SYMBOL
    assert persisted.updated_at.tzinfo is not None


def test_second_refresh_overwrites_the_real_row_rather_than_accumulating(
    repository: PostgresScreeningStateRepository,
) -> None:
    fulfillment, clock, _ = _fulfillment()

    refresh(
        repository, TARGET_STRATEGY_REGISTRY, fulfillment, clock,
        signal_id="earnings_calendar", symbol=SYMBOL,
    )
    refresh(
        repository, TARGET_STRATEGY_REGISTRY, fulfillment, clock,
        signal_id="earnings_calendar", symbol=SYMBOL,
    )

    all_state = get_state(repository)
    assert len(all_state) == 1


def test_get_state_never_triggers_a_provider_request(
    repository: PostgresScreeningStateRepository,
) -> None:
    fulfillment, clock, budget_manager = _fulfillment()
    refresh(
        repository, TARGET_STRATEGY_REGISTRY, fulfillment, clock,
        signal_id="earnings_calendar", symbol=SYMBOL,
    )
    before = len(budget_manager.accounting)

    get_state(repository)
    get_state(repository, signal_id="earnings_calendar")
    get_state(repository, signal_id="earnings_calendar", symbol=SYMBOL)

    after = len(budget_manager.accounting)
    assert after == before
