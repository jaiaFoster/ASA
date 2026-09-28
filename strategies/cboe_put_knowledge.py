"""Immutable canonical mapping for Cboe PUT."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from analytics.features import DerivedFactRequest, DerivedFactSet
from domain import CanonicalFact, MarketCapability, OptionChain
from facts.canonical_projection import CanonicalFactRequest
from strategies.knowledge_contracts import KnowledgeMapping


@dataclass(frozen=True, slots=True)
class CboePutPayload:
    chain: OptionChain
    spot: Decimal
    quote_effective_time: datetime


def build_cboe_put_knowledge_mapping(
    *,
    subject: str,
    quote_observation_id: str,
    chain_observation_id: str,
    chain: OptionChain,
    spot: Decimal,
    quote_effective_time: datetime,
) -> KnowledgeMapping[CboePutPayload]:
    requests = (
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
    )

    def _compute(_facts: tuple[CanonicalFact, ...]) -> tuple[DerivedFactRequest, ...]:
        return ()

    def _payload(_facts: tuple[CanonicalFact, ...], _derived: DerivedFactSet) -> CboePutPayload:
        return CboePutPayload(chain, spot, quote_effective_time)

    return KnowledgeMapping(requests, _compute, _payload)
