"""Generic deterministic ranking and trend eligibility over named facts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from domain import CanonicalInstrumentIdentity
from domain.values import require_tz_aware


class RankingDirection(StrEnum):
    ASCENDING = "ascending"
    DESCENDING = "descending"


class EligibilityState(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RankableFact:
    subject: CanonicalInstrumentIdentity
    feature_id: str
    formula_version: str
    fact_id: str
    value: Decimal
    effective_time: datetime

    def __post_init__(self) -> None:
        if any(
            not value or value != value.strip()
            for value in (self.feature_id, self.formula_version, self.fact_id)
        ):
            raise ValueError("rankable fact identity fields must be normalized")
        if not self.value.is_finite():
            raise ValueError("rankable value must be finite")
        require_tz_aware(self.effective_time, "RankableFact", "effective_time")


@dataclass(frozen=True, slots=True)
class UnrankableSubject:
    subject: CanonicalInstrumentIdentity
    reason: str

    def __post_init__(self) -> None:
        if not self.reason or self.reason != self.reason.strip():
            raise ValueError("unrankable reason must be normalized")


@dataclass(frozen=True, slots=True)
class RankedFact:
    rank: int
    fact: RankableFact


@dataclass(frozen=True, slots=True)
class CrossSectionalRanking:
    ranking_id: str
    feature_id: str
    formula_version: str
    effective_time: datetime
    direction: RankingDirection
    ranked: tuple[RankedFact, ...]
    unrankable: tuple[UnrankableSubject, ...]


def _subject_key(subject: CanonicalInstrumentIdentity) -> tuple[str, str]:
    return subject.scheme, subject.value


def rank_named_facts(
    facts: tuple[RankableFact, ...],
    *,
    unrankable: tuple[UnrankableSubject, ...] = (),
    direction: RankingDirection = RankingDirection.DESCENDING,
) -> CrossSectionalRanking:
    """Rank comparable facts; missing subjects remain separate typed gaps."""
    if not facts:
        raise ValueError("at least one rankable fact is required")
    subjects = tuple(item.subject for item in facts) + tuple(item.subject for item in unrankable)
    if len(subjects) != len(set(subjects)):
        raise ValueError("cross-sectional subjects must be unique")
    feature_ids = {item.feature_id for item in facts}
    versions = {item.formula_version for item in facts}
    effective_times = {item.effective_time for item in facts}
    if len(feature_ids) != 1 or len(versions) != 1 or len(effective_times) != 1:
        raise ValueError("ranked facts must share feature, version, and effective time")
    ordered = tuple(
        sorted(
            facts,
            key=lambda item: (
                -item.value if direction is RankingDirection.DESCENDING else item.value,
                *_subject_key(item.subject),
            ),
        )
    )
    ranked = tuple(RankedFact(index, item) for index, item in enumerate(ordered, start=1))
    missing = tuple(sorted(unrankable, key=lambda item: _subject_key(item.subject)))
    payload = {
        "namespace": "asa.cross_sectional_ranking",
        "version": "v1",
        "feature_id": ordered[0].feature_id,
        "formula_version": ordered[0].formula_version,
        "effective_time": ordered[0].effective_time.isoformat(),
        "direction": direction.value,
        "ranked": [(item.rank, item.fact.fact_id) for item in ranked],
        "unrankable": [(*_subject_key(item.subject), item.reason) for item in missing],
    }
    ranking_id = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return CrossSectionalRanking(
        ranking_id,
        ordered[0].feature_id,
        ordered[0].formula_version,
        ordered[0].effective_time,
        direction,
        ranked,
        missing,
    )


def top_ranked(ranking: CrossSectionalRanking, count: int) -> tuple[RankedFact, ...]:
    if count <= 0:
        raise ValueError("top-ranked count must be positive")
    return ranking.ranked[:count]


@dataclass(frozen=True, slots=True)
class TrendEligibility:
    state: EligibilityState
    observation_fact_id: str | None
    sma_fact_id: str | None
    reason: str | None = None


def strictly_above_trend(
    observation: Decimal | None,
    sma: Decimal | None,
    *,
    observation_fact_id: str | None,
    sma_fact_id: str | None,
    unknown_reason: str = "missing_trend_evidence",
) -> TrendEligibility:
    """Generic strict comparison; equality fails and absence stays UNKNOWN."""
    if observation is None or sma is None:
        return TrendEligibility(
            EligibilityState.UNKNOWN, observation_fact_id, sma_fact_id, unknown_reason
        )
    return TrendEligibility(
        EligibilityState.PASS if observation > sma else EligibilityState.FAIL,
        observation_fact_id,
        sma_fact_id,
    )

