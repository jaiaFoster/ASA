"""Immutable BXM knowledge with optional X05/X07/X01 lifecycle evidence."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from analytics.buywrite import cboe_buywrite_daily_return
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
    IndexDividendPoints,
    IndexSettlementValue,
    MarketCapability,
    OptionChain,
    OptionTradeTape,
    UnknownReason,
)
from facts.canonical_projection import CanonicalFactRequest, canonical_fact_id
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
    prior_index_close: Decimal | None = None,
    prior_call_close: Decimal | None = None,
    current_call_close: Decimal | None = None,
    index_vwav: Decimal | None = None,
    selected_call_strike: Decimal | None = None,
    index_close: Decimal | None = None,
    bars_observation_id: str | None = None,
    option_history_observation_id: str | None = None,
) -> KnowledgeMapping[BxmPayload]:
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
    if dividend_observation is not None:
        requests.append(
            CanonicalFactRequest(
                MarketCapability.INDEX_DIVIDEND_POINTS_V1,
                dividend_observation[0],
                dividend_observation[1].points,
                subject,
                "index_dividend_points",
            )
        )
    if settlement_observation is not None:
        requests.append(
            CanonicalFactRequest(
                MarketCapability.INDEX_SETTLEMENT_VALUE_V1,
                settlement_observation[0],
                settlement_observation[1].value,
                subject,
                "index_settlement_value",
            )
        )
    scalar_inputs = (
        (
            "prior_index_close",
            prior_index_close,
            bars_observation_id,
            MarketCapability.HISTORICAL_BARS_V1,
        ),
        ("index_close", index_close, bars_observation_id, MarketCapability.HISTORICAL_BARS_V1),
        ("index_vwav", index_vwav, bars_observation_id, MarketCapability.HISTORICAL_BARS_V1),
        (
            "prior_call_close",
            prior_call_close,
            option_history_observation_id,
            MarketCapability.HISTORICAL_OPTION_PANEL_V1,
        ),
        (
            "current_call_close",
            current_call_close,
            chain_observation_id,
            MarketCapability.OPTION_CHAIN_V1,
        ),
        (
            "selected_call_strike",
            selected_call_strike,
            chain_observation_id,
            MarketCapability.OPTION_CHAIN_V1,
        ),
    )
    for fact_type, value, observation_id, capability in scalar_inputs:
        if value is not None and observation_id is not None:
            requests.append(
                CanonicalFactRequest(capability, observation_id, value, subject, fact_type)
            )

    def _compute(facts: tuple[CanonicalFact, ...]) -> tuple[DerivedFactRequest, ...]:
        requests: list[DerivedFactRequest] = []
        entry_vwap: Decimal | None = None
        if tape_observation is not None:
            value = option_trade_window_vwap(
                tape_observation[1],
                vwap_window_start,
                vwap_window_end,
                excluded_sale_condition_codes=frozenset(),
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
            roll_day=(
                roll_date is not None and new_york_time(quote_effective_time).date() == roll_date
            ),
            prior_index_close=_decimal_fact("prior_index_close"),
            prior_call_close=_decimal_fact("prior_call_close"),
            index_close=_decimal_fact("index_close"),
            call_close=_decimal_fact("current_call_close"),
            dividend_points=_decimal_fact("index_dividend_points"),
            old_strike=_decimal_fact("selected_call_strike"),
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
            dividend_observation[1]
            if dividend_observation is not None
            else UnknownReason("INDEX_DIVIDEND_POINTS_UNAVAILABLE"),
            settlement_observation[1]
            if settlement_observation is not None
            else UnknownReason("INDEX_SETTLEMENT_VALUE_UNAVAILABLE"),
            roll_date,
            daily_fact.value
            if daily_fact is not None and isinstance(daily_fact.value, Decimal)
            else UnknownReason("missing_cboe_buywrite_daily_return_input"),
        )

    return KnowledgeMapping(tuple(requests), _compute, _payload)
