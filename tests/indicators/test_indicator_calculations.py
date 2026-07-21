"""ASA-CORE-004: indicator calculation unit tests, including pinned regression vectors."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from domain.canonical_fact import CanonicalFact
from domain.provenance import Provenance
from domain.references import Confidence
from indicators.calculations import (
    exponential_moving_average,
    latest_price,
    price_change_percent,
    rolling_high,
    rolling_low,
    simple_moving_average,
)
from indicators.errors import (
    IndicatorCalculationError,
    InconsistentFactGroupError,
    InsufficientDataError,
)

T0 = datetime(2026, 7, 21, 14, 0, tzinfo=timezone.utc)


def _fact(i: int, price: str, fact_type: str = "market_price") -> CanonicalFact:
    t = T0 + timedelta(minutes=i)
    return CanonicalFact(
        fact_id=f"fact-{i}", version=1, fact_type=fact_type,
        value=(("currency", "USD"), ("price", Decimal(price)), ("symbol", "AAPL")),
        confidence=Confidence(score=1.0),
        provenance=Provenance(
            contributing_observation_ids=(f"o{i}",), contributing_provider_ids=("p1",),
            selected_provider_id="p1", disagreements=(), reconciled_at=t),
        effective_time=t, created_time=t,
    )


PRICES = ["200", "201", "202", "203", "204"]  # facts 0..4


def _facts(n: int = 5) -> tuple[CanonicalFact, ...]:
    return tuple(_fact(i, PRICES[i]) for i in range(n))


class TestLatestPrice:
    def test_returns_most_recent(self):
        value, contributing = latest_price(_facts(), {})
        assert value == Decimal("204")

    def test_cites_only_the_one_fact_used(self):
        value, contributing = latest_price(_facts(), {})
        assert {f.fact_id for f in contributing} == {"fact-4"}

    def test_order_independent(self):
        facts = _facts()
        shuffled = tuple(reversed(facts))
        assert latest_price(shuffled, {})[0] == latest_price(facts, {})[0]

    def test_single_fact(self):
        value, _ = latest_price((_fact(0, "150.25"),), {})
        assert value == Decimal("150.25")

    def test_empty_raises(self):
        with pytest.raises(InsufficientDataError):
            latest_price((), {})


class TestPriceChangePercent:
    def test_correctness(self):
        facts = (_fact(0, "100"), _fact(1, "110"))
        value, _ = price_change_percent(facts, {})
        assert value == Decimal("0.1")

    def test_negative_change(self):
        facts = (_fact(0, "100"), _fact(1, "90"))
        value, _ = price_change_percent(facts, {})
        assert value == Decimal("-0.1")

    def test_uses_last_two_of_larger_set(self):
        facts = _facts()  # 200..204, last two are 203, 204
        expected = (Decimal("204") - Decimal("203")) / Decimal("203")
        value, contributing = price_change_percent(facts, {})
        assert value == expected
        assert {f.fact_id for f in contributing} == {"fact-3", "fact-4"}

    def test_zero_previous_price_raises(self):
        facts = (_fact(0, "0"), _fact(1, "100"))
        with pytest.raises(IndicatorCalculationError):
            price_change_percent(facts, {})

    def test_insufficient_data_raises(self):
        with pytest.raises(InsufficientDataError):
            price_change_percent((_fact(0, "100"),), {})

    def test_decimal_precision_preserved(self):
        facts = (_fact(0, "3"), _fact(1, "10"))
        value, _ = price_change_percent(facts, {})
        assert isinstance(value, Decimal)
        assert value == Decimal(7) / Decimal(3)


class TestSimpleMovingAverage:
    def test_correctness(self):
        facts = _facts()  # 200..204
        value, _ = simple_moving_average(facts, {"period": 3})
        assert value == Decimal("203")  # mean(202,203,204)

    def test_cites_only_window_used(self):
        facts = _facts()
        _, contributing = simple_moving_average(facts, {"period": 3})
        assert {f.fact_id for f in contributing} == {"fact-2", "fact-3", "fact-4"}

    def test_period_equals_all_facts(self):
        facts = _facts()
        value, contributing = simple_moving_average(facts, {"period": 5})
        assert value == Decimal("202")  # mean(200..204)
        assert len(contributing) == 5

    def test_order_independent(self):
        facts = _facts()
        shuffled = tuple(reversed(facts))
        a, _ = simple_moving_average(facts, {"period": 3})
        b, _ = simple_moving_average(shuffled, {"period": 3})
        assert a == b

    def test_insufficient_data_raises(self):
        with pytest.raises(InsufficientDataError):
            simple_moving_average(_facts(2), {"period": 3})

    def test_decimal_precision_no_float_drift(self):
        facts = (_fact(0, "0.1"), _fact(1, "0.2"), _fact(2, "0.3"))
        value, _ = simple_moving_average(facts, {"period": 3})
        # 0.1 + 0.2 + 0.3 == 0.6 exactly in Decimal (unlike float)
        assert value == Decimal("0.2")


class TestExponentialMovingAverage:
    def test_correctness(self):
        # seed = mean(200,201,202) = 201; multiplier = 2/4 = 0.5
        # step 203: (203-201)*0.5+201 = 202
        # step 204: (204-202)*0.5+202 = 203
        facts = _facts()
        value, _ = exponential_moving_average(facts, {"period": 3})
        assert value == Decimal("203.00")

    def test_cites_all_facts_fed_to_running_average(self):
        facts = _facts()
        _, contributing = exponential_moving_average(facts, {"period": 3})
        assert {f.fact_id for f in contributing} == {f.fact_id for f in facts}

    def test_period_equals_all_facts_is_sma(self):
        facts = _facts()
        ema_value, _ = exponential_moving_average(facts, {"period": 5})
        sma_value, _ = simple_moving_average(facts, {"period": 5})
        assert ema_value == sma_value

    def test_order_independent(self):
        facts = _facts()
        shuffled = tuple(reversed(facts))
        a, _ = exponential_moving_average(facts, {"period": 3})
        b, _ = exponential_moving_average(shuffled, {"period": 3})
        assert a == b

    def test_insufficient_data_raises(self):
        with pytest.raises(InsufficientDataError):
            exponential_moving_average(_facts(2), {"period": 3})


class TestRollingHighLow:
    def test_rolling_high_correctness(self):
        facts = _facts()
        value, _ = rolling_high(facts, {"period": 3})
        assert value == Decimal("204")

    def test_rolling_low_correctness(self):
        facts = _facts()
        value, _ = rolling_low(facts, {"period": 3})
        assert value == Decimal("202")

    def test_rolling_high_low_cite_only_window_used(self):
        facts = _facts()
        _, high_contributing = rolling_high(facts, {"period": 3})
        _, low_contributing = rolling_low(facts, {"period": 3})
        assert {f.fact_id for f in high_contributing} == {"fact-2", "fact-3", "fact-4"}
        assert {f.fact_id for f in low_contributing} == {"fact-2", "fact-3", "fact-4"}

    def test_rolling_high_with_non_monotonic_prices(self):
        facts = (_fact(0, "100"), _fact(1, "150"), _fact(2, "120"))
        high, _ = rolling_high(facts, {"period": 3})
        low, _ = rolling_low(facts, {"period": 3})
        assert high == Decimal("150")
        assert low == Decimal("100")

    def test_order_independent(self):
        facts = (_fact(0, "100"), _fact(1, "150"), _fact(2, "120"))
        shuffled = tuple(reversed(facts))
        high_a, _ = rolling_high(facts, {"period": 3})
        high_b, _ = rolling_high(shuffled, {"period": 3})
        low_a, _ = rolling_low(facts, {"period": 3})
        low_b, _ = rolling_low(shuffled, {"period": 3})
        assert high_a == high_b
        assert low_a == low_b

    def test_insufficient_data_raises(self):
        with pytest.raises(InsufficientDataError):
            rolling_high(_facts(2), {"period": 3})
        with pytest.raises(InsufficientDataError):
            rolling_low(_facts(2), {"period": 3})


class TestConsistentFactGroup:
    def test_mixed_fact_type_rejected(self):
        facts = (_fact(0, "100", fact_type="a"), _fact(1, "101", fact_type="b"))
        with pytest.raises(InconsistentFactGroupError):
            latest_price(facts, {})

    def test_mixed_fact_type_rejected_in_sma(self):
        facts = (_fact(0, "100", fact_type="a"), _fact(1, "101", fact_type="b"))
        with pytest.raises(InconsistentFactGroupError):
            simple_moving_average(facts, {"period": 2})


# ---------------------------------------------------------------------------
# Pinned regression vectors
# ---------------------------------------------------------------------------

class TestPinnedCalculationVectors:
    """A failure here means calculation behavior changed unexpectedly."""

    def test_pinned_sma(self):
        value, _ = simple_moving_average(_facts(), {"period": 3})
        assert value == Decimal("203")

    def test_pinned_ema(self):
        value, _ = exponential_moving_average(_facts(), {"period": 3})
        assert value == Decimal("203.00")

    def test_pinned_latest_price(self):
        value, _ = latest_price(_facts(), {})
        assert value == Decimal("204")

    def test_pinned_price_change_percent(self):
        value, _ = price_change_percent(_facts(), {})
        assert str(value) == "0.004926108374384236453201970443"

    def test_pinned_rolling_high_low(self):
        high, _ = rolling_high(_facts(), {"period": 3})
        low, _ = rolling_low(_facts(), {"period": 3})
        assert high == Decimal("204")
        assert low == Decimal("202")
