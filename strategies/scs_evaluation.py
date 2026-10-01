"""Execute the frozen SCS manifest over sealed provider-neutral inputs."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import cast

from domain import OptionChain, OptionContract, UnknownReason
from strategies import CORE_COMPONENTS, compile_strategy_graph, execute_strategy_graph
from strategies.manifest import StrategyManifest
from strategies.plugins import build_plugin_registry
from strategies.scs_components import (
    DATE,
    DECIMAL,
    INSTANT,
    OPTION_CHAIN,
    OPTIONAL_DECIMAL,
    SCS_PLUGIN,
)
from strategies.scs_manifest import SCS_MANIFEST
from strategies.tristate_components import FAIL, TRISTATE_PLUGIN, UNKNOWN
from strategies.type_system import ComponentValues, TypedValue

NO_ACTION = "NO_ACTION"
_REGISTRY = build_plugin_registry(CORE_COMPONENTS, (TRISTATE_PLUGIN, SCS_PLUGIN))
_GRAPH = compile_strategy_graph(SCS_MANIFEST, _REGISTRY)


@dataclass(frozen=True, slots=True)
class SCSDecision:
    verdict: str
    reason: str
    selected_call: OptionContract | None = None
    selected_put: OptionContract | None = None
    short_call_quantity: Decimal = Decimal(1)
    short_put_quantity: Decimal = Decimal(1)
    call_naked_margin: Decimal | UnknownReason = UnknownReason("G_SCS_MARGIN_UNKNOWN")
    put_naked_margin: Decimal | UnknownReason = UnknownReason("G_SCS_MARGIN_UNKNOWN")
    straddle_margin: Decimal | UnknownReason = UnknownReason("G_SCS_MARGIN_UNKNOWN")


def evaluate_scs(
    *,
    decision_date: date,
    entry_date_state: str | None = None,
    selected_expiration: date | UnknownReason,
    spot: Decimal | None,
    chain: OptionChain | None,
    rate: Decimal | None,
    dividend_yield: Decimal | None,
    decision_time: datetime | None = None,
    quote_effective_time: datetime | None = None,
    first_trading_day: date | None = None,
    session_close: datetime | None = None,
    manifest: StrategyManifest = SCS_MANIFEST,
) -> SCSDecision:
    if entry_date_state == FAIL:
        return SCSDecision(NO_ACTION, "G_SCS_ENTRY_DATE_FAIL")
    if isinstance(selected_expiration, UnknownReason):
        return SCSDecision(UNKNOWN, "G_SCS_EXPIRY_UNIQUE_UNKNOWN")
    if spot is None or chain is None:
        return SCSDecision(UNKNOWN, "G_SCS_STRIKE_UNIQUE_UNKNOWN")
    instant = decision_time or datetime.combine(decision_date, time.max, UTC)
    quote_time = quote_effective_time or instant
    entry_day = first_trading_day or decision_date
    close_time = session_close or instant
    graph = _GRAPH if manifest is SCS_MANIFEST else compile_strategy_graph(manifest, _REGISTRY)
    outputs = execute_strategy_graph(
        graph,
        ComponentValues(
            (
                ("policy.decision_time", TypedValue(INSTANT, instant)),
                ("policy.quote_effective_time", TypedValue(INSTANT, quote_time)),
                ("policy.first_trading_day", TypedValue(DATE, entry_day)),
                ("policy.session_close", TypedValue(INSTANT, close_time)),
                ("policy.selected_expiration", TypedValue(DATE, selected_expiration)),
                ("policy.spot", TypedValue(DECIMAL, spot)),
                ("policy.chain", TypedValue(OPTION_CHAIN, chain)),
                ("policy.rate", TypedValue(OPTIONAL_DECIMAL, rate)),
                ("policy.dividend_yield", TypedValue(OPTIONAL_DECIMAL, dividend_yield)),
            )
        ),
    ).outputs
    raw = cast(str, outputs.get("verdict").value)
    entry = cast(str, outputs.get("entry_state").value)
    call = cast(OptionContract | None, outputs.get("selected_call").value)
    put = cast(OptionContract | None, outputs.get("selected_put").value)
    selection_reason = cast(str, outputs.get("selection_reason").value)
    call_margin = cast(Decimal | None, outputs.get("call_naked_margin").value)
    put_margin = cast(Decimal | None, outputs.get("put_naked_margin").value)
    straddle_margin = cast(Decimal | None, outputs.get("straddle_margin").value)
    verdict = NO_ACTION if raw == FAIL and entry == FAIL else raw
    reason = (
        "G_SCS_ENTRY_DATE_FAIL"
        if verdict == NO_ACTION
        else "G_SCS_ENTRY_DATE_UNKNOWN"
        if entry == UNKNOWN
        else selection_reason
        if raw == UNKNOWN
        else "SCS_ALL_GATES_PASS"
    )
    return SCSDecision(
        verdict,
        reason,
        call,
        put,
        cast(Decimal, outputs.get("short_call_quantity").value),
        cast(Decimal, outputs.get("short_put_quantity").value),
        call_margin if call_margin is not None else UnknownReason("G_SCS_MARGIN_UNKNOWN"),
        put_margin if put_margin is not None else UnknownReason("G_SCS_MARGIN_UNKNOWN"),
        straddle_margin
        if straddle_margin is not None
        else UnknownReason("G_SCS_MARGIN_UNKNOWN"),
    )
