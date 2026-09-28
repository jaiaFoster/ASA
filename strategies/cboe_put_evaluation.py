"""Frozen source rules for one Cboe PUT roll decision."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from domain import OptionChain, OptionContract, OptionType, SettlementStyle, UnknownReason
from strategies import CORE_COMPONENTS, compile_strategy_graph, execute_strategy_graph
from strategies.cboe_put_components import CBOE_PUT_PLUGIN
from strategies.cboe_put_manifest import CBOE_PUT_MANIFEST
from strategies.plugins import build_plugin_registry
from strategies.tristate_components import FAIL, PASS, TRISTATE, TRISTATE_PLUGIN, UNKNOWN
from strategies.type_system import ComponentValues, TypedValue

NO_ACTION = "NO_ACTION"
_GRAPH = compile_strategy_graph(
    CBOE_PUT_MANIFEST, build_plugin_registry(CORE_COMPONENTS, (TRISTATE_PLUGIN, CBOE_PUT_PLUGIN))
)


@dataclass(frozen=True, slots=True)
class CboePutDecision:
    verdict: str
    reason: str
    selected_put: OptionContract | None = None


@dataclass(frozen=True, slots=True)
class PutwriteStrikePolicy:
    fraction: Decimal
    comparator: str
    unknown_reason: str
    pass_reason: str


PUT_STRIKE_POLICY = PutwriteStrikePolicy(
    Decimal(1), "lte", "G_PUT_STRIKE_EXISTS_UNKNOWN", "CBOE_PUT_ALL_GATES_PASS"
)


def evaluate_cboe_put(
    *,
    decision_date: date,
    roll_date: date | UnknownReason,
    reference_state: str,
    quote_value: Decimal | None,
    chain: OptionChain | None,
    strike_policy: PutwriteStrikePolicy = PUT_STRIKE_POLICY,
) -> CboePutDecision:
    if reference_state not in (PASS, UNKNOWN):
        raise ValueError("reference_state must be PASS or UNKNOWN")
    if isinstance(roll_date, UnknownReason):
        roll_state = UNKNOWN
    else:
        roll_state = PASS if decision_date == roll_date else FAIL
    if roll_state == FAIL:
        return CboePutDecision(NO_ACTION, "G_CBOE_MONTHLY_ROLL_DATE_FAIL")
    if roll_state == UNKNOWN:
        return CboePutDecision(UNKNOWN, "G_CBOE_MONTHLY_ROLL_DATE_UNKNOWN")
    assert isinstance(roll_date, date)
    next_year, next_month = (
        (roll_date.year + 1, 1) if roll_date.month == 12 else (roll_date.year, roll_date.month + 1)
    )
    candidates = (
        ()
        if chain is None or quote_value is None
        else tuple(
            item
            for item in chain.contracts
            if item.option_type is OptionType.PUT
            and item.root == "SPX"
            and item.settlement_style is SettlementStyle.AM
            and (item.expiration.year, item.expiration.month) == (next_year, next_month)
            and (
                item.strike < quote_value * strike_policy.fraction
                if strike_policy.comparator == "lt"
                else item.strike <= quote_value * strike_policy.fraction
            )
        )
    )
    selected = max(candidates, key=lambda item: item.strike) if candidates else None
    strike_state = PASS if selected is not None else UNKNOWN
    outputs = execute_strategy_graph(
        _GRAPH,
        ComponentValues(
            (
                ("entry_gates.left", TypedValue(TRISTATE, reference_state)),
                ("entry_gates.right", TypedValue(TRISTATE, strike_state)),
                ("verdict.roll_date", TypedValue(TRISTATE, roll_state)),
            )
        ),
    ).outputs
    verdict = str(outputs.get("verdict").value)
    if reference_state == UNKNOWN:
        return CboePutDecision(verdict, "G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN")
    if strike_state == UNKNOWN:
        return CboePutDecision(verdict, strike_policy.unknown_reason)
    return CboePutDecision(verdict, strike_policy.pass_reason, selected)
