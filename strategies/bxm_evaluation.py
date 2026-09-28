"""Frozen Cboe BXM roll and exact-call selection semantics."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from domain import OptionChain, OptionContract, OptionType, SettlementStyle, UnknownReason
from strategies import CORE_COMPONENTS, compile_strategy_graph, execute_strategy_graph
from strategies.bxm_manifest import BXM_MANIFEST
from strategies.cboe_put_components import CBOE_PUT_PLUGIN
from strategies.plugins import build_plugin_registry
from strategies.tristate_components import FAIL, PASS, TRISTATE, TRISTATE_PLUGIN, UNKNOWN
from strategies.type_system import ComponentValues, TypedValue

NO_ACTION = "NO_ACTION"
_GRAPH = compile_strategy_graph(
    BXM_MANIFEST, build_plugin_registry(CORE_COMPONENTS, (TRISTATE_PLUGIN, CBOE_PUT_PLUGIN))
)


@dataclass(frozen=True, slots=True)
class BXMDecision:
    verdict: str
    reason: str
    selected_call: OptionContract | None = None


def evaluate_bxm(
    *,
    decision_date: date,
    roll_date: date | UnknownReason,
    reference_state: str,
    quote_value: Decimal | None,
    chain: OptionChain | None,
) -> BXMDecision:
    if reference_state not in (PASS, UNKNOWN):
        raise ValueError("reference_state must be PASS or UNKNOWN")
    roll_state = (
        UNKNOWN
        if isinstance(roll_date, UnknownReason)
        else PASS
        if decision_date == roll_date
        else FAIL
    )
    if roll_state == FAIL:
        return BXMDecision(NO_ACTION, "G_CBOE_MONTHLY_ROLL_DATE_FAIL")
    if roll_state == UNKNOWN:
        return BXMDecision(UNKNOWN, "G_CBOE_MONTHLY_ROLL_DATE_UNKNOWN")
    assert isinstance(roll_date, date)
    year, month = (
        (roll_date.year + 1, 1) if roll_date.month == 12 else (roll_date.year, roll_date.month + 1)
    )
    candidates = (
        ()
        if chain is None or quote_value is None
        else tuple(
            item
            for item in chain.contracts
            if item.option_type is OptionType.CALL
            and item.root == "SPX"
            and item.settlement_style is SettlementStyle.AM
            and (item.expiration.year, item.expiration.month) == (year, month)
            and item.strike >= quote_value
        )
    )
    selected = (
        min(candidates, key=lambda item: (item.strike, item.identity)) if candidates else None
    )
    strike_state = PASS if selected is not None else UNKNOWN
    verdict = str(
        execute_strategy_graph(
            _GRAPH,
            ComponentValues(
                (
                    ("entry_gates.left", TypedValue(TRISTATE, reference_state)),
                    ("entry_gates.right", TypedValue(TRISTATE, strike_state)),
                    ("verdict.roll_date", TypedValue(TRISTATE, roll_state)),
                )
            ),
        )
        .outputs.get("verdict")
        .value
    )
    if reference_state == UNKNOWN:
        return BXMDecision(verdict, "G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN")
    if selected is None:
        return BXMDecision(verdict, "G_BXM_STRIKE_EXISTS_UNKNOWN")
    return BXMDecision(verdict, "CBOE_BXM_ALL_GATES_PASS", selected)
