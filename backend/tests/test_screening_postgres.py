import os
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from screening.state import ScreeningStateRecord
from sqlalchemy import create_engine, text

from asa.integrations.screening_postgres import PostgresScreeningStateRepository

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv("ASA_TEST_DATABASE_URL"),
        reason="ASA_TEST_DATABASE_URL not set",
    ),
]


@pytest.fixture
def repository() -> PostgresScreeningStateRepository:
    database_url = os.environ["ASA_TEST_DATABASE_URL"]
    os.environ["ASA_DATABASE_URL"] = database_url
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE screening_state"))
    return PostgresScreeningStateRepository(engine)


def _record(
    signal_id: str = "forward_factor",
    symbol: str = "AAPL",
    outcome: str = "pass",
    updated_at: datetime | None = None,
) -> ScreeningStateRecord:
    return ScreeningStateRecord(
        signal_id=signal_id,
        signal_version="1.0.0",
        symbol=symbol,
        outcome=outcome,
        explanation="PASS",
        metrics={"strategy_native_score": "75"},
        updated_at=updated_at or datetime.now(UTC),
        dependency_timestamps={"as_of": updated_at or datetime.now(UTC)},
    )


def test_upsert_then_get_one_round_trips(repository: PostgresScreeningStateRepository) -> None:
    record = _record()
    repository.upsert(record)
    fetched = repository.get_one("forward_factor", "AAPL")
    assert fetched == record


def test_get_one_returns_none_when_absent(repository: PostgresScreeningStateRepository) -> None:
    assert repository.get_one("forward_factor", "AAPL") is None


def test_upsert_overwrites_rather_than_accumulates(
    repository: PostgresScreeningStateRepository,
) -> None:
    repository.upsert(_record(outcome="pass"))
    repository.upsert(_record(outcome="no_signal"))
    fetched = repository.get_one("forward_factor", "AAPL")
    assert fetched is not None
    assert fetched.outcome == "no_signal"
    assert len(repository.get_all()) == 1


def test_get_for_signal_filters_correctly(repository: PostgresScreeningStateRepository) -> None:
    repository.upsert(_record(signal_id="forward_factor", symbol="AAPL"))
    repository.upsert(_record(signal_id="forward_factor", symbol="MSFT"))
    repository.upsert(_record(signal_id="skew_momentum", symbol="AAPL"))
    results = repository.get_for_signal("forward_factor")
    assert {item.symbol for item in results} == {"AAPL", "MSFT"}
    assert all(item.signal_id == "forward_factor" for item in results)


def test_get_all_orders_deterministically(repository: PostgresScreeningStateRepository) -> None:
    repository.upsert(_record(signal_id="skew_momentum", symbol="MSFT"))
    repository.upsert(_record(signal_id="forward_factor", symbol="AAPL"))
    results = repository.get_all()
    assert [(item.signal_id, item.symbol) for item in results] == [
        ("forward_factor", "AAPL"),
        ("skew_momentum", "MSFT"),
    ]


def test_dependency_timestamps_round_trip_as_timezone_aware_datetimes(
    repository: PostgresScreeningStateRepository,
) -> None:
    as_of = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
    repository.upsert(_record(updated_at=as_of))
    fetched = repository.get_one("forward_factor", "AAPL")
    assert fetched is not None
    assert fetched.dependency_timestamps["as_of"] == as_of
    assert fetched.dependency_timestamps["as_of"].tzinfo is not None
