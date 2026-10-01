"""Registered BXM policy components driven solely by manifest parameters."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import cast

from analytics.calendar_facts import new_york_time
from domain import OptionChain, OptionContract, OptionType, SettlementStyle
from strategies.components import (
    BaseComponent,
    ComponentCategory,
    ComponentDefinition,
    ParameterDefinition,
    PortDefinition,
)
from strategies.manifest import ManifestObject
from strategies.plugins import PluginMetadata, StrategyPlugin
from strategies.tristate_components import FAIL, PASS, TRISTATE, UNKNOWN
from strategies.type_system import ComponentValues, StrategyTypeReference, TypedValue

DATE = StrategyTypeReference("Date", "1.0.0")
INSTANT = StrategyTypeReference("Instant", "1.0.0")
DECIMAL = StrategyTypeReference("Decimal", "1.0.0")
TEXT = StrategyTypeReference("Text", "1.0.0")
OPTION_CHAIN = StrategyTypeReference("OptionChain", "1.0.0")
OPTION_CONTRACT = StrategyTypeReference("OptionContract", "1.0.0")
OPTIONAL_DATE = StrategyTypeReference("Optional", "1.0.0", (DATE,))
OPTIONAL_OPTION_CONTRACT = StrategyTypeReference("Optional", "1.0.0", (OPTION_CONTRACT,))


def _clock(value: object, name: str) -> time:
    try:
        parsed = time.fromisoformat(cast(str, value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an ISO local time") from exc
    if parsed.tzinfo is not None:
        raise ValueError(f"{name} must be an unzoned exchange-local time")
    return parsed


class BxmEntryTiming(BaseComponent):  # type: ignore[misc]
    __slots__ = ()
    definition = ComponentDefinition(
        "asa.bxm",
        "entry_timing",
        "1.0.0",
        ComponentCategory.PREDICATE,
        (
            PortDefinition("decision_date", DATE),
            PortDefinition("roll_date", OPTIONAL_DATE),
            PortDefinition("quote_effective_time", INSTANT),
        ),
        (
            PortDefinition("roll_state", TRISTATE),
            PortDefinition("reference_state", TRISTATE),
        ),
        (
            ParameterDefinition("reference_time_et", TEXT),
            ParameterDefinition("vwap_window_start_et", TEXT),
            ParameterDefinition("vwap_window_end_et", TEXT),
            ParameterDefinition("excluded_sale_condition_codes", TEXT),
        ),
        explanation_template=ManifestObject((("operation", "bxm_entry_timing"),)),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        decision_date = cast(date, inputs.get("decision_date").value)
        roll_date = cast(date | None, inputs.get("roll_date").value)
        observed = new_york_time(cast(datetime, inputs.get("quote_effective_time").value))
        reference_time = _clock(parameters.get("reference_time_et").value, "reference_time_et")
        start = _clock(parameters.get("vwap_window_start_et").value, "vwap_window_start_et")
        end = _clock(parameters.get("vwap_window_end_et").value, "vwap_window_end_et")
        excluded = cast(str, parameters.get("excluded_sale_condition_codes").value)
        if not excluded or len(excluded) != len(set(excluded)):
            raise ValueError("BXM excluded sale-condition codes must be unique")
        if not reference_time < start < end:
            raise ValueError("BXM reference/VWAP times must be strictly ordered")
        roll_state = UNKNOWN if roll_date is None else PASS if decision_date == roll_date else FAIL
        reference_state = (
            PASS
            if roll_date is not None
            and observed.date() == roll_date
            and observed.time().replace(tzinfo=None) < reference_time
            else UNKNOWN
        )
        return ComponentValues(
            (
                ("roll_state", TypedValue(TRISTATE, roll_state)),
                ("reference_state", TypedValue(TRISTATE, reference_state)),
            )
        )


class BxmCallSelection(BaseComponent):  # type: ignore[misc]
    __slots__ = ()
    definition = ComponentDefinition(
        "asa.bxm",
        "call_selection",
        "1.0.0",
        ComponentCategory.PROPOSAL,
        (
            PortDefinition("chain", OPTION_CHAIN),
            PortDefinition("reference", DECIMAL),
            PortDefinition("roll_date", OPTIONAL_DATE),
        ),
        (
            PortDefinition("selected_call", OPTIONAL_OPTION_CONTRACT),
            PortDefinition("strike_state", TRISTATE),
        ),
        (
            ParameterDefinition("contract_root", TEXT),
            ParameterDefinition("settlement_style", TEXT),
            ParameterDefinition("expiration_month_offset", DECIMAL),
            ParameterDefinition("strike_operator", TEXT),
        ),
        explanation_template=ManifestObject((("operation", "bxm_call_selection"),)),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        chain = cast(OptionChain, inputs.get("chain").value)
        reference = cast(Decimal, inputs.get("reference").value)
        roll_date = cast(date | None, inputs.get("roll_date").value)
        root = cast(str, parameters.get("contract_root").value)
        settlement = SettlementStyle(cast(str, parameters.get("settlement_style").value))
        month_offset = cast(Decimal, parameters.get("expiration_month_offset").value)
        operator = cast(str, parameters.get("strike_operator").value)
        if month_offset != month_offset.to_integral_value() or month_offset <= 0:
            raise ValueError("expiration_month_offset must be a positive integer")
        if operator != ">=":
            raise ValueError("unsupported BXM strike operator")
        selected: OptionContract | None = None
        if roll_date is not None:
            year, month = roll_date.year, roll_date.month
            for _ in range(int(month_offset)):
                year, month = (year + 1, 1) if month == 12 else (year, month + 1)
            candidates = tuple(
                item
                for item in chain.contracts
                if item.option_type is OptionType.CALL
                and item.root == root
                and item.settlement_style is settlement
                and (item.expiration.year, item.expiration.month) == (year, month)
                and item.strike >= reference
            )
            selected = min(candidates, key=lambda item: (item.strike, item.identity), default=None)
        return ComponentValues(
            (
                ("selected_call", TypedValue(OPTIONAL_OPTION_CONTRACT, selected)),
                ("strike_state", TypedValue(TRISTATE, PASS if selected is not None else UNKNOWN)),
            )
        )


BXM_PLUGIN = StrategyPlugin(
    PluginMetadata("asa.bxm", "bxm_components", "1.0.0", "Manifest-driven BXM policy."),
    (BxmEntryTiming(), BxmCallSelection()),
)
