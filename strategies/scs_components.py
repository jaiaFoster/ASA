"""Manifest-driven Santa-Clara/Saretto policy components."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import cast

from analytics.margin import cboe_naked_option_margin, cboe_short_straddle_margin
from domain import OptionChain, OptionContract, OptionType, SettlementStyle, UnknownReason
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
OPTIONAL_DECIMAL = StrategyTypeReference("Optional", "1.0.0", (DECIMAL,))
OPTIONAL_OPTION_CONTRACT = StrategyTypeReference("Optional", "1.0.0", (OPTION_CONTRACT,))


def select_monthly_expiration(
    candidates: tuple[tuple[date, int, bool], ...], target_days: int, cycle: str
) -> date | UnknownReason:
    if cycle != "standard_monthly":
        raise ValueError("unsupported SCS expiration cycle")
    eligible = tuple((day, dte) for day, dte, monthly in candidates if monthly)
    if not eligible:
        return UnknownReason("G_SCS_EXPIRY_UNIQUE_UNKNOWN")
    distance = {day: abs(dte - target_days) for day, dte in eligible}
    minimum = min(distance.values())
    selected = tuple(sorted(day for day, value in distance.items() if value == minimum))
    return selected[0] if len(selected) == 1 else UnknownReason("AMBIGUOUS_SELECTION")


def _mid(contract: OptionContract) -> Decimal | None:
    if contract.bid is None or contract.ask is None:
        return None
    return (contract.bid + contract.ask) / Decimal(2)


class ScsPolicy(BaseComponent):  # type: ignore[misc]
    __slots__ = ()
    definition = ComponentDefinition(
        "asa.scs",
        "policy",
        "1.0.0",
        ComponentCategory.PROPOSAL,
        (
            PortDefinition("decision_time", INSTANT),
            PortDefinition("quote_effective_time", INSTANT),
            PortDefinition("first_trading_day", DATE),
            PortDefinition("session_close", INSTANT),
            PortDefinition("selected_expiration", DATE),
            PortDefinition("spot", DECIMAL),
            PortDefinition("chain", OPTION_CHAIN),
            PortDefinition("rate", OPTIONAL_DECIMAL),
            PortDefinition("dividend_yield", OPTIONAL_DECIMAL),
        ),
        (
            PortDefinition("entry_state", TRISTATE),
            PortDefinition("pair_state", TRISTATE),
            PortDefinition("selected_call", OPTIONAL_OPTION_CONTRACT),
            PortDefinition("selected_put", OPTIONAL_OPTION_CONTRACT),
            PortDefinition("selection_reason", TEXT),
            PortDefinition("call_naked_margin", OPTIONAL_DECIMAL),
            PortDefinition("put_naked_margin", OPTIONAL_DECIMAL),
            PortDefinition("straddle_margin", OPTIONAL_DECIMAL),
            PortDefinition("margin_reason", TEXT),
        ),
        (
            ParameterDefinition("target_dte_calendar_days", DECIMAL),
            ParameterDefinition("expiration_cycle", TEXT),
            ParameterDefinition("contract_root", TEXT),
            ParameterDefinition("settlement_style", TEXT),
            ParameterDefinition("minimum_iv", DECIMAL),
            ParameterDefinition("maximum_iv", DECIMAL),
            ParameterDefinition("low_price_boundary", DECIMAL),
            ParameterDefinition("low_price_minimum_spread", DECIMAL),
            ParameterDefinition("high_price_minimum_spread", DECIMAL),
            ParameterDefinition("risk_free_series", TEXT),
            ParameterDefinition("dividend_yield_series", TEXT),
            ParameterDefinition("exit_policy", TEXT),
            ParameterDefinition("margin_alpha", DECIMAL),
            ParameterDefinition("margin_beta", DECIMAL),
        ),
        explanation_template=ManifestObject((("operation", "scs_policy"),)),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        decision_time = cast(datetime, inputs.get("decision_time").value)
        quote_time = cast(datetime, inputs.get("quote_effective_time").value)
        first_trading_day = cast(date, inputs.get("first_trading_day").value)
        session_close = cast(datetime, inputs.get("session_close").value)
        expiration = cast(date, inputs.get("selected_expiration").value)
        spot = cast(Decimal, inputs.get("spot").value)
        chain = cast(OptionChain, inputs.get("chain").value)
        rate = cast(Decimal | None, inputs.get("rate").value)
        dividend = cast(Decimal | None, inputs.get("dividend_yield").value)
        entry_state = (
            FAIL
            if first_trading_day != decision_time.date() or decision_time < session_close
            else UNKNOWN
            if quote_time < session_close
            else PASS
        )
        root = cast(str, parameters.get("contract_root").value)
        settlement = SettlementStyle(cast(str, parameters.get("settlement_style").value))
        exact_contracts = tuple(
            item
            for item in chain.contracts
            if item.expiration == expiration
            and item.root == root
            and item.settlement_style is settlement
        )
        exact_by_strike = {
            strike: (
                tuple(
                    item
                    for item in exact_contracts
                    if item.strike == strike and item.option_type is OptionType.CALL
                ),
                tuple(
                    item
                    for item in exact_contracts
                    if item.strike == strike and item.option_type is OptionType.PUT
                ),
            )
            for strike in {item.strike for item in exact_contracts}
        }
        paired = tuple(
            sorted(
                strike
                for strike, (calls, puts) in exact_by_strike.items()
                if len(calls) == 1 and len(puts) == 1
            )
        )
        selected_call: OptionContract | None = None
        selected_put: OptionContract | None = None
        pair_state = UNKNOWN
        selection_reason = "G_SCS_STRIKE_UNIQUE_UNKNOWN"
        if paired:
            distances = {strike: abs(strike - spot) for strike in paired}
            minimum = min(distances.values())
            strikes = tuple(strike for strike in paired if distances[strike] == minimum)
            if len(strikes) == 1:
                strike = strikes[0]
                selected_call = exact_by_strike[strike][0][0]
                selected_put = exact_by_strike[strike][1][0]
                selection_reason = "G_SCS_QUOTE_FILTERS_UNKNOWN"
                if rate is not None and dividend is not None:
                    states = tuple(
                        self._filter(item, spot, rate, dividend, decision_time.date(), parameters)
                        for item in (selected_call, selected_put)
                    )
                    pair_state = PASS if all(states) else UNKNOWN
                    selection_reason = (
                        "SCS_ALL_GATES_PASS"
                        if pair_state == PASS
                        else "G_SCS_QUOTE_FILTERS_UNKNOWN"
                    )
            else:
                selection_reason = "AMBIGUOUS_SELECTION"
        call_margin: Decimal | None = None
        put_margin: Decimal | None = None
        straddle_margin: Decimal | None = None
        margin_reason = "G_SCS_MARGIN_UNKNOWN"
        if selected_call is not None and selected_put is not None:
            call_value = _mid(selected_call)
            put_value = _mid(selected_put)
            alpha = cast(Decimal, parameters.get("margin_alpha").value)
            beta = cast(Decimal, parameters.get("margin_beta").value)
            call_result = cboe_naked_option_margin(
                option_type=OptionType.CALL,
                option_value=call_value,
                spot=spot,
                strike=selected_call.strike,
                alpha=alpha,
                beta=beta,
            )
            put_result = cboe_naked_option_margin(
                option_type=OptionType.PUT,
                option_value=put_value,
                spot=spot,
                strike=selected_put.strike,
                alpha=alpha,
                beta=beta,
            )
            combined = cboe_short_straddle_margin(
                call_margin=call_result,
                put_margin=put_result,
                call_value=call_value,
                put_value=put_value,
            )
            if not isinstance(call_result, UnknownReason):
                call_margin = call_result
            if not isinstance(put_result, UnknownReason):
                put_margin = put_result
            if not isinstance(combined, UnknownReason):
                straddle_margin = combined
                margin_reason = "SCS_MARGIN_RESOLVED"
        return ComponentValues(
            (
                ("entry_state", TypedValue(TRISTATE, entry_state)),
                ("pair_state", TypedValue(TRISTATE, pair_state)),
                ("selected_call", TypedValue(OPTIONAL_OPTION_CONTRACT, selected_call)),
                ("selected_put", TypedValue(OPTIONAL_OPTION_CONTRACT, selected_put)),
                ("selection_reason", TypedValue(TEXT, selection_reason)),
                ("call_naked_margin", TypedValue(OPTIONAL_DECIMAL, call_margin)),
                ("put_naked_margin", TypedValue(OPTIONAL_DECIMAL, put_margin)),
                ("straddle_margin", TypedValue(OPTIONAL_DECIMAL, straddle_margin)),
                ("margin_reason", TypedValue(TEXT, margin_reason)),
            )
        )

    @staticmethod
    def _filter(
        contract: OptionContract,
        spot: Decimal,
        rate: Decimal,
        dividend: Decimal,
        as_of: date,
        parameters: ComponentValues,
    ) -> bool:
        if (
            contract.bid is None
            or contract.ask is None
            or contract.implied_volatility is None
            or contract.bid <= 0
            or contract.ask < contract.bid
        ):
            return False
        mid = _mid(contract)
        assert mid is not None
        boundary = cast(Decimal, parameters.get("low_price_boundary").value)
        spread = (
            cast(Decimal, parameters.get("low_price_minimum_spread").value)
            if mid < boundary
            else cast(Decimal, parameters.get("high_price_minimum_spread").value)
        )
        if contract.ask - contract.bid < spread:
            return False
        if (
            not cast(Decimal, parameters.get("minimum_iv").value)
            <= contract.implied_volatility
            <= cast(Decimal, parameters.get("maximum_iv").value)
        ):
            return False
        tau = Decimal((contract.expiration - as_of).days) / Decimal(365)
        ds, dk = spot * (-tau * dividend).exp(), contract.strike * (-tau * rate).exp()
        lower, upper = (ds - dk, ds) if contract.option_type is OptionType.CALL else (dk - ds, dk)
        return max(Decimal(0), lower) < mid < upper


SCS_PLUGIN = StrategyPlugin(
    PluginMetadata("asa.scs", "scs_components", "1.0.0", "Manifest-driven SCS policy."),
    (ScsPolicy(),),
)
