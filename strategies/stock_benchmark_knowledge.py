"""Stock benchmark (B001/B002) mapping from sealed evidence to immutable
facts. Both benchmarks are StructureKind.NONE/NO_LIFECYCLE: there is no
option chain, no structural selection, and (unlike Skew Momentum/Forward
Factor/Earnings Calendar) no manifest-graph evaluation -- their payloads
are consumed directly by strategy_runtime/adapters/stock_benchmarks_subject_first.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from analytics.derived_facts import (
    SMA_10M_COMPLETED_MONTHS,
    AdjustedCloseBarLike,
    compute_sma_10m_completed_months,
)
from analytics.features import DerivedFactQualityStatus, DerivedFactRequest, DerivedFactSet
from domain import (
    AdjustedCloseBasis,
    CanonicalFact,
    EvidenceKind,
    EvidenceReference,
    MarketCapability,
    OHLCVBar,
    UnknownReason,
)
from facts.canonical_projection import CanonicalFactRequest, canonical_fact_id
from strategies.knowledge_contracts import KnowledgeMapping

FACT_CURRENT_PRICE = "stock_benchmark_current_price"
FACT_MONTHLY_HISTORY_BARS = "stock_benchmark_monthly_history_bars"
_EVIDENCE_VERSION = 1

# A CanonicalFact's value must be an immutable normalized scalar/tuple
# (domain/values.py's own require_normalized) -- a raw OHLCVBar cannot be
# projected directly. Each bar is flattened to exactly the three fields
# compute_sma_10m_completed_months reads (end_at, adjusted_close,
# adjusted_close_basis-as-str), reconstructed as an AdjustedCloseBarLike
# below -- the same real values, never fabricated ones.
_NormalizedBar = tuple[datetime, Decimal | None, str | None]


@dataclass(frozen=True, slots=True)
class _MonthEndObservation:
    end_at: datetime
    adjusted_close: Decimal | None
    adjusted_close_basis: AdjustedCloseBasis | None


def _normalize_bars(bars: tuple[OHLCVBar, ...]) -> tuple[_NormalizedBar, ...]:
    return tuple(
        (
            bar.end_at,
            bar.adjusted_close,
            bar.adjusted_close_basis.value if bar.adjusted_close_basis is not None else None,
        )
        for bar in bars
    )


def _denormalize_bars(value: object) -> tuple[AdjustedCloseBarLike, ...]:
    if not isinstance(value, tuple):
        raise TypeError("B002 monthly history bars canonical fact must be a tuple")
    observations = []
    for entry in value:
        end_at, adjusted_close, basis = entry
        observations.append(
            _MonthEndObservation(
                end_at=end_at,
                adjusted_close=adjusted_close,
                adjusted_close_basis=(AdjustedCloseBasis(basis) if basis is not None else None),
            )
        )
    return tuple(observations)


@dataclass(frozen=True, slots=True)
class B001Payload:
    price: Decimal


@dataclass(frozen=True, slots=True)
class B002Payload:
    price: Decimal
    sma_10m: Decimal


def build_b001_knowledge_mapping(
    *,
    subject: str,
    quote_observation_id: str,
    price: Decimal,
) -> KnowledgeMapping[B001Payload]:
    price_request = CanonicalFactRequest(
        MarketCapability.REAL_TIME_QUOTE_V1,
        quote_observation_id,
        price,
        subject,
        FACT_CURRENT_PRICE,
    )

    def _compute(facts: tuple[CanonicalFact, ...]) -> tuple[DerivedFactRequest, ...]:
        del facts
        return ()

    def _payload(facts: tuple[CanonicalFact, ...], derived: DerivedFactSet) -> B001Payload:
        del derived
        (price_fact,) = facts
        if not isinstance(price_fact.value, Decimal):
            raise TypeError("B001 current price canonical fact must be decimal")
        return B001Payload(price_fact.value)

    return KnowledgeMapping((price_request,), _compute, _payload)


def build_b002_knowledge_mapping(
    *,
    subject: str,
    snapshot_digest: str,
    quote_observation_id: str,
    price: Decimal,
    bars_observation_id: str,
    bars: tuple[OHLCVBar, ...],
    as_of: datetime,
) -> KnowledgeMapping[B002Payload]:
    price_request = CanonicalFactRequest(
        MarketCapability.REAL_TIME_QUOTE_V1,
        quote_observation_id,
        price,
        subject,
        FACT_CURRENT_PRICE,
    )
    bars_request = CanonicalFactRequest(
        MarketCapability.HISTORICAL_BARS_V1,
        bars_observation_id,
        _normalize_bars(bars),
        subject,
        FACT_MONTHLY_HISTORY_BARS,
    )
    price_fact_id = canonical_fact_id(FACT_CURRENT_PRICE, subject, snapshot_digest)
    bars_fact_id = canonical_fact_id(FACT_MONTHLY_HISTORY_BARS, subject, snapshot_digest)

    def _compute(
        facts: tuple[CanonicalFact, ...],
    ) -> tuple[DerivedFactRequest, ...] | UnknownReason:
        fact_by_id = {fact.fact_id: fact for fact in facts}
        observations = _denormalize_bars(fact_by_id[bars_fact_id].value)
        try:
            sma = compute_sma_10m_completed_months(observations, as_of)
        except ValueError:
            # A genuine, expected data gap (fewer than ten completed
            # months of adjusted-close history) -- never a raw-close
            # fallback, per STOCK-RUNTIME-001 STK-01/STK-02.
            return UnknownReason("insufficient_adjusted_history")
        evidence = (
            EvidenceReference(EvidenceKind.CANONICAL_FACT, bars_fact_id, _EVIDENCE_VERSION),
        )
        return (
            DerivedFactRequest(
                SMA_10M_COMPLETED_MONTHS,
                subject,
                sma,
                "decimal",
                evidence,
                DerivedFactQualityStatus.VALID,
            ),
        )

    def _payload(facts: tuple[CanonicalFact, ...], derived: DerivedFactSet) -> B002Payload:
        fact_by_id = {fact.fact_id: fact for fact in facts}
        price_value = fact_by_id[price_fact_id].value
        if not isinstance(price_value, Decimal):
            raise TypeError("B002 current price canonical fact must be decimal")
        sma_fact = next(
            item
            for item in derived.facts
            if item.derived_fact_id.startswith(f"{SMA_10M_COMPLETED_MONTHS}:")
        )
        if not isinstance(sma_fact.value, Decimal):
            raise TypeError("sma_10m_completed_months derived fact must be decimal")
        return B002Payload(price_value, sma_fact.value)

    return KnowledgeMapping((price_request, bars_request), _compute, _payload)
