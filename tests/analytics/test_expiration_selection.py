from __future__ import annotations

from datetime import date

import pytest

from analytics.expiration_selection import ExpirationCandidate, select_expiration_pair

_POLICY = {
    "front_min_dte": 35,
    "front_max_dte": 90,
    "back_min_dte": 49,
    "back_max_dte": 139,
    "minimum_gap_days": 14,
    "maximum_gap_days": 49,
    "target_front_dte": 60,
    "target_gap_days": 30,
}


def _candidate(days: int, expiration: date) -> ExpirationCandidate:
    return ExpirationCandidate(expiration, days)


class TestSelectExpirationPair:
    def test_selects_the_pair_closest_to_target(self) -> None:
        candidates = (
            _candidate(61, date(2026, 9, 21)),
            _candidate(91, date(2026, 10, 21)),
            _candidate(35, date(2026, 8, 26)),
            _candidate(139, date(2026, 12, 8)),
        )
        selected = select_expiration_pair(candidates, **_POLICY)
        assert selected is not None
        front, back = selected
        assert front.days_to_expiration == 61
        assert back.days_to_expiration == 91

    def test_returns_none_when_no_pair_satisfies_the_policy(self) -> None:
        candidates = (_candidate(5, date(2026, 7, 27)),)
        assert select_expiration_pair(candidates, **_POLICY) is None

    def test_returns_none_for_empty_candidates(self) -> None:
        assert select_expiration_pair((), **_POLICY) is None

    def test_gap_constraint_is_enforced(self) -> None:
        # front and back both individually valid, but gap (139-35=104) exceeds max 49.
        candidates = (
            _candidate(35, date(2026, 8, 26)),
            _candidate(139, date(2026, 12, 8)),
        )
        assert select_expiration_pair(candidates, **_POLICY) is None

    def test_is_deterministic(self) -> None:
        candidates = (
            _candidate(61, date(2026, 9, 21)),
            _candidate(91, date(2026, 10, 21)),
        )
        first = select_expiration_pair(candidates, **_POLICY)
        second = select_expiration_pair(candidates, **_POLICY)
        assert first == second

    @pytest.mark.parametrize(
        "overrides",
        [
            {"front_min_dte": 100, "front_max_dte": 50},
            {"minimum_gap_days": 100, "maximum_gap_days": 10},
            {"front_min_dte": -1},
        ],
    )
    def test_invalid_policy_rejected(self, overrides: dict[str, int]) -> None:
        policy = dict(_POLICY)
        policy.update(overrides)
        with pytest.raises(ValueError, match="policy is invalid"):
            select_expiration_pair((), **policy)
