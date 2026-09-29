"""Execute the frozen BXM manifest graph over sealed provider-neutral inputs."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import cast

from domain import OptionChain, OptionContract, UnknownReason
from strategies import CORE_COMPONENTS, compile_strategy_graph, execute_strategy_graph
from strategies.bxm_components import (
    BXM_PLUGIN,
    DATE,
    DECIMAL,
    INSTANT,
    OPTION_CHAIN,
    OPTIONAL_DATE,
)
from strategies.bxm_manifest import BXM_MANIFEST
from strategies.cboe_put_components import CBOE_PUT_PLUGIN
from strategies.manifest import StrategyManifest
from strategies.plugins import build_plugin_registry
from strategies.tristate_components import TRISTATE_PLUGIN, UNKNOWN
from strategies.type_system import ComponentValues, TypedValue

NO_ACTION = "NO_ACTION"
_GRAPH = compile_strategy_graph(
    BXM_MANIFEST,
    build_plugin_registry(CORE_COMPONENTS, (TRISTATE_PLUGIN, CBOE_PUT_PLUGIN, BXM_PLUGIN)),
)


@dataclass(frozen=True, slots=True)
class BXMDecision:
    verdict: str
    reason: str
    selected_call: OptionContract | None = None
    index_units: Decimal = Decimal(1)
    short_call_quantity: Decimal = Decimal(1)


def evaluate_bxm(
    *,
    decision_date: date,
    roll_date: date | UnknownReason,
    quote_effective_time: datetime,
    quote_value: Decimal,
    chain: OptionChain,
    manifest: StrategyManifest = BXM_MANIFEST,
) -> BXMDecision:
    optional_roll = None if isinstance(roll_date, UnknownReason) else roll_date
    graph = _GRAPH if manifest is BXM_MANIFEST else compile_strategy_graph(
        manifest,
        build_plugin_registry(CORE_COMPONENTS, (TRISTATE_PLUGIN, CBOE_PUT_PLUGIN, BXM_PLUGIN)),
    )
    outputs = execute_strategy_graph(
        graph,
        ComponentValues(
            (
                ("timing.decision_date", TypedValue(DATE, decision_date)),
                ("timing.roll_date", TypedValue(OPTIONAL_DATE, optional_roll)),
                ("timing.quote_effective_time", TypedValue(INSTANT, quote_effective_time)),
                ("selection.chain", TypedValue(OPTION_CHAIN, chain)),
                ("selection.reference", TypedValue(DECIMAL, quote_value)),
                ("selection.roll_date", TypedValue(OPTIONAL_DATE, optional_roll)),
            )
        ),
    ).outputs
    verdict = cast(str, outputs.get("verdict").value)
    selected = cast(OptionContract | None, outputs.get("selected_call").value)
    roll_state = cast(str, outputs.get("roll_state").value)
    reference_state = cast(str, outputs.get("reference_state").value)
    reason = (
        "G_CBOE_MONTHLY_ROLL_DATE_FAIL"
        if verdict == NO_ACTION
        else "G_CBOE_MONTHLY_ROLL_DATE_UNKNOWN"
        if roll_state == UNKNOWN
        else "G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN"
        if reference_state == UNKNOWN
        else "G_BXM_STRIKE_EXISTS_UNKNOWN"
        if selected is None
        else "CBOE_BXM_ALL_GATES_PASS"
    )
    return BXMDecision(
        verdict,
        reason,
        selected,
        cast(Decimal, outputs.get("index_units").value),
        cast(Decimal, outputs.get("short_call_quantity").value),
    )
