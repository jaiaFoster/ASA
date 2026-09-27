"""Straddle weights and option-position returns (SP-01E).

Formula ids and versions are declared in `analytics.formulas`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from domain import UnknownReason


@dataclass(frozen=True, slots=True)
class StraddleWeights:
    """Return weights of a call+put pair; they sum to one."""

    call: Decimal
    put: Decimal


def zero_delta_straddle_weights(
    call_price: Decimal | None,
    put_price: Decimal | None,
    call_delta: Decimal | None,
    put_delta: Decimal | None,
) -> StraddleWeights | UnknownReason:
    """DF-STRADDLE-ZERO-DELTA-WEIGHT 1.0.0.

    w_c = -Δp·C / (Δc·P - Δp·C), w_p = Δc·P / (Δc·P - Δp·C). The implied
    quantities n_c = w_c / C and n_p = w_p / P satisfy n_c·Δc + n_p·Δp = 0.
    """
    if None in (call_price, put_price, call_delta, put_delta):
        return UnknownReason("missing_straddle_input")
    assert call_price is not None and put_price is not None
    assert call_delta is not None and put_delta is not None
    if call_price <= 0 or put_price <= 0:
        return UnknownReason("non_positive_option_price")
    if call_delta <= 0 or put_delta >= 0:
        return UnknownReason("invalid_delta_sign")
    denominator = call_delta * put_price - put_delta * call_price
    return StraddleWeights(
        -put_delta * call_price / denominator, call_delta * put_price / denominator
    )


def value_straddle_weights(
    call_price: Decimal | None, put_price: Decimal | None
) -> StraddleWeights | UnknownReason:
    """Simple straddle value weights C/(C+P), P/(C+P) (the DF-STRADDLE-RETURN alternative)."""
    if call_price is None or put_price is None:
        return UnknownReason("missing_straddle_input")
    total = call_price + put_price
    if call_price < 0 or put_price < 0 or total <= 0:
        return UnknownReason("non_positive_option_price")
    return StraddleWeights(call_price / total, put_price / total)


def straddle_return(
    weights: StraddleWeights | UnknownReason,
    call_return: Decimal | UnknownReason,
    put_return: Decimal | UnknownReason,
) -> Decimal | UnknownReason:
    """DF-STRADDLE-RETURN 1.0.0: w_c · R_call + w_p · R_put."""
    for item in (weights, call_return, put_return):
        if isinstance(item, UnknownReason):
            return item
    assert isinstance(weights, StraddleWeights)
    assert isinstance(call_return, Decimal) and isinstance(put_return, Decimal)
    return weights.call * call_return + weights.put * put_return


def zero_cost_option_return(
    entry_value: Decimal | None,
    exit_value: Decimal | None,
    risk_free_period_return: Decimal | UnknownReason | None,
    *,
    short: bool,
) -> Decimal | UnknownReason:
    """DF-ZERO-COST-OPTION-RETURN 1.0.0 (Santa-Clara-Saretto §2).

    Long: (V1 - V0)/V0 - rf. Short: (V0 - V1)/V0 + rf.
    """
    if isinstance(risk_free_period_return, UnknownReason):
        return risk_free_period_return
    if entry_value is None or exit_value is None or risk_free_period_return is None:
        return UnknownReason("missing_zero_cost_input")
    if entry_value <= 0:
        return UnknownReason("non_positive_entry_value")
    long_return = (exit_value - entry_value) / entry_value - risk_free_period_return
    return -long_return if short else long_return
