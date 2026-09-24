"""SPY put credit spread mapping from sealed evidence to immutable facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from analytics.features import DerivedFactRequest, DerivedFactSet
from domain import CanonicalFact, MarketCapability, OptionChain
from facts.canonical_projection import CanonicalFactRequest
from strategies.knowledge_contracts import KnowledgeMapping

FACT_UNDERLYING_PRICE = "put_credit_spread_underlying_price"
FACT_DAYS_TO_EXPIRATION = "put_credit_spread_days_to_expiration"


@dataclass(frozen=True, slots=True)
class PutCreditSpreadPayload:
    chain: OptionChain
    expiration: date
    underlying_price: Decimal
    days_to_expiration: int


def build_put_credit_spread_knowledge_mapping(
    *,
    subject: str,
    quote_observation_id: str,
    chain_observation_id: str,
    chain: OptionChain,
    expiration: date,
    underlying_price: Decimal,
    days_to_expiration: int,
) -> KnowledgeMapping[PutCreditSpreadPayload]:
    requests = (
        CanonicalFactRequest(
            MarketCapability.REAL_TIME_QUOTE_V1,
            quote_observation_id,
            underlying_price,
            subject,
            FACT_UNDERLYING_PRICE,
        ),
        CanonicalFactRequest(
            MarketCapability.OPTION_CHAIN_V1,
            chain_observation_id,
            Decimal(days_to_expiration),
            f"{subject}:{expiration.isoformat()}",
            FACT_DAYS_TO_EXPIRATION,
        ),
    )

    def _compute(facts: tuple[CanonicalFact, ...]) -> tuple[DerivedFactRequest, ...]:
        del facts
        return ()

    def _payload(
        facts: tuple[CanonicalFact, ...], derived: DerivedFactSet
    ) -> PutCreditSpreadPayload:
        del derived
        by_type = {fact.fact_type: fact for fact in facts}
        price = by_type[FACT_UNDERLYING_PRICE].value
        dte = by_type[FACT_DAYS_TO_EXPIRATION].value
        if not isinstance(price, Decimal) or not isinstance(dte, Decimal):
            raise TypeError("put credit spread canonical facts must be decimal")
        return PutCreditSpreadPayload(chain, expiration, price, int(dte))

    return KnowledgeMapping(requests, _compute, _payload)
