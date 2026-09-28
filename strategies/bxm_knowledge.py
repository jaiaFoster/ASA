"""Immutable BXM knowledge with optional X05/X07/X01 lifecycle evidence."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from analytics.derived_facts import WINDOWED_OPTION_TRADE_VWAP
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

    def _compute(facts: tuple[CanonicalFact, ...]) -> tuple[DerivedFactRequest, ...]:
        if tape_observation is None:
            return ()
        value = option_trade_window_vwap(
            tape_observation[1],
            vwap_window_start,
            vwap_window_end,
            excluded_sale_condition_codes=frozenset(),
        )
        if isinstance(value, UnknownReason):
            return ()
        tape_fact_id = canonical_fact_id(
            "option_trade_tape_contract_identity", subject, snapshot_digest
        )
        return (
            DerivedFactRequest(
                WINDOWED_OPTION_TRADE_VWAP,
                subject,
                value,
                "USD_per_option_unit",
                (EvidenceReference(EvidenceKind.CANONICAL_FACT, tape_fact_id, _FACT_VERSION),),
                DerivedFactQualityStatus.VALID,
                (
                    ("window_end", vwap_window_end.isoformat()),
                    ("window_start", vwap_window_start.isoformat()),
                ),
            ),
        )

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
        )

    return KnowledgeMapping(tuple(requests), _compute, _payload)
