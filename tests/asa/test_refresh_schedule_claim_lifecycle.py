"""Scheduler claim lifecycle parity without a database."""

from datetime import UTC, datetime, timedelta

import pytest

from asa.integrations.refresh_schedule_postgres import (
    InMemoryRefreshScheduleClaimRepository,
    ScheduleSlotOwnershipLost,
    ScheduleSlotState,
)

NOW = datetime(2026, 10, 16, 21, tzinfo=UTC)


def test_expired_owner_cannot_complete_successor_attempt() -> None:
    repository = InMemoryRefreshScheduleClaimRepository()
    slot = "complete-family:test:2026-10-16"
    first = repository.claim_due_slot(slot, NOW, timedelta(minutes=30))
    assert first is not None
    second = repository.claim_due_slot(slot, NOW + timedelta(minutes=31))
    assert second is not None

    with pytest.raises(ScheduleSlotOwnershipLost):
        repository.complete(
            first,
            completed_at=NOW + timedelta(minutes=32),
            state=ScheduleSlotState.DUE_EVALUATED,
        )

    current = repository.observations("complete-family:")[0]
    assert current.state == ScheduleSlotState.DUE_UNOBSERVED
    assert current.attempt_count == second.attempt_count
    repository.complete(
        second,
        completed_at=NOW + timedelta(minutes=33),
        state=ScheduleSlotState.DUE_EVALUATED,
    )
    assert repository.observations("complete-family:")[0].state == (
        ScheduleSlotState.DUE_EVALUATED
    )


def test_not_due_exception_retry_and_terminal_idempotency_are_distinct() -> None:
    repository = InMemoryRefreshScheduleClaimRepository()
    slot = "complete-family:test:2026-10-16"
    repository.observe_not_due(slot, NOW)
    assert repository.observations("complete-family:")[0].state == ScheduleSlotState.NOT_DUE
    first = repository.claim_due_slot(slot, NOW)
    assert first is not None
    repository.complete(
        first,
        completed_at=NOW,
        state=ScheduleSlotState.DUE_ASA_EXCEPTION,
        reason_code="injected",
    )
    retry = repository.claim_due_slot(slot, NOW)
    assert retry is not None
    repository.complete(
        retry,
        completed_at=NOW,
        state=ScheduleSlotState.DUE_TYPED_DEFERRED,
        reason_code="typed_deferred",
    )
    assert repository.claim_due_slot(slot, NOW + timedelta(hours=1)) is None
