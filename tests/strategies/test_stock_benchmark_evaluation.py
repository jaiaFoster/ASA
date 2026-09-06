from __future__ import annotations

from decimal import Decimal

from strategies.stock_benchmark_evaluation import evaluate_b001, evaluate_b002
from strategies.stock_benchmark_knowledge import B001Payload, B002Payload


def test_b001_is_always_pass_once_reached() -> None:
    assert evaluate_b001(B001Payload(Decimal("560.25"))) == "PASS"


def test_b002_is_pass_strictly_above_sma() -> None:
    payload = B002Payload(price=Decimal("410"), sma_10m=Decimal("400"))
    assert evaluate_b002(payload) == "PASS"


def test_b002_is_no_signal_at_or_below_sma() -> None:
    at_sma = B002Payload(price=Decimal("400"), sma_10m=Decimal("400"))
    below_sma = B002Payload(price=Decimal("390"), sma_10m=Decimal("400"))
    assert evaluate_b002(at_sma) == "NO_SIGNAL"
    assert evaluate_b002(below_sma) == "NO_SIGNAL"
