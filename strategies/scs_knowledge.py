"""Immutable canonical mapping for SCS."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from analytics.features import DerivedFactRequest, DerivedFactSet
from domain import CanonicalFact, MarketCapability, OptionChain
from facts.canonical_projection import CanonicalFactRequest
from strategies.knowledge_contracts import KnowledgeMapping


@dataclass(frozen=True, slots=True)
class SCSPayload:
    chain: OptionChain
    spot: Decimal
    selected_expiration: date
    rate: Decimal | None
    dividend_yield: Decimal | None


def build_scs_knowledge_mapping(
    *,
    subject: str,
    quote_observation_id: str,
    chain_observation_id: str,
    chain: OptionChain,
    spot: Decimal,
    selected_expiration: date,
) -> KnowledgeMapping[SCSPayload]:
    requests = (
        CanonicalFactRequest(
            MarketCapability.REAL_TIME_QUOTE_V1,
            quote_observation_id,
            spot,
            subject,
            "spx_close",
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

    def _payload(_facts: tuple[CanonicalFact, ...], _derived: DerivedFactSet) -> SCSPayload:
        # X04 has a canonical risk-free rate but no canonical SPX dividend-yield
        # series in the current provider topology. Both remain explicit UNKNOWN
        # rather than weakening the sourced arbitrage filter.
        return SCSPayload(chain, spot, selected_expiration, None, None)

    return KnowledgeMapping(requests, _compute, _payload)
