"""Immutable canonical/derived knowledge mapping for Zhan SP-05C."""

from __future__ import annotations

from decimal import Decimal

from analytics.derived_facts import NEGATIVE_LOG_PRICE, compute_negative_log_price
from analytics.features import DerivedFactQualityStatus, DerivedFactRequest, DerivedFactSet
from domain import (
    CanonicalFact,
    EvidenceKind,
    EvidenceReference,
    MarketCapability,
    OptionChain,
    SecurityMasterRecord,
)
from facts.canonical_projection import CanonicalFactRequest, canonical_fact_id
from strategies.knowledge_contracts import KnowledgeMapping
from strategies.zhan_portfolio import ZhanSubjectCandidate

FACT_PRICE = "zhan_formation_price"
FACT_SECURITY_TYPE = "security_type"
FACT_SHARES_OUTSTANDING = "shares_outstanding"
FACT_RISK_FREE_RATE = "risk_free_rate"
FACT_OPTION_CHAIN_IDENTITY = "option_chain_identity"


def build_zhan_knowledge_mapping(
    *,
    subject: str,
    snapshot_digest: str,
    bars_observation_id: str,
    spot: Decimal,
    security_observation_id: str,
    security: SecurityMasterRecord,
    rate_observation_id: str,
    risk_free_rate: Decimal,
    chain_observation_id: str,
    chain: OptionChain,
    formation_date_state: str,
) -> KnowledgeMapping[ZhanSubjectCandidate]:
    price_fact_id = canonical_fact_id(FACT_PRICE, subject, snapshot_digest)
    requests = (
        CanonicalFactRequest(
            MarketCapability.HISTORICAL_BARS_V1,
            bars_observation_id,
            spot,
            subject,
            FACT_PRICE,
        ),
        CanonicalFactRequest(
            MarketCapability.SECURITY_MASTER_V1,
            security_observation_id,
            security.security_type.value,
            subject,
            FACT_SECURITY_TYPE,
        ),
        CanonicalFactRequest(
            MarketCapability.SECURITY_MASTER_V1,
            security_observation_id,
            security.shares_outstanding,
            subject,
            FACT_SHARES_OUTSTANDING,
        ),
        CanonicalFactRequest(
            MarketCapability.RATE_OBSERVATION_V1,
            rate_observation_id,
            risk_free_rate,
            subject,
            FACT_RISK_FREE_RATE,
        ),
        CanonicalFactRequest(
            MarketCapability.OPTION_CHAIN_V1,
            chain_observation_id,
            chain.identity,
            subject,
            FACT_OPTION_CHAIN_IDENTITY,
        ),
    )

    def _compute(facts: tuple[CanonicalFact, ...]) -> tuple[DerivedFactRequest, ...]:
        by_type = {fact.fact_type: fact for fact in facts}
        value = by_type[FACT_PRICE].value
        if not isinstance(value, Decimal):
            raise TypeError("Zhan price canonical fact must be decimal")
        return (
            DerivedFactRequest(
                NEGATIVE_LOG_PRICE,
                subject,
                compute_negative_log_price(value),
                "decimal",
                (EvidenceReference(EvidenceKind.CANONICAL_FACT, price_fact_id, 1),),
                DerivedFactQualityStatus.VALID,
            ),
        )

    def _payload(facts: tuple[CanonicalFact, ...], derived: DerivedFactSet) -> ZhanSubjectCandidate:
        by_type = {fact.fact_type: fact for fact in facts}
        price = by_type[FACT_PRICE].value
        shares = by_type[FACT_SHARES_OUTSTANDING].value
        rate = by_type[FACT_RISK_FREE_RATE].value
        if not all(isinstance(item, Decimal) for item in (price, shares, rate)):
            raise TypeError("Zhan price, shares, and rate facts must be decimal")
        assert isinstance(price, Decimal)
        assert isinstance(shares, Decimal)
        assert isinstance(rate, Decimal)
        negative_log_price = derived.get(
            next(
                item.derived_fact_id
                for item in derived.facts
                if item.derived_fact_id.startswith(f"{NEGATIVE_LOG_PRICE}:")
            )
        ).value
        if not isinstance(negative_log_price, Decimal):
            raise TypeError("Zhan negative-log-price derived fact must be decimal")
        return ZhanSubjectCandidate(
            subject=subject,
            as_of=by_type[FACT_PRICE].effective_time,
            evidence_identity="|".join(f"{fact.fact_id}@{fact.version}" for fact in facts),
            spot=price,
            security_type=security.security_type,
            shares_outstanding=shares,
            risk_free_rate=rate,
            negative_log_price=negative_log_price,
            contracts=chain.contracts,
            formation_date_state=formation_date_state,
        )

    return KnowledgeMapping(requests, _compute, _payload)
