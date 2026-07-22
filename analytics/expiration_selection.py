"""Reusable expiration-pair selection (ANALYTICS-002).

Selects one front/back ExpirationCycle pair from a pool by an explicit DTE
and gap policy. This is deliberately independent of
strategies/stonk_components.py's DtePairSelector component -- that
component is wired inside the frozen Forward Factor manifest graph for its
own calendar-structure-building branch, but the manifest's separate
implied_forward_volatility node has no incoming graph edges at all (SPRINT-
006's discovered gap): its front_iv/back_iv/front_dte/back_dte inputs must
be supplied from outside the graph entirely. This selector serves that
external, pre-graph step, using the same selection semantics so the two
branches choose consistent expirations, without importing strategies/ (this
package cannot -- see tests/architecture/test_analytics_boundaries.py) or
modifying the manifest itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class ExpirationCandidate:
    """The minimal shape this selector needs from a canonical expiration
    cycle -- decoupled from domain.ExpirationCycle's own constructor shape
    so callers can adapt any compatible source.
    """

    expiration_date: date
    days_to_expiration: int


def select_earnings_relative_expiration_pair(
    candidates: tuple[ExpirationCandidate, ...],
    earnings_date: date,
    *,
    front_min_dte: int,
    front_max_dte: int,
    back_min_dte: int,
    back_max_dte: int,
    front_must_be_before_earnings: bool = True,
) -> tuple[ExpirationCandidate, ExpirationCandidate] | None:
    """Select the front/back pair spanning an earnings event: independent
    of strategies/stonk_components.py::ExpirationPairSelector (this
    package cannot import strategies/), using the same earnings-relative
    selection semantics -- front strictly before the earnings date, back
    strictly after, both within their own DTE windows -- so a consistent
    pair is chosen without depending on the graph system. Returns None
    when no candidate pair satisfies the policy -- an expected,
    non-exceptional outcome the caller must handle explicitly.
    """
    if (
        min(front_min_dte, front_max_dte, back_min_dte, back_max_dte) < 0
        or front_min_dte > front_max_dte
        or back_min_dte > back_max_dte
    ):
        raise ValueError("earnings-relative expiration selection policy is invalid")

    fronts = tuple(
        candidate
        for candidate in candidates
        if front_min_dte <= candidate.days_to_expiration <= front_max_dte
        and (
            candidate.expiration_date < earnings_date
            or not front_must_be_before_earnings
        )
    )
    backs = tuple(
        candidate
        for candidate in candidates
        if back_min_dte <= candidate.days_to_expiration <= back_max_dte
        and candidate.expiration_date > earnings_date
    )
    pairs = tuple(
        (front, back)
        for front in fronts
        for back in backs
        if back.expiration_date > front.expiration_date
    )
    return min(
        pairs,
        key=lambda pair: (
            (earnings_date - pair[0].expiration_date).days
            + (pair[1].expiration_date - earnings_date).days,
            pair[0].expiration_date,
            pair[1].expiration_date,
        ),
        default=None,
    )


def select_expiration_pair(
    candidates: tuple[ExpirationCandidate, ...],
    *,
    front_min_dte: int,
    front_max_dte: int,
    back_min_dte: int,
    back_max_dte: int,
    minimum_gap_days: int,
    maximum_gap_days: int,
    target_front_dte: int,
    target_gap_days: int,
) -> tuple[ExpirationCandidate, ExpirationCandidate] | None:
    """Select the front/back pair closest to the target front DTE and gap,
    among all pairs satisfying the DTE-window and gap bounds. Returns None
    when no candidate pair satisfies the policy -- an expected, non-
    exceptional outcome the caller must handle explicitly, not a defect.
    """
    if (
        min(
            front_min_dte,
            front_max_dte,
            back_min_dte,
            back_max_dte,
            minimum_gap_days,
            maximum_gap_days,
        )
        < 0
        or front_min_dte > front_max_dte
        or back_min_dte > back_max_dte
        or minimum_gap_days > maximum_gap_days
    ):
        raise ValueError("expiration selection policy is invalid")

    pairs = tuple(
        (front, back)
        for front in candidates
        for back in candidates
        if front_min_dte <= front.days_to_expiration <= front_max_dte
        and back_min_dte <= back.days_to_expiration <= back_max_dte
        and minimum_gap_days
        <= back.days_to_expiration - front.days_to_expiration
        <= maximum_gap_days
    )
    return min(
        pairs,
        key=lambda pair: (
            abs(pair[0].days_to_expiration - target_front_dte)
            + abs(pair[1].days_to_expiration - pair[0].days_to_expiration - target_gap_days),
            pair[0].expiration_date,
            pair[1].expiration_date,
        ),
        default=None,
    )
