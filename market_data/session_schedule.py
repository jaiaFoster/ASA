"""Exchange-calendar-relative refresh schedule and bounded retry policy."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from domain.values import require_tz_aware
from market_data.session_calendar import NEW_YORK, UsEquitySessionCalendar

ON_DEMAND_COOLDOWN = timedelta(minutes=10)
MISSED_RUN_CATCH_UP = timedelta(minutes=20)
FAILURE_BACKOFF = (
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(minutes=30),
)


@dataclass(frozen=True, slots=True)
class ScheduledRefreshSlot:
    scheduled_at: datetime
    session_date: date
    ordinal: int

    @property
    def slot_id(self) -> str:
        payload = f"{self.session_date.isoformat()}:{self.ordinal}:{self.scheduled_at.isoformat()}"
        return hashlib.sha256(payload.encode()).hexdigest()


class SessionRefreshSchedule:
    def __init__(self, calendar: UsEquitySessionCalendar | None = None) -> None:
        self._calendar = calendar or UsEquitySessionCalendar()

    def slots_for(self, session_date: date) -> tuple[ScheduledRefreshSlot, ...]:
        session = self._calendar.session(session_date)
        if session is None:
            return ()
        instants: tuple[datetime, ...]
        if session.early_close:
            duration = session.closes_at - session.opens_at
            instants = (
                session.opens_at + timedelta(minutes=10),
                session.opens_at + duration / 3,
                session.opens_at + duration * 2 / 3,
                session.closes_at - timedelta(minutes=10),
            )
        else:
            instants = (
                session.opens_at + timedelta(minutes=10),
                session.opens_at + timedelta(hours=1, minutes=30),
                session.opens_at + timedelta(hours=3, minutes=30),
                session.opens_at + timedelta(hours=5, minutes=30),
                session.closes_at - timedelta(minutes=10),
            )
        return tuple(
            ScheduledRefreshSlot(instant.astimezone(UTC), session_date, index)
            for index, instant in enumerate(instants, start=1)
        )

    def due_slot(
        self,
        now: datetime,
        *,
        catch_up_window: timedelta = MISSED_RUN_CATCH_UP,
    ) -> ScheduledRefreshSlot | None:
        require_tz_aware(now, "SessionRefreshSchedule", "due_slot")
        session_date = now.astimezone(NEW_YORK).date()
        candidates = [
            slot
            for day_offset in (-1, 0, 1)
            for slot in self.slots_for(session_date + timedelta(days=day_offset))
            if slot.scheduled_at <= now.astimezone(UTC)
        ]
        if not candidates:
            return None
        latest = max(candidates, key=lambda item: item.scheduled_at)
        return latest if now.astimezone(UTC) - latest.scheduled_at <= catch_up_window else None

    def next_slot(self, after: datetime) -> ScheduledRefreshSlot:
        require_tz_aware(after, "SessionRefreshSchedule", "next_slot")
        candidate_date = after.astimezone(NEW_YORK).date()
        for day_offset in range(10):
            slots = self.slots_for(candidate_date + timedelta(days=day_offset))
            for slot in slots:
                if slot.scheduled_at > after.astimezone(UTC):
                    return slot
        raise ValueError("no scheduled refresh slot found in bounded lookahead")


def retry_at(failed_at: datetime, consecutive_failures: int) -> datetime:
    require_tz_aware(failed_at, "retry_at", "failed_at")
    if type(consecutive_failures) is not int or consecutive_failures < 1:
        raise ValueError("consecutive_failures must be positive")
    delay = FAILURE_BACKOFF[min(consecutive_failures - 1, len(FAILURE_BACKOFF) - 1)]
    return failed_at.astimezone(UTC) + delay
