"""Provider-neutral staged demands for the Cboe BXM methodology."""

from datetime import date, datetime, timedelta
from typing import Mapping  # noqa: UP035

from analytics.calendar_facts import new_york_time
from domain import (
    CapabilityDemand,
    DemandExpansion,
    MarketCapability,
    OptionChain,
    Quote,
    ResolvedCapabilityEvidence,
    UnknownReason,
)
from strategies.bxm_evaluation import evaluate_bxm
from strategies.bxm_manifest import bxm_parameter
from strategies.cboe_put_planning import (
    expand_demands as expand_monthly_chain_demands,
)
from strategies.cboe_put_planning import (
    expirations_demand,
    quote_demand,
)


def trade_tape_demand(now: datetime, contract_identity: str) -> CapabilityDemand:
    local = new_york_time(now)
    start = datetime.strptime(
        str(bxm_parameter("timing", "vwap_window_start_et")), "%H:%M:%S"
    ).time()
    end = datetime.strptime(str(bxm_parameter("timing", "vwap_window_end_et")), "%H:%M:%S").time()
    window_start = local.replace(
        hour=start.hour, minute=start.minute, second=start.second, microsecond=0
    )
    window_end = local.replace(hour=end.hour, minute=end.minute, second=end.second, microsecond=0)
    return CapabilityDemand(
        MarketCapability.OPTION_TRADE_TAPE_V1,
        ("contract_identity", "event_time", "price", "sale_condition_codes", "size"),
        window_start,
        window_end,
        required=False,
        contract_identity=contract_identity,
    )


def dividend_points_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.INDEX_DIVIDEND_POINTS_V1,
        ("effective_date", "points"),
        now - timedelta(days=35),
        now,
        required=False,
    )


def settlement_value_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.INDEX_SETTLEMENT_VALUE_V1,
        ("observed_at", "settlement_date", "settlement_style", "value"),
        now - timedelta(days=35),
        now,
        required=False,
    )


def historical_bars_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.HISTORICAL_BARS_V1,
        ("close", "volume"),
        now - timedelta(days=10),
        now,
        required=False,
    )


def historical_option_panel_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.HISTORICAL_OPTION_PANEL_V1,
        ("contracts", "observed_at"),
        now - timedelta(days=10),
        now,
        required=False,
    )


def bootstrap_demands(now: datetime) -> tuple[CapabilityDemand, ...]:
    return (
        quote_demand(now),
        expirations_demand(now),
        dividend_points_demand(now),
        settlement_value_demand(now),
        historical_bars_demand(now),
        historical_option_panel_demand(now),
    )


def expand_demands(
    evidence: Mapping[str, ResolvedCapabilityEvidence], *, now: datetime
) -> DemandExpansion:
    expanded = expand_monthly_chain_demands(evidence, now=now)
    return DemandExpansion(expanded.demands, expanded.selections, expanded.unknown_reasons)


def expand_post_selection_demands(
    evidence: Mapping[str, ResolvedCapabilityEvidence],
    selections: tuple[tuple[str, object], ...],
    *,
    now: datetime,
    roll_date: date | UnknownReason,
) -> DemandExpansion:
    """Request X05 only after the manifest-driven exact call exists."""
    expiration_text = dict(selections).get("expiration")
    if not isinstance(expiration_text, str):
        return DemandExpansion()
    from strategies.cboe_put_planning import chain_demand

    quote = evidence.get(quote_demand(now).demand_id)
    chain = evidence.get(chain_demand(now, date.fromisoformat(expiration_text)).demand_id)
    if (
        quote is None
        or chain is None
        or not isinstance(quote.value, Quote)
        or quote.value.last is None
        or not isinstance(chain.value, OptionChain)
    ):
        return DemandExpansion()
    decision = evaluate_bxm(
        decision_date=new_york_time(now).date(),
        roll_date=roll_date,
        quote_effective_time=now,
        quote_value=quote.value.last,
        chain=chain.value,
    )
    if decision.selected_call is None:
        return DemandExpansion(
            selections=()
            if isinstance(roll_date, UnknownReason)
            else (("roll_date", roll_date.isoformat()),)
        )
    tape = trade_tape_demand(now, decision.selected_call.identity)
    return DemandExpansion(
        demands=(tape,),
        selections=(
            ("roll_date", roll_date.isoformat()),
            ("selected_call_identity", decision.selected_call.identity),
            ("trade_tape_demand_id", tape.demand_id),
        ),
    )


def resolved_field_requirements() -> dict[MarketCapability, tuple[tuple[str, ...], int]]:
    return {
        MarketCapability.REAL_TIME_QUOTE_V1: (("last",), 3600),
        MarketCapability.OPTION_CHAIN_V1: (("contracts",), 3600),
        MarketCapability.OPTION_TRADE_TAPE_V1: (
            ("contract_identity", "event_time", "price", "sale_condition_codes", "size"),
            86400,
        ),
        MarketCapability.INDEX_DIVIDEND_POINTS_V1: (("effective_date", "points"), 86400 * 35),
        MarketCapability.INDEX_SETTLEMENT_VALUE_V1: (
            ("observed_at", "settlement_date", "settlement_style", "value"),
            86400 * 35,
        ),
        MarketCapability.HISTORICAL_BARS_V1: (("close", "volume"), 86400 * 10),
        MarketCapability.HISTORICAL_OPTION_PANEL_V1: (
            ("contracts", "observed_at"),
            86400 * 10,
        ),
    }
