from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from domain import FreshnessStatus
from domain.values import DomainInvariantError
from market_data.session_calendar import (
    MarketSessionStatus,
    UsEquitySessionCalendar,
    classify_market_data_freshness,
    median_observed_at,
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
        result = classify_market_data_freshness(evaluated_at, effective, 3600)
        assert result.status is FreshnessStatus.PRIOR_SESSION

    def test_same_day_after_close_is_prior_session(self) -> None:
        result = classify_market_data_freshness(
            _utc(2026, 7, 24, 23), _utc(2026, 7, 24, 20), 3600
        )
        assert result.status is FreshnessStatus.PRIOR_SESSION

    def test_market_open_recent_quote_is_fresh(self) -> None:
        result = classify_market_data_freshness(
            _utc(2026, 7, 24, 15), _utc(2026, 7, 24, 14, 59), 3600
        )
        assert result.status is FreshnessStatus.FRESH

    def test_market_open_expired_quote_is_stale(self) -> None:
        result = classify_market_data_freshness(
            _utc(2026, 7, 24, 18), _utc(2026, 7, 24, 16), 3600
        )
        assert result.status is FreshnessStatus.STALE

    def test_quote_older_than_latest_completed_session_is_stale(self) -> None:
        result = classify_market_data_freshness(
            _utc(2026, 7, 26, 16), _utc(2026, 7, 23, 20), 3600
        )
        assert result.status is FreshnessStatus.STALE

    def test_naive_time_is_rejected(self) -> None:
        with pytest.raises(DomainInvariantError):
            classify_market_data_freshness(
                datetime(2026, 7, 25, 16), _utc(2026, 7, 24, 20), 3600
            )


class TestMedianObservedAt:
    def test_odd_count_returns_the_middle_value(self) -> None:
        early, middle, late = _utc(2026, 7, 24, 14), _utc(2026, 7, 24, 15), _utc(2026, 7, 24, 16)
        assert median_observed_at([late, early, middle]) == middle

    def test_even_count_returns_the_midpoint_of_the_two_middle_values(self) -> None:
        values = [
            _utc(2026, 7, 24, 14),
            _utc(2026, 7, 24, 15),
            _utc(2026, 7, 24, 16),
            _utc(2026, 7, 24, 17),
        ]
        expected = _utc(2026, 7, 24, 15) + (_utc(2026, 7, 24, 16) - _utc(2026, 7, 24, 15)) / 2
        assert median_observed_at(values) == expected

    def test_result_is_identical_regardless_of_input_order(self) -> None:
        values = [_utc(2026, 7, 24, 9), _utc(2026, 7, 24, 20), _utc(2026, 7, 24, 12)]
        forward = median_observed_at(values)
        reversed_order = median_observed_at(list(reversed(values)))
        assert forward == reversed_order

    def test_single_value_is_returned_unchanged(self) -> None:
        only = _utc(2026, 7, 24, 12)
        assert median_observed_at([only]) == only

    def test_empty_sequence_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one candidate"):
            median_observed_at([])

    def test_one_far_outlier_does_not_dominate_a_larger_cluster(self) -> None:
        cluster = [_utc(2026, 7, 24, 15, minute) for minute in (0, 1, 2, 3, 4)]
        far_outlier = _utc(2026, 7, 20, 0)
        result = median_observed_at([*cluster, far_outlier])
        assert _utc(2026, 7, 24, 15, 0) <= result <= _utc(2026, 7, 24, 15, 4)


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
