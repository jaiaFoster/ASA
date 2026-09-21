"""S001 thesis over comparable, already-materialized sector knowledge.

This module has no acquisition or runtime authority. The caller supplies the
point-in-time eligible cohort and immutable named facts from sealed evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from analytics.cross_sectional_ranking import (
    CrossSectionalRanking,
    RankableFact,
    RankingDirection,
    TrendEligibility,
    UnrankableSubject,
    rank_named_facts,
    strictly_above_trend,
    top_ranked,
)
from analytics.derived_facts import TRAILING_12M_TOTAL_RETURN
from domain import CanonicalInstrumentIdentity


@dataclass(frozen=True, slots=True)
class SectorFacts:
    """Material inputs for one eligible subject at a common decision time."""

    subject: CanonicalInstrumentIdentity
    trailing_return: Decimal | None
    trailing_return_fact_id: str | None
    trend_observation: Decimal | None
    trend_observation_fact_id: str | None
    sma_10m: Decimal | None
    sma_10m_fact_id: str | None
    effective_time: datetime
    missing_reason: str | None = None


@dataclass(frozen=True, slots=True)
class SelectedSector:
    rank: int
    subject: CanonicalInstrumentIdentity
    return_fact_id: str
    trailing_return: Decimal
    trend: TrendEligibility


@dataclass(frozen=True, slots=True)
class S001Selection:
    decision_time: datetime
    eligible_subjects: tuple[CanonicalInstrumentIdentity, ...]
    ranking: CrossSectionalRanking | None
    selected: tuple[SelectedSector, ...]
    unknown_reason: str | None


def compose_s001_selection(
    eligible: tuple[CanonicalInstrumentIdentity, ...],
    facts: tuple[SectorFacts, ...],
    *,
    decision_time: datetime,
) -> S001Selection:
    """Rank eligible sectors, then apply the strict trend gate to top three.

    An unknown return could outrank a known return. Selection therefore fails
    closed while retaining the observed ranking for diagnostics.
    """
    if decision_time.tzinfo is None or decision_time.utcoffset() is None:
        raise ValueError("decision_time must be timezone-aware")
    if eligible != tuple(sorted(set(eligible), key=lambda item: (item.scheme, item.value))):
        raise ValueError("eligible subjects must be unique and canonically sorted")
    by_subject = {item.subject: item for item in facts}
    if len(by_subject) != len(facts) or set(by_subject) - set(eligible):
        raise ValueError("sector facts must uniquely identify eligible subjects")
    if any(item.effective_time != decision_time for item in facts):
        raise ValueError("sector facts must share the decision time")
    rankable: list[RankableFact] = []
    unrankable: list[UnrankableSubject] = []
    for subject in eligible:
        item = by_subject.get(subject)
        if item is None or item.trailing_return is None or item.trailing_return_fact_id is None:
            unrankable.append(
                UnrankableSubject(
                    subject,
                    item.missing_reason
                    if item is not None and item.missing_reason
                    else "missing_trailing_return",
                )
            )
            continue
        rankable.append(
            RankableFact(
                subject,
                TRAILING_12M_TOTAL_RETURN,
                "1.0.0",
                item.trailing_return_fact_id,
                item.trailing_return,
                decision_time,
            )
        )
    ranking = (
        rank_named_facts(
            tuple(rankable), unrankable=tuple(unrankable), direction=RankingDirection.DESCENDING
        )
        if rankable
        else None
    )
    if unrankable or ranking is None or len(ranking.ranked) < 3:
        return S001Selection(decision_time, eligible, ranking, (), "incomplete_sector_returns")
    selected = tuple(
        SelectedSector(
            ranked.rank,
            ranked.fact.subject,
            ranked.fact.fact_id,
            ranked.fact.value,
            strictly_above_trend(
                by_subject[ranked.fact.subject].trend_observation,
                by_subject[ranked.fact.subject].sma_10m,
                observation_fact_id=by_subject[ranked.fact.subject].trend_observation_fact_id,
                sma_fact_id=by_subject[ranked.fact.subject].sma_10m_fact_id,
            ),
        )
        for ranked in top_ranked(ranking, 3)
    )
    return S001Selection(decision_time, eligible, ranking, selected, None)
