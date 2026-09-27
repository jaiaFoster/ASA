"""Frozen GXZ gate and exact-pair selection semantics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from analytics.option_facts import gxz_pair_volume, moneyness_spot_over_strike, option_mid
from analytics.option_returns import zero_delta_straddle_weights
from domain import OptionChain, OptionContract, OptionType, UnknownReason
from strategies import CORE_COMPONENTS, compile_strategy_graph, execute_strategy_graph
from strategies.gxz_components import GXZ_PLUGIN
from strategies.gxz_manifest import GXZ_MANIFEST
from strategies.plugins import build_plugin_registry
from strategies.tristate_components import TRISTATE, TRISTATE_PLUGIN
from strategies.type_system import ComponentValues, TypedValue

PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"
NO_ACTION = "NO_ACTION"

_COMPONENT_REGISTRY = build_plugin_registry(CORE_COMPONENTS, (TRISTATE_PLUGIN, GXZ_PLUGIN))
_GRAPH = compile_strategy_graph(GXZ_MANIFEST, _COMPONENT_REGISTRY)


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


def _graph_verdict(
    entry_session: str,
    ea_state: str,
    stock_state: str,
    expiry_state: str,
    pair_state: str,
) -> str:
    context = ComponentValues(
        (
            ("ea_stock.left", TypedValue(TRISTATE, ea_state)),
            ("ea_stock.right", TypedValue(TRISTATE, stock_state)),
            ("expiry_pair.left", TypedValue(TRISTATE, expiry_state)),
            ("expiry_pair.right", TypedValue(TRISTATE, pair_state)),
            ("verdict.entry_session", TypedValue(TRISTATE, entry_session)),
        )
    )
    return str(execute_strategy_graph(_GRAPH, context).outputs.get("verdict").value)


def evaluate_gxz(
    *,
    chain: OptionChain,
    spot: Decimal | None,
    earnings_date: date | None,
    earnings_confirmed: bool | None,
    entry_date: date,
    entry_session_state: str,
) -> GXZDecision:
    """Build gate facts, then let the frozen manifest graph own the verdict."""
    if entry_session_state not in (PASS, FAIL, UNKNOWN):
        raise ValueError("entry_session_state must be PASS, FAIL or UNKNOWN")

    ea_state = FAIL if earnings_date is None else PASS if earnings_confirmed is True else UNKNOWN
    ea_reason = (
        "G_GXZ_EA_DATE_KNOWN_FAIL"
        if ea_state == FAIL
        else "G_GXZ_EA_DATE_KNOWN_UNKNOWN"
        if ea_state == UNKNOWN
        else "GXZ_EA_DATE_KNOWN_PASS"
    )
    stock_state = UNKNOWN if spot is None else FAIL if spot < Decimal(5) else PASS
    stock_reason = (
        "G_GXZ_STOCK_PRICE_MIN_UNKNOWN"
        if stock_state == UNKNOWN
        else "G_GXZ_STOCK_PRICE_MIN_FAIL"
        if stock_state == FAIL
        else "GXZ_STOCK_PRICE_MIN_PASS"
    )
    expirations = sorted(
        {
            item.expiration
            for item in chain.contracts
            if earnings_date is not None
            and item.expiration > earnings_date
            and 4 <= (item.expiration - entry_date).days <= 10
        }
    )
    expiry_state = PASS if expirations else UNKNOWN if earnings_date is None else FAIL
    expiry_reason = (
        "GXZ_HOLD_TO_EXPIRY_DTE_PASS"
        if expiry_state == PASS
        else "G_GXZ_HOLD_TO_EXPIRY_DTE_UNKNOWN"
        if expiry_state == UNKNOWN
        else "G_GXZ_HOLD_TO_EXPIRY_DTE_FAIL"
    )

    by_strike: dict[Decimal, dict[OptionType, OptionContract]] = {}
    unknown_seen = False
    if expirations and spot is not None:
        expiration = expirations[0]
        for contract in chain.contracts:
            if contract.expiration != expiration:
                continue
            state = _eligible(contract, spot)
            if state is None:
                unknown_seen = True
            elif state:
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
        volume = gxz_pair_volume(call.volume, put.volume)
        if isinstance(weights, UnknownReason) or isinstance(volume, UnknownReason):
            unknown_seen = True
            continue
        if volume > 0:
            raw_pairs.append((call, put, weights.call / call_mid, weights.put / put_mid, volume))

    pair_state = (
        UNKNOWN if unknown_seen or spot is None or not expirations else PASS if raw_pairs else FAIL
    )
    pair_reason = (
        "G_GXZ_PAIR_INPUT_UNKNOWN"
        if pair_state == UNKNOWN
        else "G_GXZ_NO_QUALIFYING_PAIR"
        if pair_state == FAIL
        else "GXZ_PAIR_INPUT_PASS"
    )
    verdict = _graph_verdict(entry_session_state, ea_state, stock_state, expiry_state, pair_state)

    if verdict == NO_ACTION:
        return GXZDecision(verdict, "G_GXZ_ENTRY_SESSION_FAIL")
    if entry_session_state == UNKNOWN:
        return GXZDecision(verdict, "G_GXZ_ENTRY_SESSION_UNKNOWN")
    states = (
        (ea_state, ea_reason),
        (stock_state, stock_reason),
        (expiry_state, expiry_reason),
        (pair_state, pair_reason),
    )
    reason = next((item_reason for state, item_reason in states if state == verdict), None)
    if verdict != PASS:
        assert reason is not None
        return GXZDecision(verdict, reason)

    volume_total = sum((item[4] for item in raw_pairs), Decimal(0))
    pairs = tuple(
        GXZPair(call, put, call_qty, put_qty, volume / volume_total)
        for call, put, call_qty, put_qty, volume in raw_pairs
    )
    return GXZDecision(verdict, "GXZ_ALL_GATES_PASS", pairs)
