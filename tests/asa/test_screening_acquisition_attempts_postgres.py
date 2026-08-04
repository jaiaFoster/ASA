"""SPRINT-013 S13-02: PostgresAcquisitionAttemptRepository exercised
against a real (test) Postgres instance -- not the in-memory fake
tests/market_data/test_attempts.py already covers.

Mirrors tests/asa/test_universal_screening_service_postgres_integration.py's
own exact pattern: proving the same semantics
InMemoryAcquisitionAttemptRepository already proves (idempotency on
(pair_evaluation_id, sequence), stable-ordered filtered/paginated queries,
outcome-grouped summaries) hold end to end through the real raw-SQL layer.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from asa.integrations.screening_acquisition_attempts_postgres import (
    PostgresAcquisitionAttemptRepository,
)
from domain import MarketCapability
from market_data import FulfillmentStatus, ProviderErrorCode
from market_data.attempts import AcquisitionAttemptRecord, AcquisitionOutcome, AttemptQuery

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv("ASA_TEST_DATABASE_URL"),
        reason="ASA_TEST_DATABASE_URL not set",
    ),
]

CAPABILITY = MarketCapability.REAL_TIME_QUOTE_V1
RECORDED_AT = datetime(2026, 7, 21, 16, 0, tzinfo=UTC)


@pytest.fixture
def repository() -> PostgresAcquisitionAttemptRepository:
    database_url = os.environ["ASA_TEST_DATABASE_URL"]
    os.environ["ASA_DATABASE_URL"] = database_url
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE screening_acquisition_attempts"))
    return PostgresAcquisitionAttemptRepository(engine)


def _record(
    *,
    pair: str = "cycle_1:forward_factor:AAPL",
    sequence: int = 0,
    provider_id: str = "primary",
    outcome: AcquisitionOutcome = AcquisitionOutcome.SUCCESS,
    diagnostic_code: ProviderErrorCode | None = None,
    recorded_at: datetime = RECORDED_AT,
) -> AcquisitionAttemptRecord:
    failed = outcome is not AcquisitionOutcome.SUCCESS
    return AcquisitionAttemptRecord(
        "cycle_1",
        pair,
        sequence,
        CAPABILITY,
        provider_id,
        1,
        FulfillmentStatus.FULFILLED if not failed else FulfillmentStatus.FAILED,
        outcome,
        diagnostic_code if failed else None,
        failed,
        "a safe summary" if failed else None,
        recorded_at,
    )


def test_record_and_query_round_trip(
    repository: PostgresAcquisitionAttemptRepository,
) -> None:
    repository.record((_record(),))
    results = repository.query(AttemptQuery(screening_cycle_id="cycle_1"))
    assert len(results) == 1
    assert results[0].pair_evaluation_id == "cycle_1:forward_factor:AAPL"
    assert results[0].outcome is AcquisitionOutcome.SUCCESS
    assert results[0].diagnostic_code is None
    assert results[0].recorded_at == RECORDED_AT


def test_record_is_idempotent_on_pair_and_sequence(
    repository: PostgresAcquisitionAttemptRepository,
) -> None:
    repository.record((_record(),))
    repository.record((_record(),))
    results = repository.query(AttemptQuery(screening_cycle_id="cycle_1"))
    assert len(results) == 1


def test_does_not_collapse_a_genuinely_new_attempt(
    repository: PostgresAcquisitionAttemptRepository,
) -> None:
    repository.record((_record(sequence=0),))
    repository.record((_record(sequence=1, provider_id="secondary"),))
    results = repository.query(AttemptQuery(screening_cycle_id="cycle_1"))
    assert len(results) == 2


def test_diagnostic_code_round_trips(repository: PostgresAcquisitionAttemptRepository) -> None:
    repository.record(
        (
            _record(
                outcome=AcquisitionOutcome.TRANSPORT_FAILURE,
                diagnostic_code=ProviderErrorCode.TIMEOUT,
            ),
        )
    )
    results = repository.query(AttemptQuery(screening_cycle_id="cycle_1"))
    assert results[0].diagnostic_code is ProviderErrorCode.TIMEOUT
    assert results[0].outcome is AcquisitionOutcome.TRANSPORT_FAILURE


def test_query_filters_and_pagination_are_stable(
    repository: PostgresAcquisitionAttemptRepository,
) -> None:
    repository.record(
        tuple(
            _record(
                pair=f"cycle_1:forward_factor:SYM{i}",
                sequence=0,
                recorded_at=RECORDED_AT + timedelta(seconds=i),
            )
            for i in range(5)
        )
    )
    first_page = repository.query(AttemptQuery(limit=2, offset=0))
    second_page = repository.query(AttemptQuery(limit=2, offset=2))
    assert [item.pair_evaluation_id for item in first_page] == [
        "cycle_1:forward_factor:SYM0",
        "cycle_1:forward_factor:SYM1",
    ]
    assert [item.pair_evaluation_id for item in second_page] == [
        "cycle_1:forward_factor:SYM2",
        "cycle_1:forward_factor:SYM3",
    ]


def test_summarize_groups_by_outcome_ignoring_pagination(
    repository: PostgresAcquisitionAttemptRepository,
) -> None:
    repository.record(
        (
            _record(outcome=AcquisitionOutcome.SUCCESS),
            _record(
                pair="cycle_1:forward_factor:MSFT",
                outcome=AcquisitionOutcome.TRANSPORT_FAILURE,
                diagnostic_code=ProviderErrorCode.TRANSPORT_ERROR,
            ),
            _record(
                pair="cycle_1:forward_factor:GOOG",
                outcome=AcquisitionOutcome.TRANSPORT_FAILURE,
                diagnostic_code=ProviderErrorCode.TIMEOUT,
            ),
        )
    )
    counts = repository.summarize(AttemptQuery(screening_cycle_id="cycle_1", limit=1))
    assert counts == {
        AcquisitionOutcome.SUCCESS: 1,
        AcquisitionOutcome.TRANSPORT_FAILURE: 2,
    }


def test_no_raw_payloads_headers_or_credentials_in_stored_row(
    repository: PostgresAcquisitionAttemptRepository,
) -> None:
    """Column set itself is the guardrail -- there is no column that could
    hold a raw payload, header, or credential in the first place."""
    repository.record(
        (
            _record(
                outcome=AcquisitionOutcome.STALE_DATA,
                diagnostic_code=ProviderErrorCode.STALE_DATA,
            ),
        )
    )
    engine = repository._engine  # noqa: SLF001 -- test-only introspection
    with engine.connect() as connection:
        columns = connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'screening_acquisition_attempts'"
            )
        ).scalars()
        assert set(columns) == {
            "id", "screening_cycle_id", "pair_evaluation_id", "sequence", "capability",
            "provider_id", "priority", "fulfillment_status", "outcome", "diagnostic_code",
            "retryable", "safe_summary", "recorded_at",
        }
