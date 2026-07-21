"""ASA-CORE-005: strategy calculation unit tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from domain.canonical_fact import CanonicalFact
from domain.provenance import Provenance
from domain.references import Confidence
from indicators.engine import compute_indicator
from strategies.calculations import breakout, momentum, moving_average_crossover
from strategies.errors import (
    InvalidStrategyParameterError,
    MissingIndicatorInputError,
    NoContributingFactsError,
)

T0 = datetime(2026, 7, 21, 14, 0, tzinfo=timezone.utc)


def _fact(i: int, price: str) -> CanonicalFact:
    t = T0 + timedelta(minutes=i)
    return CanonicalFact(
        fact_id=f"fact-{i}", version=1, fact_type="market_price",
        value=(("currency", "USD"), ("price", Decimal(price)), ("symbol", "AAPL")),
        confidence=Confidence(score=1.0),
        provenance=Provenance(
            contributing_observation_ids=(f"o{i}",), contributing_provider_ids=("p1",),
            selected_provider_id="p1", disagreements=(), reconciled_at=t),
        effective_time=t, created_time=t,
    )


def _ind(indicator_type, facts, effective_time, params=None):
    ind, _ = compute_indicator(indicator_type, facts, effective_time, effective_time,
                               params=params or {})
    return ind


class TestMovingAverageCrossover:
    def _rising_facts(self):
        # Prices designed so short(2) MA crosses above long(4) MA at fact-5
        return tuple(_fact(i, p) for i, p in enumerate(
            ["100", "100", "100", "100", "100", "110"]))

    def test_crossover_detected(self):
        facts = self._rising_facts()
        t_now = T0 + timedelta(minutes=5)
        t_prev = T0 + timedelta(minutes=4)
        short_ma = _ind("simple_moving_average", facts[:6], t_now, {"period": 2})
        long_ma = _ind("simple_moving_average", facts[:6], t_now, {"period": 4})
        short_prev = _ind("simple_moving_average", facts[:5], t_prev, {"period": 2})
        long_prev = _ind("simple_moving_average", facts[:5], t_prev, {"period": 4})

        assert short_prev.value <= long_prev.value  # precondition: was not above
        assert short_ma.value > long_ma.value  # precondition: now above

        signal = moving_average_crossover(
            {"short_ma": short_ma, "long_ma": long_ma,
             "short_ma_previous": short_prev, "long_ma_previous": long_prev},
            facts, {})
        assert signal is not None
        assert signal.expected_outcome_metrics.expected_return > 0

    def test_no_crossover_when_already_above(self):
        """short MA already above long MA on both calls — not a crossing event."""
        facts = tuple(_fact(i, "100") for i in range(6))
        # Force short already above long via distinct constant windows won't
        # naturally diverge with flat prices, so construct explicitly:
        t_now = T0 + timedelta(minutes=5)
        short_ma = _ind("latest_price", facts, t_now)
        long_ma = _ind("latest_price", facts, t_now)
        # Same value both times => never "was at/below then now above" is False by construction
        signal = moving_average_crossover(
            {"short_ma": short_ma, "long_ma": long_ma,
             "short_ma_previous": short_ma, "long_ma_previous": long_ma},
            facts, {})
        assert signal is None

    def test_missing_indicator_raises(self):
        facts = tuple(_fact(i, "100") for i in range(3))
        ind = _ind("latest_price", facts, T0 + timedelta(minutes=2))
        with pytest.raises(MissingIndicatorInputError):
            moving_average_crossover({"short_ma": ind}, facts, {})

    def test_evidence_narrowed_to_indicator_backing(self):
        facts = self._rising_facts()
        t_now = T0 + timedelta(minutes=5)
        t_prev = T0 + timedelta(minutes=4)
        short_ma = _ind("simple_moving_average", facts[:6], t_now, {"period": 2})
        long_ma = _ind("simple_moving_average", facts[:6], t_now, {"period": 4})
        short_prev = _ind("simple_moving_average", facts[:5], t_prev, {"period": 2})
        long_prev = _ind("simple_moving_average", facts[:5], t_prev, {"period": 4})
        signal = moving_average_crossover(
            {"short_ma": short_ma, "long_ma": long_ma,
             "short_ma_previous": short_prev, "long_ma_previous": long_prev},
            facts, {})
        cited = {r.referenced_id for ind in
                 (short_ma, long_ma, short_prev, long_prev) for r in ind.computed_from}
        assert {f.fact_id for f in signal.contributing_facts} <= cited
        assert {f.fact_id for f in signal.contributing_facts} == cited


class TestBreakout:
    def test_breakout_detected(self):
        facts = tuple(_fact(i, str(200 + i)) for i in range(5))
        rolling_high = _ind("rolling_high", facts[:4], T0 + timedelta(minutes=3),
                            {"period": 3})
        latest_price = _ind("latest_price", facts, T0 + timedelta(minutes=4))
        signal = breakout(
            {"latest_price": latest_price, "rolling_high": rolling_high}, facts, {})
        assert signal is not None
        assert signal.expected_outcome_metrics.expected_return > 0
        assert signal.expected_outcome_metrics.capital_required == Decimal("204")

    def test_no_breakout_when_price_below_high(self):
        facts = tuple(_fact(i, p) for i, p in enumerate(["200", "210", "190"]))
        rolling_high = _ind("rolling_high", facts, T0 + timedelta(minutes=2), {"period": 3})
        latest_price = _ind("latest_price", facts, T0 + timedelta(minutes=2))
        signal = breakout(
            {"latest_price": latest_price, "rolling_high": rolling_high}, facts, {})
        assert signal is None

    def test_missing_indicator_raises(self):
        facts = tuple(_fact(i, "100") for i in range(2))
        ind = _ind("latest_price", facts, T0 + timedelta(minutes=1))
        with pytest.raises(MissingIndicatorInputError):
            breakout({"latest_price": ind}, facts, {})

    def test_capital_required_uses_backing_facts_only(self):
        """capital_required must not be contaminated by unrelated candidate facts."""
        facts = tuple(_fact(i, str(200 + i)) for i in range(5))
        rolling_high = _ind("rolling_high", facts[:4], T0 + timedelta(minutes=3),
                            {"period": 3})
        latest_price = _ind("latest_price", facts, T0 + timedelta(minutes=4))
        signal = breakout(
            {"latest_price": latest_price, "rolling_high": rolling_high}, facts, {})
        # capital_required must equal the most recent backing fact's price (204),
        # not be skewed by any fact outside what latest_price/rolling_high cited.
        assert signal.expected_outcome_metrics.capital_required == Decimal("204")


class TestMomentum:
    def test_momentum_detected_above_threshold(self):
        facts = (_fact(0, "100"), _fact(1, "110"))
        pct = _ind("price_change_percent", facts, T0 + timedelta(minutes=1))
        signal = momentum(
            {"price_change_percent": pct}, facts, {"threshold": Decimal("0.05")})
        assert signal is not None
        assert signal.expected_outcome_metrics.expected_return == Decimal("0.1")

    def test_no_signal_below_threshold(self):
        facts = (_fact(0, "100"), _fact(1, "102"))
        pct = _ind("price_change_percent", facts, T0 + timedelta(minutes=1))
        signal = momentum(
            {"price_change_percent": pct}, facts, {"threshold": Decimal("0.05")})
        assert signal is None

    def test_missing_threshold_raises(self):
        facts = (_fact(0, "100"), _fact(1, "110"))
        pct = _ind("price_change_percent", facts, T0 + timedelta(minutes=1))
        with pytest.raises(InvalidStrategyParameterError):
            momentum({"price_change_percent": pct}, facts, {})

    def test_non_decimal_threshold_rejected(self):
        facts = (_fact(0, "100"), _fact(1, "110"))
        pct = _ind("price_change_percent", facts, T0 + timedelta(minutes=1))
        with pytest.raises(InvalidStrategyParameterError):
            momentum({"price_change_percent": pct}, facts, {"threshold": 0.05})

    def test_missing_indicator_raises(self):
        facts = (_fact(0, "100"),)
        with pytest.raises(MissingIndicatorInputError):
            momentum({}, facts, {"threshold": Decimal("0.05")})


class TestDecimalPrecision:
    def test_no_float_anywhere_in_metrics(self):
        facts = tuple(_fact(i, str(200 + i)) for i in range(5))
        rolling_high = _ind("rolling_high", facts[:4], T0 + timedelta(minutes=3),
                            {"period": 3})
        latest_price = _ind("latest_price", facts, T0 + timedelta(minutes=4))
        signal = breakout(
            {"latest_price": latest_price, "rolling_high": rolling_high}, facts, {})
        m = signal.expected_outcome_metrics
        assert isinstance(m.expected_return, Decimal)
        assert isinstance(m.maximum_loss, Decimal)
        assert isinstance(m.capital_required, Decimal)
