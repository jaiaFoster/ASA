"""Pure, deterministic verdict logic for the stock benchmarks (B001/B002).

Both benchmarks reach this function only once their required evidence has
already resolved and (for B002) SMA10M has already been materialized --
an unusable-evidence or insufficient-history gap is a typed UnknownReason
raised earlier in preparation, surfaced generically as MISSING_DATA, and
never reaches these functions at all.
"""

from __future__ import annotations

from strategies.stock_benchmark_knowledge import B001Payload, B002Payload

VERDICT_PASS = "PASS"
VERDICT_NO_SIGNAL = "NO_SIGNAL"


def evaluate_b001(payload: B001Payload) -> str:
    """SPY buy-and-hold: usable current price is always a PASS/BUY."""

    del payload
    return VERDICT_PASS


def evaluate_b002(payload: B002Payload) -> str:
    """SPY 10-month trend: PASS/BUY only strictly above the SMA10M."""

    return VERDICT_PASS if payload.price > payload.sma_10m else VERDICT_NO_SIGNAL
