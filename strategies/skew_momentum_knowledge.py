"""Skew Momentum mapping from sealed evidence to immutable facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from analytics.derived_facts import (
    ATM_IV_VS_REALIZED,
    CALL_WING_IV_VS_REALIZED,
    NAMED_MOMENTUM_DIMENSIONS,
    NORMALIZED_CALL_SKEW,
    NORMALIZED_PUT_SKEW,
    PUT_WING_IV_VS_REALIZED,
    REALIZED_VOLATILITY,
    SKEW_HISTORICAL_ZSCORE,
    compute_atm_iv_vs_realized_volatility,
    compute_historical_zscore,
    compute_iv_realized_spread,
    compute_normalized_skew,
)
from analytics.features import DerivedFactQualityStatus, DerivedFactRequest, DerivedFactSet
from analytics.realized_volatility import compute_realized_volatility, compute_trailing_return
from domain import (
    CanonicalFact,
    EvidenceKind,
    EvidenceReference,
    HistoricalSkewObservation,
    MarketCapability,
    OptionChain,
)
from facts.canonical_projection import CanonicalFactRequest, canonical_fact_id
from strategies.knowledge_contracts import KnowledgeMapping

FACT_DAILY_CLOSES = "daily_closes"
FACT_OPTION_IV = "option_implied_volatility"
_VERSION = 1


@dataclass(frozen=True, slots=True)
class SkewMomentumPayload:
    chain: OptionChain
    expiration: date
    normalized_call_skew: Decimal
    normalized_put_skew: Decimal
    call_skew_zscore: Decimal | None
    put_skew_zscore: Decimal | None
    historical_valid_observations: int
    call_atm_iv_minus_rv: Decimal
    put_atm_iv_minus_rv: Decimal
    call_wing_iv_minus_rv: Decimal
    put_wing_iv_minus_rv: Decimal
    call_wing_iv_minus_atm_iv: Decimal
    put_wing_iv_minus_atm_iv: Decimal
    time_series_return: Decimal


def build_skew_momentum_knowledge_mapping(
    *,
    subject: str,
    snapshot_digest: str,
    chain_observation_id: str,
    bars_observation_id: str,
    chain: OptionChain,
    expiration: date,
    closes: tuple[Decimal, ...],
    call_atm_iv: Decimal,
    put_atm_iv: Decimal,
    call_wing_iv: Decimal,
    put_wing_iv: Decimal,
    history: tuple[HistoricalSkewObservation, ...],
) -> KnowledgeMapping[SkewMomentumPayload]:
    iv_values = (
        ("call_atm", call_atm_iv),
        ("put_atm", put_atm_iv),
        ("call_wing", call_wing_iv),
        ("put_wing", put_wing_iv),
    )
    requests = [
        CanonicalFactRequest(
            MarketCapability.HISTORICAL_BARS_V1,
            bars_observation_id,
            closes,
            subject,
            FACT_DAILY_CLOSES,
        )
    ]
    requests.extend(
        CanonicalFactRequest(
            MarketCapability.OPTION_CHAIN_V1,
            chain_observation_id,
            value,
            f"{subject}:{expiration.isoformat()}:{name}",
            FACT_OPTION_IV,
        )
        for name, value in iv_values
    )
    close_id = canonical_fact_id(FACT_DAILY_CLOSES, subject, snapshot_digest)
    iv_ids = {
        name: canonical_fact_id(
            FACT_OPTION_IV, f"{subject}:{expiration.isoformat()}:{name}", snapshot_digest
        )
        for name, _ in iv_values
    }
    params = (("expiration", expiration.isoformat()),)

    def _compute(facts: tuple[CanonicalFact, ...]) -> tuple[DerivedFactRequest, ...]:
        fact_by_id = {fact.fact_id: fact for fact in facts}
        close_values = fact_by_id[close_id].value
        assert isinstance(close_values, tuple)
        typed_closes = tuple(value for value in close_values if isinstance(value, Decimal))
        iv = {name: fact_by_id[fact_id].value for name, fact_id in iv_ids.items()}
        assert all(isinstance(value, Decimal) for value in iv.values())
        typed_iv = {name: value for name, value in iv.items() if isinstance(value, Decimal)}
        canonical_evidence = tuple(
            EvidenceReference(EvidenceKind.CANONICAL_FACT, fact.fact_id, _VERSION) for fact in facts
        )
        chain_evidence = tuple(
            EvidenceReference(EvidenceKind.CANONICAL_FACT, iv_ids[name], _VERSION)
            for name in sorted(iv_ids)
        )
        call_skew = compute_normalized_skew(typed_iv["call_atm"], typed_iv["call_wing"])
        put_skew = compute_normalized_skew(typed_iv["put_atm"], typed_iv["put_wing"])
        realized = compute_realized_volatility(typed_closes)
        result = [
            DerivedFactRequest(
                REALIZED_VOLATILITY,
                subject,
                realized,
                "decimal",
                canonical_evidence,
                DerivedFactQualityStatus.VALID,
            ),
            DerivedFactRequest(
                NORMALIZED_CALL_SKEW,
                subject,
                call_skew,
                "decimal",
                chain_evidence,
                DerivedFactQualityStatus.VALID,
                params,
            ),
            DerivedFactRequest(
                NORMALIZED_PUT_SKEW,
                subject,
                put_skew,
                "decimal",
                chain_evidence,
                DerivedFactQualityStatus.VALID,
                params,
            ),
            DerivedFactRequest(
                ATM_IV_VS_REALIZED,
                f"{subject}:call",
                compute_atm_iv_vs_realized_volatility(typed_iv["call_atm"], typed_closes),
                "decimal",
                canonical_evidence,
                DerivedFactQualityStatus.VALID,
                params,
            ),
            DerivedFactRequest(
                ATM_IV_VS_REALIZED,
                f"{subject}:put",
                compute_atm_iv_vs_realized_volatility(typed_iv["put_atm"], typed_closes),
                "decimal",
                canonical_evidence,
                DerivedFactQualityStatus.VALID,
                params,
            ),
            DerivedFactRequest(
                CALL_WING_IV_VS_REALIZED,
                subject,
                compute_iv_realized_spread(typed_iv["call_wing"], realized),
                "decimal",
                canonical_evidence,
                DerivedFactQualityStatus.VALID,
                params,
            ),
            DerivedFactRequest(
                PUT_WING_IV_VS_REALIZED,
                subject,
                compute_iv_realized_spread(typed_iv["put_wing"], realized),
                "decimal",
                canonical_evidence,
                DerivedFactQualityStatus.VALID,
                params,
            ),
            DerivedFactRequest(
                NAMED_MOMENTUM_DIMENSIONS,
                subject,
                compute_trailing_return(typed_closes[-21:]),
                "decimal",
                (EvidenceReference(EvidenceKind.CANONICAL_FACT, close_id, _VERSION),),
                DerivedFactQualityStatus.VALID,
                (("lookback_sessions", "20"),),
            ),
        ]
        if len(history) >= 40:
            history_evidence = tuple(reference for item in history for reference in item.evidence)
            result.extend(
                (
                    DerivedFactRequest(
                        SKEW_HISTORICAL_ZSCORE,
                        f"{subject}:call",
                        compute_historical_zscore(
                            call_skew, tuple(item.call_skew for item in history)
                        ),
                        "decimal",
                        history_evidence,
                        DerivedFactQualityStatus.VALID,
                        (("lookback_observations", "60"),),
                    ),
                    DerivedFactRequest(
                        SKEW_HISTORICAL_ZSCORE,
                        f"{subject}:put",
                        compute_historical_zscore(
                            put_skew, tuple(item.put_skew for item in history)
                        ),
                        "decimal",
                        history_evidence,
                        DerivedFactQualityStatus.VALID,
                        (("lookback_observations", "60"),),
                    ),
                )
            )
        return tuple(result)

    def _payload(facts: tuple[CanonicalFact, ...], derived: DerivedFactSet) -> SkewMomentumPayload:
        def value(feature: str, subject_part: str = subject) -> Decimal:
            fact = next(
                item
                for item in derived.facts
                if item.derived_fact_id.startswith(f"{feature}:{subject_part}:")
            )
            assert isinstance(fact.value, Decimal)
            return fact.value

        call_z = value(SKEW_HISTORICAL_ZSCORE, f"{subject}:call") if len(history) >= 40 else None
        put_z = value(SKEW_HISTORICAL_ZSCORE, f"{subject}:put") if len(history) >= 40 else None
        return SkewMomentumPayload(
            chain,
            expiration,
            value(NORMALIZED_CALL_SKEW),
            value(NORMALIZED_PUT_SKEW),
            call_z,
            put_z,
            len(history),
            value(ATM_IV_VS_REALIZED, f"{subject}:call"),
            value(ATM_IV_VS_REALIZED, f"{subject}:put"),
            value(CALL_WING_IV_VS_REALIZED),
            value(PUT_WING_IV_VS_REALIZED),
            call_wing_iv - call_atm_iv,
            put_wing_iv - put_atm_iv,
            value(NAMED_MOMENTUM_DIMENSIONS),
        )

    return KnowledgeMapping(tuple(requests), _compute, _payload)
