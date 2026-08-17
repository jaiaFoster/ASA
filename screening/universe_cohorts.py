"""Deterministic bounded traversal of effective-dated universe membership.

This is capacity/fairness planning only. It never ranks symbols, inspects
strategy policy, or changes membership. Every member appears exactly once in
one full sweep; callers choose which cohort ordinal a cycle processes.
"""

from __future__ import annotations

from dataclasses import dataclass

from screening.universe_membership import EquityUniverseMembershipSnapshot


@dataclass(frozen=True, slots=True)
class UniverseCohort:
    universe_id: str
    source_revision_id: int
    cohort_ordinal: int
    cohort_count: int
    symbols: tuple[str, ...]


def plan_universe_cohort(
    snapshot: EquityUniverseMembershipSnapshot,
    *,
    maximum_subjects: int,
    cohort_ordinal: int,
) -> UniverseCohort:
    """Return one deterministic slice of symbol-sorted membership.

    ``cohort_ordinal`` may increase indefinitely; modulo traversal makes the
    plan replayable while guaranteeing a complete sweep every ``cohort_count``
    cycles. The final cohort may be smaller and is never padded or duplicated.
    """
    if maximum_subjects < 1:
        raise ValueError("maximum_subjects must be positive")
    if cohort_ordinal < 0:
        raise ValueError("cohort_ordinal must be non-negative")
    cohort_count = (len(snapshot.symbols) + maximum_subjects - 1) // maximum_subjects
    normalized_ordinal = cohort_ordinal % cohort_count
    start = normalized_ordinal * maximum_subjects
    return UniverseCohort(
        universe_id=snapshot.universe_id,
        source_revision_id=snapshot.source_revision_id,
        cohort_ordinal=normalized_ordinal,
        cohort_count=cohort_count,
        symbols=snapshot.symbols[start : start + maximum_subjects],
    )
