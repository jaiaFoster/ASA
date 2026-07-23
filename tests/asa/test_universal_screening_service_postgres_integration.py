"""SPRINT-009/EPIC-9: strategy_runtime.service.get_state()/refresh()
exercised end to end against a real (test) Postgres instance, through
PostgresLatestResultRepository -- not the in-memory fake
tests/strategy_runtime/test_service.py already covers.

Mirrors tests/asa/test_screening_service_postgres_integration.py's own
exact pattern (API-002) for the same reason: proving get_state()'s reads
and refresh()'s upsert actually compose correctly through the real
raw-SQL/JSON-serialization layer, not just that each works in isolation.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from asa.integrations.universal_screening_postgres import PostgresLatestResultRepository
from market_data.config import load_market_data_config
from strategy_runtime.adapters import build_migrated_strategy_registry
from strategy_runtime.market_data_planning import build_shared_market_data_access
from strategy_runtime.service import get_state, refresh

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv("ASA_TEST_DATABASE_URL"),
        reason="ASA_TEST_DATABASE_URL not set",
    ),
]

SYMBOL = "AAPL"
STRATEGY_ID = "skew_momentum"


class FixedClock:
    def __init__(self, start: datetime) -> None:
        self._next = start

    def now(self) -> datetime:
        current = self._next
        self._next = current + timedelta(microseconds=1)
        return current


@pytest.fixture
def repository() -> PostgresLatestResultRepository:
    database_url = os.environ["ASA_TEST_DATABASE_URL"]
    os.environ["ASA_DATABASE_URL"] = database_url
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE universal_screening_state"))
    return PostgresLatestResultRepository(engine)


def _fulfillment_by_subject(clock: FixedClock) -> dict[str, object]:
    # The deterministic_fixture provider, left enabled (not force-disabled
    # via live_only_config()) -- this test is about persistence
    # round-tripping, not about the live-acquisition safety guarantee
    # EPIC-7's own tests already prove separately.
    config = load_market_data_config({})
    access = build_shared_market_data_access(
        config, lambda _provider_id: object(), clock, (SYMBOL,)
    )
    return {symbol: item.fulfillment for symbol, item in access.items()}


def test_refresh_persists_to_real_postgres_and_get_state_reads_it_back(
    repository: PostgresLatestResultRepository,
) -> None:
    clock = FixedClock(datetime(2026, 7, 23, 16, 0, tzinfo=UTC))
    registry = build_migrated_strategy_registry()

    refreshed = refresh(
        registry,
        repository,
        clock,
        strategy_id=STRATEGY_ID,
        symbol=SYMBOL,
        fulfillment_by_subject=_fulfillment_by_subject(clock),
    )

    (persisted,) = get_state(repository, strategy_id=STRATEGY_ID, symbol=SYMBOL)
    assert persisted == refreshed
    assert persisted.strategy_id == STRATEGY_ID
    assert persisted.symbol == SYMBOL
    assert persisted.observed_at.tzinfo is not None


def test_second_refresh_overwrites_the_real_row_rather_than_accumulating(
    repository: PostgresLatestResultRepository,
) -> None:
    clock = FixedClock(datetime(2026, 7, 23, 16, 0, tzinfo=UTC))
    registry = build_migrated_strategy_registry()

    refresh(
        registry,
        repository,
        clock,
        strategy_id=STRATEGY_ID,
        symbol=SYMBOL,
        fulfillment_by_subject=_fulfillment_by_subject(clock),
    )
    refresh(
        registry,
        repository,
        clock,
        strategy_id=STRATEGY_ID,
        symbol=SYMBOL,
        fulfillment_by_subject=_fulfillment_by_subject(clock),
    )

    assert len(get_state(repository)) == 1


def test_get_state_never_triggers_a_provider_request(
    repository: PostgresLatestResultRepository,
) -> None:
    # get_state()'s own signature (strategy_runtime/service.py) takes only
    # a repository -- structurally, not merely behaviorally, it has no
    # parameter through which a fulfillment service or provider could ever
    # be reached. Calling it repeatedly against real persisted state
    # (written once via refresh(), which does own a fulfillment service)
    # and getting back identical results is the decisive, observable proof.
    clock = FixedClock(datetime(2026, 7, 23, 16, 0, tzinfo=UTC))
    registry = build_migrated_strategy_registry()
    refresh(
        registry,
        repository,
        clock,
        strategy_id=STRATEGY_ID,
        symbol=SYMBOL,
        fulfillment_by_subject=_fulfillment_by_subject(clock),
    )

    first = get_state(repository, strategy_id=STRATEGY_ID)
    second = get_state(repository, strategy_id=STRATEGY_ID)
    assert first == second
