from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from analytics.derived_facts import (
    DERIVED_FACT_REGISTRY,
    compute_bid_ask_spread_ratio,
    compute_days_to_earnings,
    compute_earnings_inside_trade_window,
    compute_expiration_gap_days,
    compute_expiration_gap_distance,
    compute_forward_factor,
    compute_historical_percentile,
    compute_historical_zscore,
    compute_implied_forward_volatility,
    compute_iv_realized_spread,
    compute_momentum_dimensions,
    compute_normalized_skew,
    compute_open_interest_quality,
    compute_option_volume_band,
)


def test_forward_variance_and_factor_independent_vector() -> None:
    forward = compute_implied_forward_volatility(Decimal("0.40"), Decimal("0.35"), 30, 60)
    assert forward == Decimal("0.2915475947422650235437076438772792")
    assert compute_forward_factor(Decimal("0.40"), forward) == (
        Decimal("0.371988681140070699029212441775431")
    )


def test_earnings_and_expiration_temporal_facts() -> None:
    as_of = date(2026, 7, 1)
    front = date(2026, 7, 18)
    earnings = date(2026, 7, 21)
    back = date(2026, 8, 22)
    assert compute_days_to_earnings(as_of, earnings) == 20
    assert compute_earnings_inside_trade_window(earnings, front, back)
    assert compute_expiration_gap_days(front, back) == 35
    assert compute_expiration_gap_distance(front, back, 30) == 5


def test_normalized_skew_and_iv_realized_spread() -> None:
    assert compute_normalized_skew(Decimal("0.20"), Decimal("0.25")) == Decimal("0.25")
    assert compute_iv_realized_spread(Decimal("0.30"), Decimal("0.18")) == Decimal("0.12")
    history = (Decimal("-0.2"), Decimal("0"), Decimal("0.1"))
    assert compute_historical_percentile(Decimal("0"), history) == (Decimal(2) / Decimal(3))
    assert compute_historical_zscore(Decimal("0.1"), history) > 0


def test_raw_liquidity_dimensions_do_not_embed_strategy_thresholds() -> None:
    assert compute_bid_ask_spread_ratio(Decimal("0.90"), Decimal("1.10")) == Decimal("0.2")
    assert compute_option_volume_band(999) == 3
    assert compute_option_volume_band(None) == 0
    assert compute_open_interest_quality(1250) == 1250


def test_named_momentum_dimensions_are_replay_stable() -> None:
    closes = (Decimal("100"), Decimal("101"), Decimal("103"))
    first = compute_momentum_dimensions(closes)
    assert first == compute_momentum_dimensions(closes)
    assert first[0] == Decimal("0.03")


def test_initial_registry_is_closed_versioned_and_complete() -> None:
    assert len(DERIVED_FACT_REGISTRY.registered_ids()) == 18
    assert DERIVED_FACT_REGISTRY.get("forward_factor").feature_version == "1.0.0"


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (
            lambda: compute_implied_forward_volatility(Decimal("0.5"), Decimal("0.2"), 30, 31),
            "variance",
        ),
        (
            lambda: compute_expiration_gap_days(date(2026, 8, 1), date(2026, 7, 1)),
            "back expiration",
        ),
        (
            lambda: compute_bid_ask_spread_ratio(Decimal("2"), Decimal("1")),
            "bid and ask",
        ),
    ],
)
def test_invalid_inputs_fail_closed(call: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        call()  # type: ignore[operator]
