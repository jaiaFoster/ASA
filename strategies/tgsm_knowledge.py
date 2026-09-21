"""S001's provider-neutral binding from sealed historical evidence to facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from analytics.derived_facts import (
    SMA_10M_COMPLETED_MONTHS,
    TRAILING_12M_TOTAL_RETURN,
    completed_month_end_observations,
    compute_sma_10m_completed_months,
    compute_trailing_12m_total_return,
)
from analytics.features import DerivedFactQualityStatus, DerivedFactRequest, DerivedFactSet
from domain import (
    AdjustedCloseBasis,
    CanonicalFact,
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    MarketCapability,
    OHLCVBar,
    UnknownReason,
)
from facts.canonical_projection import CanonicalFactRequest, canonical_fact_id
from strategies.knowledge_contracts import KnowledgeMapping
from strategies.tgsm_composition import SectorFacts

FACT_TOTAL_RETURN_HISTORY = "total_return_adjusted_close_history"
FACT_COMPLETED_MONTH_OBSERVATION = "completed_month_total_return_observation"


@dataclass(frozen=True, slots=True)
class _Bar:
    end_at: datetime
    adjusted_close: Decimal | None
    adjusted_close_basis: AdjustedCloseBasis | None


def _normalized(
    bars: tuple[OHLCVBar, ...],
) -> tuple[tuple[datetime, Decimal | None, str | None], ...]:
    return tuple(
        (
            bar.end_at,
            bar.adjusted_close,
            bar.adjusted_close_basis.value if bar.adjusted_close_basis is not None else None,
        )
        for bar in bars
    )


def _bars(value: object) -> tuple[_Bar, ...]:
    if not isinstance(value, tuple):
        raise TypeError("total-return historical fact must contain normalized bars")
    result: list[_Bar] = []
    for entry in value:
        end_at, adjusted_close, basis = entry
        result.append(_Bar(end_at, adjusted_close, AdjustedCloseBasis(basis) if basis else None))
    return tuple(result)


def build_s001_knowledge_mapping(
    *,
    subject: str,
    snapshot_digest: str,
    bars_observation_id: str,
    bars: tuple[OHLCVBar, ...],
    as_of: datetime,
) -> KnowledgeMapping[SectorFacts] | UnknownReason:
    """Require total-return-capable monthly history before strategy interpretation."""
    month_ends = completed_month_end_observations(bars, as_of)
    if len(month_ends) < 13:
        return UnknownReason("insufficient_total_return_history")
    latest_value = month_ends[-1].adjusted_close
    if latest_value is None:
        return UnknownReason("missing_total_return_observation")
    history_id = canonical_fact_id(FACT_TOTAL_RETURN_HISTORY, subject, snapshot_digest)
    observation_id = canonical_fact_id(FACT_COMPLETED_MONTH_OBSERVATION, subject, snapshot_digest)
    history_request = CanonicalFactRequest(
        capability=MarketCapability.HISTORICAL_BARS_V1,
        observation_id=bars_observation_id,
        value=_normalized(bars),
        subject=subject,
        fact_type=FACT_TOTAL_RETURN_HISTORY,
    )
    observation_request = CanonicalFactRequest(
        MarketCapability.HISTORICAL_BARS_V1,
        bars_observation_id,
        latest_value,
        subject,
        FACT_COMPLETED_MONTH_OBSERVATION,
    )

    def _compute(
        facts: tuple[CanonicalFact, ...],
    ) -> tuple[DerivedFactRequest, ...] | UnknownReason:
        by_id = {item.fact_id: item for item in facts}
        observations = _bars(by_id[history_id].value)
        month_ends = completed_month_end_observations(observations, as_of)
        if len(month_ends) < 13:
            return UnknownReason("insufficient_total_return_history")
        latest = month_ends[-1]
        if latest.adjusted_close is None:
            return UnknownReason("missing_total_return_observation")
        try:
            trailing = compute_trailing_12m_total_return(observations, as_of)
            sma = compute_sma_10m_completed_months(observations, as_of)
        except ValueError:
            return UnknownReason("unusable_total_return_history")
        selected = month_ends[-13:]
        if any(
            item.adjusted_close_basis is not AdjustedCloseBasis.SPLIT_AND_DIVIDEND_ADJUSTED
            for item in selected
        ):
            return UnknownReason("unusable_total_return_history")
        evidence = (EvidenceReference(EvidenceKind.CANONICAL_FACT, history_id, 1),)
        return (
            DerivedFactRequest(
                TRAILING_12M_TOTAL_RETURN,
                subject,
                trailing,
                "decimal",
                evidence,
                DerivedFactQualityStatus.VALID,
            ),
            DerivedFactRequest(
                SMA_10M_COMPLETED_MONTHS,
                subject,
                sma,
                "price",
                evidence,
                DerivedFactQualityStatus.VALID,
            ),
        )

    def _payload(facts: tuple[CanonicalFact, ...], derived: DerivedFactSet) -> SectorFacts:
        by_id = {item.fact_id: item for item in facts}
        trailing = next(
            item
            for item in derived.facts
            if item.derived_fact_id.startswith(f"{TRAILING_12M_TOTAL_RETURN}:")
        )
        sma = next(
            item
            for item in derived.facts
            if item.derived_fact_id.startswith(f"{SMA_10M_COMPLETED_MONTHS}:")
        )
        assert isinstance(trailing.value, Decimal)
        assert isinstance(sma.value, Decimal)
        observed = by_id[observation_id].value
        assert isinstance(observed, Decimal)
        return SectorFacts(
            CanonicalInstrumentIdentity("symbol", subject),
            trailing.value,
            trailing.derived_fact_id,
            observed,
            observation_id,
            sma.value,
            sma.derived_fact_id,
            as_of,
        )

    return KnowledgeMapping((history_request, observation_request), _compute, _payload)
