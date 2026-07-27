from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from domain import FreshnessStatus
from domain.values import DomainInvariantError
from market_data.session_calendar import (
    MarketSessionStatus,
    UsEquitySessionCalendar,
    classify_quote_freshness,
)


def _utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


class TestSessionAwareFreshness:
    @pytest.mark.parametrize(
        ("evaluated_at", "latest_session"),
        (
            (_utc(2026, 7, 25, 16), date(2026, 7, 24)),  # Saturday
            (_utc(2026, 7, 26, 16), date(2026, 7, 24)),  # Sunday
            (_utc(2026, 7, 27, 12), date(2026, 7, 24)),  # Monday 08:00 ET
            (_utc(2026, 7, 3, 16), date(2026, 7, 2)),  # Independence holiday
        ),
    )
    def test_latest_completed_session_quote_is_prior_session(
        self, evaluated_at: datetime, latest_session: date
    ) -> None:
        effective = datetime(
            latest_session.year,
            latest_session.month,
            latest_session.day,
            20,
            tzinfo=UTC,
        )
        result = classify_quote_freshness(evaluated_at, effective, 3600)
        assert result.status is FreshnessStatus.PRIOR_SESSION

    def test_same_day_after_close_is_prior_session(self) -> None:
        result = classify_quote_freshness(
            _utc(2026, 7, 24, 23), _utc(2026, 7, 24, 20), 3600
        )
        assert result.status is FreshnessStatus.PRIOR_SESSION

    def test_market_open_recent_quote_is_fresh(self) -> None:
        result = classify_quote_freshness(
            _utc(2026, 7, 24, 15), _utc(2026, 7, 24, 14, 59), 3600
        )
        assert result.status is FreshnessStatus.FRESH

    def test_market_open_expired_quote_is_stale(self) -> None:
        result = classify_quote_freshness(
            _utc(2026, 7, 24, 18), _utc(2026, 7, 24, 16), 3600
        )
        assert result.status is FreshnessStatus.STALE

    def test_quote_older_than_latest_completed_session_is_stale(self) -> None:
        result = classify_quote_freshness(
            _utc(2026, 7, 26, 16), _utc(2026, 7, 23, 20), 3600
        )
        assert result.status is FreshnessStatus.STALE

    def test_naive_time_is_rejected(self) -> None:
        with pytest.raises(DomainInvariantError):
            classify_quote_freshness(
                datetime(2026, 7, 25, 16), _utc(2026, 7, 24, 20), 3600
            )


class TestSessionCalendar:
    def test_early_close_uses_actual_close(self) -> None:
        session = UsEquitySessionCalendar().session(date(2026, 11, 27))
        assert session is not None
        assert session.early_close is True
        assert session.closes_at == _utc(2026, 11, 27, 18)

    def test_holiday_and_weekend_status_are_distinct(self) -> None:
        calendar = UsEquitySessionCalendar()
        assert calendar.status_at(_utc(2026, 7, 3, 16)) is MarketSessionStatus.HOLIDAY
        assert calendar.status_at(_utc(2026, 7, 4, 16)) is MarketSessionStatus.WEEKEND
