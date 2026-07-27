"""Provider-neutral US equity session semantics for temporal quality."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from domain import FreshnessMetadata, FreshnessStatus
from domain.values import DomainInvariantError, require_tz_aware

NEW_YORK = ZoneInfo("America/New_York")


class MarketSessionStatus(StrEnum):
    PREMARKET = "premarket"
    OPEN = "open"
    AFTER_HOURS = "after_hours"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


@dataclass(frozen=True, slots=True)
class MarketSession:
    trading_date: date
    opens_at: datetime
    closes_at: datetime
    early_close: bool


class UsEquitySessionCalendar:
    """Modern NYSE session calendar without provider or wall-clock state."""

    def session(self, trading_date: date) -> MarketSession | None:
        if trading_date.weekday() >= 5 or trading_date in _holidays(trading_date.year):
            return None
        close_time = time(13) if trading_date in _early_closes(trading_date.year) else time(16)
        return MarketSession(
            trading_date,
            datetime.combine(trading_date, time(9, 30), NEW_YORK).astimezone(UTC),
            datetime.combine(trading_date, close_time, NEW_YORK).astimezone(UTC),
            close_time.hour == 13,
        )

    def status_at(self, instant: datetime) -> MarketSessionStatus:
        require_tz_aware(instant, "UsEquitySessionCalendar", "status_at")
        local = instant.astimezone(NEW_YORK)
        session = self.session(local.date())
        if session is None:
            return (
                MarketSessionStatus.WEEKEND
                if local.weekday() >= 5
                else MarketSessionStatus.HOLIDAY
            )
        if instant < session.opens_at:
            return MarketSessionStatus.PREMARKET
        if instant <= session.closes_at:
            return MarketSessionStatus.OPEN
        return MarketSessionStatus.AFTER_HOURS

    def latest_completed_session(self, instant: datetime) -> MarketSession:
        require_tz_aware(instant, "UsEquitySessionCalendar", "latest_completed_session")
        candidate = instant.astimezone(NEW_YORK).date()
        for _ in range(10):
            session = self.session(candidate)
            if session is not None and session.closes_at <= instant.astimezone(UTC):
                return session
            candidate -= timedelta(days=1)
        raise DomainInvariantError("no completed US equity session found in bounded lookback")


def classify_quote_freshness(
    as_of: datetime,
    effective_time: datetime,
    threshold_seconds: int,
    *,
    calendar: UsEquitySessionCalendar | None = None,
) -> FreshnessMetadata:
    """Classify age without rejecting expected closed-session evidence."""
    require_tz_aware(as_of, "classify_quote_freshness", "as_of")
    require_tz_aware(effective_time, "classify_quote_freshness", "effective_time")
    age = max(0, int((as_of - effective_time).total_seconds()))
    if age <= threshold_seconds:
        status = FreshnessStatus.FRESH
    else:
        completed = (calendar or UsEquitySessionCalendar()).latest_completed_session(as_of)
        status = (
            FreshnessStatus.PRIOR_SESSION
            if effective_time.astimezone(NEW_YORK).date() == completed.trading_date
            else FreshnessStatus.STALE
        )
    return FreshnessMetadata(as_of, effective_time, threshold_seconds, age, status)


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    value = date(year, month, 1)
    return value + timedelta(days=(weekday - value.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    value = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    return value - timedelta(days=(value.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    # Gregorian computus.
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    g = (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    length = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * length) // 451
    month = (h + length - 7 * m + 114) // 31
    return date(year, month, (h + length - 7 * m + 114) % 31 + 1)


def _holidays(year: int) -> frozenset[date]:
    values = {
        _observed(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _easter(year) - timedelta(days=2),
        _last_weekday(year, 5, 0),
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed(date(year, 12, 25)),
    }
    if year >= 2022:
        values.add(_observed(date(year, 6, 19)))
    # New Year's Day may be observed in the prior calendar year.
    values.add(_observed(date(year + 1, 1, 1)))
    return frozenset(values)


def _early_closes(year: int) -> frozenset[date]:
    thanksgiving = _nth_weekday(year, 11, 3, 4)
    values = {thanksgiving + timedelta(days=1)}
    christmas_eve = date(year, 12, 24)
    if christmas_eve.weekday() < 5 and christmas_eve not in _holidays(year):
        values.add(christmas_eve)
    july_third = date(year, 7, 3)
    if july_third.weekday() < 5 and july_third not in _holidays(year):
        values.add(july_third)
    return frozenset(values)
