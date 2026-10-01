"""Exchange-calendar derived facts (SP-01E).

Pure functions over an injected trading-day predicate. The caller supplies
the canonical exchange calendar, so analytics never owns holiday data or
acquires anything. A calendar that does not cover a date range yields a
typed UNKNOWN, never a guess.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from domain import UnknownReason

_NEW_YORK = ZoneInfo("America/New_York")


def new_york_time(value: datetime) -> datetime:
    """Return an aware instant in the exchange-local New York timezone."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("new_york_time requires a timezone-aware datetime")
    return value.astimezone(_NEW_YORK)


@dataclass(frozen=True, slots=True)
class TradingCalendarView:
    """A trading-day predicate valid on [coverage_start, coverage_end]."""

    is_trading_day: Callable[[date], bool]
    coverage_start: date
    coverage_end: date

    def covers(self, day: date) -> bool:
        return self.coverage_start <= day <= self.coverage_end


_UNCOVERED = UnknownReason("trading_calendar_not_covered")


def _month_days(year: int, month: int) -> tuple[date, ...]:
    first = date(year, month, 1)
    following = date(year + (month == 12), month % 12 + 1, 1)
    return tuple(first + timedelta(days=offset) for offset in range((following - first).days))


def _covers_month(calendar: TradingCalendarView, year: int, month: int) -> bool:
    days = _month_days(year, month)
    return calendar.covers(days[0]) and calendar.covers(days[-1])


def trading_session_offset(
    calendar: TradingCalendarView, day: date, offset: int
) -> date | UnknownReason:
    """DF-TRADING-SESSION-OFFSET 1.0.0: the |offset|-th session before/after a trading date."""
    if not calendar.covers(day) or not calendar.is_trading_day(day):
        return _UNCOVERED if not calendar.covers(day) else UnknownReason("not_a_trading_day")
    step = timedelta(days=1 if offset > 0 else -1)
    cursor, remaining = day, abs(offset)
    while remaining:
        cursor += step
        if not calendar.covers(cursor):
            return _UNCOVERED
        if calendar.is_trading_day(cursor):
            remaining -= 1
    return cursor


def first_trading_day_of_month(
    calendar: TradingCalendarView, year: int, month: int
) -> date | UnknownReason:
    """DF-FIRST-TRADING-DAY-OF-MONTH 1.0.0."""
    if not _covers_month(calendar, year, month):
        return _UNCOVERED
    sessions = [day for day in _month_days(year, month) if calendar.is_trading_day(day)]
    return sessions[0] if sessions else UnknownReason("no_trading_session_in_month")


def last_trading_day_of_month(
    calendar: TradingCalendarView, year: int, month: int
) -> date | UnknownReason:
    """DF-LAST-TRADING-DAY-OF-MONTH 1.0.0."""
    if not _covers_month(calendar, year, month):
        return _UNCOVERED
    sessions = [day for day in _month_days(year, month) if calendar.is_trading_day(day)]
    return sessions[-1] if sessions else UnknownReason("no_trading_session_in_month")


def _third_friday_or_prior_session(
    calendar: TradingCalendarView, year: int, month: int
) -> date | UnknownReason:
    if not _covers_month(calendar, year, month):
        return _UNCOVERED
    fridays = [day for day in _month_days(year, month) if day.weekday() == 4]
    cursor = fridays[2]
    while not calendar.is_trading_day(cursor):
        cursor -= timedelta(days=1)
        if cursor.month != month:
            return UnknownReason("no_trading_session_before_third_friday")
    return cursor


def third_friday_roll_date(
    calendar: TradingCalendarView, year: int, month: int
) -> date | UnknownReason:
    """DF-THIRD-FRIDAY-ROLL-DATE 1.0.0: third Friday, else the preceding business day."""
    return _third_friday_or_prior_session(calendar, year, month)


def monthly_expiration_day(
    calendar: TradingCalendarView, year: int, month: int
) -> date | UnknownReason:
    """DF-MONTHLY-EXPIRATION-DAY 1.0.0: standard monthly expiration (third Friday or prior session).

    Same calendar rule as the roll date today; the two facts are kept
    distinct because their sources define them independently (Cboe index
    roll vs. equity-option expiration).
    """
    return _third_friday_or_prior_session(calendar, year, month)
