"""Immutable canonical mapping for one GXZ decision input."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from analytics.features import DerivedFactRequest, DerivedFactSet
from domain import CanonicalFact, EarningsEvent, MarketCapability, OptionChain
from facts.canonical_projection import CanonicalFactRequest
from strategies.knowledge_contracts import KnowledgeMapping


@dataclass(frozen=True, slots=True)
class GXZPayload:
    chain: OptionChain
    event: EarningsEvent
    spot: Decimal
    entry_date: date


def build_gxz_knowledge_mapping(
    *,
    subject: str,
    quote_observation_id: str,
    earnings_observation_id: str,
    chain_observation_id: str,
    chain: OptionChain,
    event: EarningsEvent,
    spot: Decimal,
    entry_date: date,
) -> KnowledgeMapping[GXZPayload]:
    requests = (
        CanonicalFactRequest(
            MarketCapability.REAL_TIME_QUOTE_V1, quote_observation_id, spot, subject, "spot_price"
        ),
        CanonicalFactRequest(
            MarketCapability.EARNINGS_CALENDAR_V1,
            earnings_observation_id,
            event.earnings_date.isoformat(),
            subject,
            "earnings_date",
        ),
        CanonicalFactRequest(
            MarketCapability.EARNINGS_CALENDAR_V1,
            earnings_observation_id,
            event.confirmed,
            subject,
            "earnings_confirmed",
        ),
        CanonicalFactRequest(
            MarketCapability.OPTION_CHAIN_V1,
            chain_observation_id,
            chain.identity,
            subject,
            "option_chain_identity",
        ),
    )

    def _compute(_facts: tuple[CanonicalFact, ...]) -> tuple[DerivedFactRequest, ...]:
        return ()

    def _payload(_facts: tuple[CanonicalFact, ...], _derived: DerivedFactSet) -> GXZPayload:
        return GXZPayload(chain, event, spot, entry_date)

    return KnowledgeMapping(requests, _compute, _payload)
