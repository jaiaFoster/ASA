"""Frozen GXZ gate and exact-pair selection semantics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from analytics.option_facts import moneyness_spot_over_strike, option_mid
from analytics.option_returns import zero_delta_straddle_weights
from domain import OptionChain, OptionContract, OptionType, UnknownReason

PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"
NO_ACTION = "NO_ACTION"


@dataclass(frozen=True, slots=True)
class GXZPair:
    call: OptionContract
    put: OptionContract
    call_quantity: Decimal
    put_quantity: Decimal
    pair_weight: Decimal


@dataclass(frozen=True, slots=True)
class GXZDecision:
    verdict: str
    reason: str
    pairs: tuple[GXZPair, ...] = ()


def _eligible(contract: OptionContract, spot: Decimal) -> bool | None:
    mid = option_mid(contract.bid, contract.ask)
    money = moneyness_spot_over_strike(contract.strike, spot)
    if isinstance(mid, UnknownReason) or isinstance(money, UnknownReason):
        return None
    if contract.delta is None or contract.open_interest is None:
        return None
    if contract.bid is None or contract.ask is None:
        return None
    intrinsic = (
        max(Decimal(0), spot - contract.strike)
        if contract.option_type is OptionType.CALL
        else max(Decimal(0), contract.strike - spot)
    )
    upper_ok = (
        spot >= contract.bid
        if contract.option_type is OptionType.CALL
        else contract.strike >= contract.bid
    )
    return (
        contract.bid > 0
        and contract.bid < contract.ask
        and mid >= Decimal("0.125")
        and Decimal("0.375") <= abs(contract.delta) <= Decimal("0.625")
        and contract.open_interest > 0
        and Decimal("0.95") <= money <= Decimal("1.05")
        and upper_ok
        and contract.ask >= intrinsic
    )


def evaluate_gxz(
    *,
    chain: OptionChain,
    spot: Decimal | None,
    earnings_date: date | None,
    earnings_confirmed: bool | None,
    entry_date: date,
    entry_session_state: str,
) -> GXZDecision:
    """Apply the frozen truth table and deterministic multi-pair weighting."""
    if earnings_date is None:
        return GXZDecision(FAIL, "G_GXZ_EA_DATE_KNOWN_FAIL")
    if earnings_confirmed is not True:
        return GXZDecision(UNKNOWN, "G_GXZ_EA_DATE_KNOWN_UNKNOWN")
    if entry_session_state == FAIL:
        return GXZDecision(NO_ACTION, "G_GXZ_ENTRY_SESSION_FAIL")
    if entry_session_state != PASS:
        return GXZDecision(UNKNOWN, "G_GXZ_ENTRY_SESSION_UNKNOWN")
    if spot is None:
        return GXZDecision(UNKNOWN, "G_GXZ_STOCK_PRICE_MIN_UNKNOWN")
    if spot < Decimal(5):
        return GXZDecision(FAIL, "G_GXZ_STOCK_PRICE_MIN_FAIL")
    expirations = sorted(
        {
            item.expiration
            for item in chain.contracts
            if item.expiration > earnings_date and 4 <= (item.expiration - entry_date).days <= 10
        }
    )
    if not expirations:
        return GXZDecision(FAIL, "G_GXZ_HOLD_TO_EXPIRY_DTE_FAIL")
    expiration = expirations[0]
    by_strike: dict[Decimal, dict[OptionType, OptionContract]] = {}
    unknown_seen = False
    for contract in chain.contracts:
        if contract.expiration != expiration:
            continue
        state = _eligible(contract, spot)
        if state is None:
            unknown_seen = True
            continue
        if state:
            by_strike.setdefault(contract.strike, {})[contract.option_type] = contract
    raw_pairs: list[tuple[OptionContract, OptionContract, Decimal, Decimal, Decimal]] = []
    for strike in sorted(by_strike):
        items = by_strike[strike]
        if OptionType.CALL not in items or OptionType.PUT not in items:
            continue
        call, put = items[OptionType.CALL], items[OptionType.PUT]
        call_mid, put_mid = option_mid(call.bid, call.ask), option_mid(put.bid, put.ask)
        assert isinstance(call_mid, Decimal) and isinstance(put_mid, Decimal)
        weights = zero_delta_straddle_weights(call_mid, put_mid, call.delta, put.delta)
        if isinstance(weights, UnknownReason) or call.volume is None or put.volume is None:
            unknown_seen = True
            continue
        volume = Decimal(call.volume + put.volume)
        if volume <= 0:
            continue
        raw_pairs.append((call, put, weights.call / call_mid, weights.put / put_mid, volume))
    if not raw_pairs:
        return GXZDecision(
            UNKNOWN if unknown_seen else FAIL,
            "G_GXZ_PAIR_INPUT_UNKNOWN" if unknown_seen else "G_GXZ_NO_QUALIFYING_PAIR",
        )
    volume_total = sum((item[4] for item in raw_pairs), Decimal(0))
    pairs = tuple(
        GXZPair(call, put, call_qty, put_qty, volume / volume_total)
        for call, put, call_qty, put_qty, volume in raw_pairs
    )
    return GXZDecision(PASS, "GXZ_ALL_GATES_PASS", pairs)
