"""SPRINT-011-CLOSEOUT/CLOSE-002: realized volatility and price momentum."""

from __future__ import annotations

from decimal import Decimal

import pytest

from analytics.realized_volatility import (
    InsufficientPriceHistoryError,
    compute_log_returns,
    compute_realized_volatility,
    compute_trailing_return,
)


class TestComputeLogReturns:
    def test_two_closes_produce_one_return(self) -> None:
        returns = compute_log_returns((Decimal("100"), Decimal("110")))
        assert len(returns) == 1
        assert returns[0] > Decimal(0)  # price rose

    def test_flat_series_produces_zero_returns(self) -> None:
        returns = compute_log_returns((Decimal("100"), Decimal("100"), Decimal("100")))
        assert all(value == Decimal(0) for value in returns)

    def test_fewer_than_two_closes_raises(self) -> None:
        with pytest.raises(InsufficientPriceHistoryError):
            compute_log_returns((Decimal("100"),))

    def test_non_positive_close_raises(self) -> None:
        with pytest.raises(InsufficientPriceHistoryError):
            compute_log_returns((Decimal("100"), Decimal("0")))


class TestComputeRealizedVolatility:
    def test_flat_series_has_zero_volatility(self) -> None:
        closes = tuple(Decimal("100") for _ in range(20))
        assert compute_realized_volatility(closes) == Decimal(0)

    def test_more_volatile_series_scores_higher(self) -> None:
        calm = (Decimal("100"), Decimal("101"), Decimal("100"), Decimal("101"), Decimal("100"))
        wild = (Decimal("100"), Decimal("130"), Decimal("90"), Decimal("140"), Decimal("80"))
        assert compute_realized_volatility(wild) > compute_realized_volatility(calm)

    def test_result_is_non_negative(self) -> None:
        closes = (Decimal("100"), Decimal("95"), Decimal("105"), Decimal("98"))
        assert compute_realized_volatility(closes) >= Decimal(0)


class TestComputeTrailingReturn:
    def test_positive_when_price_rose(self) -> None:
        assert compute_trailing_return((Decimal("100"), Decimal("120"))) == Decimal("0.2")

    def test_negative_when_price_fell(self) -> None:
        assert compute_trailing_return((Decimal("100"), Decimal("80"))) == Decimal("-0.2")

    def test_zero_when_flat(self) -> None:
        assert compute_trailing_return((Decimal("100"), Decimal("100"), Decimal("100"))) == Decimal(0)

    def test_only_endpoints_matter_not_the_path(self) -> None:
        volatile_path = (Decimal("100"), Decimal("200"), Decimal("10"), Decimal("110"))
        assert compute_trailing_return(volatile_path) == Decimal("0.1")

    def test_fewer_than_two_closes_raises(self) -> None:
        with pytest.raises(InsufficientPriceHistoryError):
            compute_trailing_return((Decimal("100"),))
