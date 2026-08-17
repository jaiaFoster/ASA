from __future__ import annotations

import pytest

from screening.universe_cohorts import plan_universe_cohort
from screening.universe_membership import SP500_MEMBERSHIP


def test_sp500_is_covered_once_across_a_complete_bounded_sweep() -> None:
    cohorts = tuple(
        plan_universe_cohort(SP500_MEMBERSHIP, maximum_subjects=30, cohort_ordinal=ordinal)
        for ordinal in range(17)
    )
    symbols = tuple(symbol for cohort in cohorts for symbol in cohort.symbols)

    assert all(len(cohort.symbols) == 30 for cohort in cohorts[:-1])
    assert len(cohorts[-1].symbols) == 23
    assert symbols == SP500_MEMBERSHIP.symbols
    assert len(set(symbols)) == 503


def test_cohort_selection_is_replay_stable_and_wraps_by_sweep() -> None:
    first = plan_universe_cohort(SP500_MEMBERSHIP, maximum_subjects=30, cohort_ordinal=3)
    replay = plan_universe_cohort(SP500_MEMBERSHIP, maximum_subjects=30, cohort_ordinal=20)
    assert first == replay


@pytest.mark.parametrize("maximum_subjects", (0, -1))
def test_non_positive_capacity_is_rejected(maximum_subjects: int) -> None:
    with pytest.raises(ValueError, match="maximum_subjects"):
        plan_universe_cohort(
            SP500_MEMBERSHIP,
            maximum_subjects=maximum_subjects,
            cohort_ordinal=0,
        )


def test_negative_ordinal_is_rejected() -> None:
    with pytest.raises(ValueError, match="cohort_ordinal"):
        plan_universe_cohort(SP500_MEMBERSHIP, maximum_subjects=30, cohort_ordinal=-1)
