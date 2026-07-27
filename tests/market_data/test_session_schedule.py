from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from market_data.session_schedule import (
    SessionRefreshSchedule,
    retry_at,
)


def test_normal_session_has_five_exchange_relative_slots() -> None:
    slots = SessionRefreshSchedule().slots_for(date(2026, 7, 27))

    assert [item.scheduled_at.hour for item in slots] == [13, 15, 17, 19, 19]
    assert [item.scheduled_at.minute for item in slots] == [40, 0, 0, 0, 50]


def test_early_close_uses_actual_close_minus_ten_minutes() -> None:
    slots = SessionRefreshSchedule().slots_for(date(2026, 11, 27))

    assert len(slots) == 4
    assert slots[-1].scheduled_at == datetime(2026, 11, 27, 17, 50, tzinfo=UTC)


def test_weekend_and_full_holiday_have_no_provider_slots() -> None:
    schedule = SessionRefreshSchedule()

    assert schedule.slots_for(date(2026, 7, 4)) == ()
    assert schedule.slots_for(date(2026, 12, 25)) == ()


def test_dst_changes_utc_time_but_not_exchange_local_time() -> None:
    schedule = SessionRefreshSchedule()
    before_spring = schedule.slots_for(date(2026, 3, 6))[0]
    after_spring = schedule.slots_for(date(2026, 3, 9))[0]
    before_fall = schedule.slots_for(date(2026, 10, 30))[0]
    after_fall = schedule.slots_for(date(2026, 11, 2))[0]

    assert (before_spring.scheduled_at.hour, after_spring.scheduled_at.hour) == (14, 13)
    assert (before_fall.scheduled_at.hour, after_fall.scheduled_at.hour) == (13, 14)
    assert {
        item.scheduled_at.astimezone().minute
        for item in (before_spring, after_spring, before_fall, after_fall)
    } == {40}


def test_missed_run_catches_up_only_inside_twenty_minutes() -> None:
    schedule = SessionRefreshSchedule()

    assert schedule.due_slot(datetime(2026, 7, 27, 13, 59, tzinfo=UTC)) is not None
    assert schedule.due_slot(datetime(2026, 7, 27, 14, 1, tzinfo=UTC)) is None


def test_retry_backoff_is_bounded() -> None:
    failed_at = datetime(2026, 7, 27, 14, 0, tzinfo=UTC)

    assert retry_at(failed_at, 1) == failed_at + timedelta(minutes=5)
    assert retry_at(failed_at, 2) == failed_at + timedelta(minutes=15)
    assert retry_at(failed_at, 3) == failed_at + timedelta(minutes=30)
    assert retry_at(failed_at, 99) == failed_at + timedelta(minutes=30)
