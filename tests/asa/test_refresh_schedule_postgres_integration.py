"""Real-Postgres proofs for atomic oldest-first subject refresh state."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from asa.integrations.refresh_schedule_postgres import (
    PostgresRefreshScheduleClaimRepository,
    PostgresSubjectRefreshRepository,
    ScheduleSlotOwnershipLost,
    ScheduleSlotState,
)

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv("ASA_TEST_DATABASE_URL"),
        reason="ASA_TEST_DATABASE_URL not set",
    ),
]

NOW = datetime(2026, 8, 21, 16, 0, tzinfo=UTC)


@pytest.fixture
def repository() -> PostgresSubjectRefreshRepository:
    database_url = os.environ["ASA_TEST_DATABASE_URL"]
    os.environ["ASA_DATABASE_URL"] = database_url
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE screening_subject_refresh_state"))
        connection.execute(
            text("""
                UPDATE screening_operational_state
                SET last_attempted_batch_at = NULL,
                    last_successful_batch_at = NULL,
                    last_batch_subject_count = 0,
                    last_batch_pair_count = 0,
                    last_batch_failure_count = 0,
                    last_batch_incomplete_diagnostic_count = 0
                WHERE singleton_id = 1
            """)
        )
    return PostgresSubjectRefreshRepository(engine)


def test_atomic_claims_are_disjoint_and_abandoned_claims_recover(
    repository: PostgresSubjectRefreshRepository,
) -> None:
    first = repository.claim_oldest(
        ("MSFT", "AAPL", "NVDA"),
        claimed_at=NOW,
        maximum_subjects=2,
        lease=timedelta(minutes=30),
    )
    second = repository.claim_oldest(
        ("MSFT", "AAPL", "NVDA"),
        claimed_at=NOW,
        maximum_subjects=2,
        lease=timedelta(minutes=30),
    )

    assert first == ("AAPL", "MSFT")
    assert second == ("NVDA",)
    assert repository.claim_oldest(
        ("MSFT", "AAPL", "NVDA"),
        claimed_at=NOW + timedelta(minutes=31),
        maximum_subjects=2,
        lease=timedelta(minutes=30),
    ) == ("AAPL", "MSFT")


def test_completion_backoff_and_operational_health(
    repository: PostgresSubjectRefreshRepository,
) -> None:
    assert repository.claim_oldest(
        ("AAPL", "MSFT"),
        claimed_at=NOW,
        maximum_subjects=2,
        lease=timedelta(minutes=30),
    ) == ("AAPL", "MSFT")
    repository.batch_started(attempted_at=NOW, subject_count=2)
    repository.complete("AAPL", completed_at=NOW + timedelta(minutes=1), succeeded=True)
    repository.complete("MSFT", completed_at=NOW + timedelta(minutes=1), succeeded=False)
    repository.batch_completed(
        completed_at=NOW + timedelta(minutes=1),
        pair_count=6,
        failure_count=1,
        incomplete_diagnostic_count=0,
    )

    health = repository.operational_health(as_of=NOW + timedelta(minutes=2))
    assert health.last_attempted_batch_at == NOW
    assert health.last_successful_batch_at is None
    assert health.oldest_subject_age_seconds is None
    assert health.overdue_subject_count == 2
    assert health.last_batch_subject_count == 2
    assert health.last_batch_pair_count == 6
    assert health.last_batch_failure_count == 1
    assert health.last_batch_incomplete_diagnostic_count == 0
    assert repository.claim_oldest(
        ("AAPL", "MSFT"),
        claimed_at=NOW + timedelta(minutes=2),
        maximum_subjects=2,
        lease=timedelta(minutes=30),
    ) == ("AAPL",)


def test_due_slot_crash_lease_and_exception_retry_are_durable() -> None:
    database_url = os.environ["ASA_TEST_DATABASE_URL"]
    os.environ["ASA_DATABASE_URL"] = database_url
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE refresh_schedule_claims"))
    repository = PostgresRefreshScheduleClaimRepository(engine)
    slot = "complete-family:test-family:2026-10-16"

    first = repository.claim_due_slot(slot, NOW, lease=timedelta(minutes=30))
    assert first is not None
    assert repository.claim_due_slot(slot, NOW + timedelta(minutes=1)) is None
    assert repository.observations("complete-family:")[0].state == (
        ScheduleSlotState.DUE_UNOBSERVED
    )
    second = repository.claim_due_slot(slot, NOW + timedelta(minutes=31))
    assert second is not None
    with pytest.raises(ScheduleSlotOwnershipLost):
        repository.complete(
            first,
            completed_at=NOW + timedelta(minutes=31, seconds=30),
            state=ScheduleSlotState.DUE_EVALUATED,
        )
    still_owned = repository.observations("complete-family:")[0]
    assert still_owned.state == ScheduleSlotState.DUE_UNOBSERVED
    assert still_owned.attempt_count == second.attempt_count
    repository.complete(
        second,
        completed_at=NOW + timedelta(minutes=32),
        state=ScheduleSlotState.DUE_ASA_EXCEPTION,
        reason_code="injected_failure",
        failure_class="RuntimeError",
    )
    third = repository.claim_due_slot(slot, NOW + timedelta(minutes=33))
    assert third is not None
    repository.complete(
        third,
        completed_at=NOW + timedelta(minutes=34),
        state=ScheduleSlotState.DUE_EVALUATED,
    )
    observation = repository.observations("complete-family:")[0]
    assert observation.state == ScheduleSlotState.DUE_EVALUATED
    assert observation.attempt_count == 3


def test_upgrade_preserves_legacy_claim_as_unknown_completion() -> None:
    database_url = os.environ["ASA_TEST_DATABASE_URL"]
    os.environ["ASA_DATABASE_URL"] = database_url
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE refresh_schedule_claims"))
    command.downgrade(config, "0020")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO refresh_schedule_claims (slot_id, claimed_at) "
                "VALUES ('complete-family:legacy:2026-08-21', :claimed_at)"
            ),
            {"claimed_at": NOW},
        )
    command.upgrade(config, "head")

    observation = PostgresRefreshScheduleClaimRepository(engine).observations(
        "complete-family:legacy:"
    )[0]
    assert observation.state == ScheduleSlotState.DUE_UNOBSERVED
    assert observation.claimed_at == NOW
    # The migration does not fabricate execution completion; the old lease is
    # immediately recoverable by a fenced successor.
    successor = PostgresRefreshScheduleClaimRepository(engine).claim_due_slot(
        observation.slot_id, NOW + timedelta(seconds=1)
    )
    assert successor is not None
    assert successor.attempt_count == 2
    # Leave a projection-only row so Product CI's subsequent downgrade proves
    # the explicitly lossy legacy rollback path remains executable.
    PostgresRefreshScheduleClaimRepository(engine).observe_not_due(
        "complete-family:not-due:2026-08-21", NOW
    )
