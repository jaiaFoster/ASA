"""Immutable BXM knowledge with optional X05/X07/X01 lifecycle evidence."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from analytics.buywrite import (
    cboe_buywrite_daily_return,
    index_session_closes,
    resolve_bxm_lifecycle_facts,
)
from analytics.calendar_facts import new_york_time
from analytics.derived_facts import (
    CBOE_BUYWRITE_DAILY_RETURN,
    THIRD_FRIDAY_ROLL_DATE,
    WINDOWED_OPTION_TRADE_VWAP,
)
from analytics.features import DerivedFactQualityStatus, DerivedFactRequest, DerivedFactSet
from analytics.option_facts import option_trade_window_vwap
from domain import (
    CanonicalFact,
    EvidenceKind,
    EvidenceReference,
    HistoricalOptionPanel,
    IndexDividendPoints,
    IndexSettlementValue,
    MarketCapability,
    OHLCVSeries,
    OptionChain,
    OptionTradeTape,
    UnknownReason,
)
from facts.canonical_projection import CanonicalFactRequest, canonical_fact_id
from strategies.bxm_manifest import bxm_parameter
from strategies.knowledge_contracts import KnowledgeMapping

_FACT_VERSION = 1


@dataclass(frozen=True, slots=True)
class BxmPayload:
    chain: OptionChain
    spot: Decimal
    quote_effective_time: datetime
    entry_vwap: Decimal | UnknownReason
    tape_contract_identity: str | None
    dividend_points: IndexDividendPoints | UnknownReason
    settlement_value: IndexSettlementValue | UnknownReason
    roll_date: date | None = None
    daily_return: Decimal | UnknownReason = UnknownReason(
        "missing_cboe_buywrite_daily_return_input"
    )
    held_call_identity: str | None = None


def build_bxm_knowledge_mapping(
    *,
    subject: str,
    snapshot_digest: str,
    quote_observation_id: str,
    chain_observation_id: str,
    chain: OptionChain,
    spot: Decimal,
    quote_effective_time: datetime,
    tape_observation: tuple[str, OptionTradeTape] | None,
    dividend_observation: tuple[str, IndexDividendPoints] | None,
    settlement_observation: tuple[str, IndexSettlementValue] | None,
    vwap_window_start: datetime,
    vwap_window_end: datetime,
    roll_date: date | None = None,
    bars_observation: tuple[str, OHLCVSeries] | None = None,
    option_history_observation: tuple[str, HistoricalOptionPanel] | None = None,
    selected_call_identity: str | None = None,
    held_call_identity: str | None = None,
) -> KnowledgeMapping[BxmPayload]:
    return_date = new_york_time(quote_effective_time).date()
    selected_call = next(
        (
            contract
            for contract in chain.contracts
            if selected_call_identity is not None and contract.identity == selected_call_identity
        ),
        None,
    )
    held_call = next(
        (
            contract
            for snapshot in (
                option_history_observation[1].snapshots
                if option_history_observation is not None
                else ()
            )
            for contract in snapshot.contracts
            if held_call_identity is not None and contract.identity == held_call_identity
        ),
        None,
    )
    roll_day = roll_date is not None and return_date == roll_date
    accounting_call = selected_call if roll_day else held_call
    accounting_call_identity = (
        accounting_call.identity if accounting_call is not None else None
    )
    valid_dividend_observation = (
        dividend_observation
        if dividend_observation is not None
        and accounting_call is not None
        and dividend_observation[1].instrument == accounting_call.underlying.instrument
        and dividend_observation[1].effective_date == return_date
        else None
    )
    valid_settlement_observation = (
        settlement_observation
        if settlement_observation is not None
        and held_call is not None
        and roll_day
        and roll_date is not None
        and held_call.expiration == roll_date
        and settlement_observation[1].index.instrument == held_call.underlying.instrument
        and settlement_observation[1].settlement_date == held_call.expiration
        and settlement_observation[1].settlement_style is held_call.settlement_style
        else None
    )
    requests = [
        CanonicalFactRequest(
            MarketCapability.REAL_TIME_QUOTE_V1,
            quote_observation_id,
            spot,
            subject,
            "spx_reference_value",
        ),
        CanonicalFactRequest(
            MarketCapability.OPTION_CHAIN_V1,
            chain_observation_id,
            chain.identity,
            subject,
            "option_chain_identity",
        ),
    ]
    if tape_observation is not None:
        requests.append(
            CanonicalFactRequest(
                MarketCapability.OPTION_TRADE_TAPE_V1,
                tape_observation[0],
                tape_observation[1].contract_identity,
                subject,
                "option_trade_tape_contract_identity",
            )
        )
    if valid_dividend_observation is not None:
        requests.append(
            CanonicalFactRequest(
                MarketCapability.INDEX_DIVIDEND_POINTS_V1,
                valid_dividend_observation[0],
                valid_dividend_observation[1].points,
                subject,
                "index_dividend_points",
            )
        )
    if valid_settlement_observation is not None:
        requests.append(
            CanonicalFactRequest(
                MarketCapability.INDEX_SETTLEMENT_VALUE_V1,
                valid_settlement_observation[0],
                valid_settlement_observation[1].value,
                subject,
                "index_settlement_value",
            )
        )
    lifecycle = (
        resolve_bxm_lifecycle_facts(
            panel=option_history_observation[1] if option_history_observation else None,
            series=bars_observation[1] if bars_observation else None,
            tape=tape_observation[1] if tape_observation else None,
            selected_contract_identity=accounting_call_identity,
            held_contract_identity=held_call_identity,
            return_date=return_date,
            roll_date=roll_date,
            window_start=vwap_window_start,
            window_end=vwap_window_end,
            excluded_sale_condition_codes=frozenset(
                str(bxm_parameter("timing", "excluded_sale_condition_codes"))
            ),
        )
        if accounting_call_identity is not None and roll_date is not None
        else None
    )
    bars_observation_id = bars_observation[0] if bars_observation else None
    option_history_observation_id = (
        option_history_observation[0] if option_history_observation else None
    )
    prior_index_close, index_close = index_session_closes(
        bars_observation[1] if bars_observation else None,
        new_york_time(quote_effective_time).date(),
    )
    scalar_inputs = (
        (
            "prior_index_close",
            prior_index_close,
            bars_observation_id,
            MarketCapability.HISTORICAL_BARS_V1,
        ),
        ("index_close", index_close, bars_observation_id, MarketCapability.HISTORICAL_BARS_V1),
        (
            "index_vwav",
            lifecycle.index_vwav if lifecycle else None,
            bars_observation_id,
            MarketCapability.HISTORICAL_BARS_V1,
        ),
        (
            "prior_call_close",
            lifecycle.prior_call_close if lifecycle else None,
            option_history_observation_id,
            MarketCapability.HISTORICAL_OPTION_PANEL_V1,
        ),
        (
            "current_call_close",
            lifecycle.current_call_close if lifecycle else None,
            option_history_observation_id,
            MarketCapability.HISTORICAL_OPTION_PANEL_V1,
        ),
        (
            "old_call_strike",
            lifecycle.old_strike if lifecycle else None,
            option_history_observation_id,
            MarketCapability.HISTORICAL_OPTION_PANEL_V1,
        ),
    )
    for fact_type, value, observation_id, capability in scalar_inputs:
        if isinstance(value, Decimal) and observation_id is not None:
            requests.append(
                CanonicalFactRequest(capability, observation_id, value, subject, fact_type)
            )

    def _compute(facts: tuple[CanonicalFact, ...]) -> tuple[DerivedFactRequest, ...]:
        requests: list[DerivedFactRequest] = []
        entry_vwap: Decimal | None = None
        if tape_observation is not None:
            value = (
                lifecycle.entry_price
                if lifecycle
                else option_trade_window_vwap(
                    tape_observation[1],
                    vwap_window_start,
                    vwap_window_end,
                    excluded_sale_condition_codes=frozenset(),
                )
            )
            if isinstance(value, Decimal):
                entry_vwap = value
                tape_fact_id = canonical_fact_id(
                    "option_trade_tape_contract_identity", subject, snapshot_digest
                )
                requests.append(
                    DerivedFactRequest(
                        WINDOWED_OPTION_TRADE_VWAP,
                        subject,
                        value,
                        "USD_per_option_unit",
                        (
                            EvidenceReference(
                                EvidenceKind.CANONICAL_FACT, tape_fact_id, _FACT_VERSION
                            ),
                        ),
                        DerivedFactQualityStatus.VALID,
                        (
                            ("window_end", vwap_window_end.isoformat()),
                            ("window_start", vwap_window_start.isoformat()),
                        ),
                    )
                )
        evidence = tuple(
            EvidenceReference(EvidenceKind.CANONICAL_FACT, fact.fact_id, fact.version)
            for fact in facts
        )
        by_type = {fact.fact_type: fact.value for fact in facts}

        def _decimal_fact(name: str) -> Decimal | None:
            value = by_type.get(name)
            return value if isinstance(value, Decimal) else None

        daily = cboe_buywrite_daily_return(
            roll_day=roll_day,
            prior_index_close=_decimal_fact("prior_index_close"),
            prior_call_close=_decimal_fact("prior_call_close"),
            index_close=_decimal_fact("index_close"),
            call_close=_decimal_fact("current_call_close"),
            dividend_points=_decimal_fact("index_dividend_points"),
            old_strike=_decimal_fact("old_call_strike"),
            settlement_value=_decimal_fact("index_settlement_value"),
            index_vwav=_decimal_fact("index_vwav"),
            call_vwap=entry_vwap,
        )
        if isinstance(daily, Decimal):
            requests.append(
                DerivedFactRequest(
                    CBOE_BUYWRITE_DAILY_RETURN,
                    subject,
                    daily,
                    "simple_daily_return",
                    evidence,
                    DerivedFactQualityStatus.VALID,
                )
            )
        if roll_date is not None:
            requests.append(
                DerivedFactRequest(
                    THIRD_FRIDAY_ROLL_DATE,
                    subject,
                    roll_date,
                    "date",
                    evidence,
                    DerivedFactQualityStatus.VALID,
                )
            )
        return tuple(requests)

    def _payload(_facts: tuple[CanonicalFact, ...], derived: DerivedFactSet) -> BxmPayload:
        vwap_fact = next(
            (
                item
                for item in derived.facts
                if item.derived_fact_id.startswith(f"{WINDOWED_OPTION_TRADE_VWAP}:")
            ),
            None,
        )
        entry_vwap: Decimal | UnknownReason = (
            vwap_fact.value
            if vwap_fact is not None and isinstance(vwap_fact.value, Decimal)
            else UnknownReason(
                "OPTION_TRADE_TAPE_UNAVAILABLE"
                if tape_observation is None
                else "NO_ELIGIBLE_OPTION_TRADES_IN_VWAP_WINDOW"
            )
        )
        daily_fact = next(
            (
                item
                for item in derived.facts
                if item.derived_fact_id.startswith(f"{CBOE_BUYWRITE_DAILY_RETURN}:")
            ),
            None,
        )
        return BxmPayload(
            chain,
            spot,
            quote_effective_time,
            entry_vwap,
            tape_observation[1].contract_identity if tape_observation is not None else None,
            valid_dividend_observation[1]
            if valid_dividend_observation is not None
            else UnknownReason(
                "INDEX_DIVIDEND_POINTS_UNAVAILABLE"
                if dividend_observation is None
                else "INDEX_DIVIDEND_POINTS_LIFECYCLE_MISMATCH"
            ),
            valid_settlement_observation[1]
            if valid_settlement_observation is not None
            else UnknownReason(
                "INDEX_SETTLEMENT_VALUE_UNAVAILABLE"
                if settlement_observation is None
                else "INDEX_SETTLEMENT_VALUE_LIFECYCLE_MISMATCH"
            ),
            roll_date,
            daily_fact.value
            if daily_fact is not None and isinstance(daily_fact.value, Decimal)
            else UnknownReason("missing_cboe_buywrite_daily_return_input"),
            held_call_identity,
        )

    return KnowledgeMapping(tuple(requests), _compute, _payload)
