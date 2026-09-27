"""Cross-sectional quantile assignment (DF-XS-QUANTILE-ASSIGNMENT 1.1.0, SP-01E).

The research sources say only "sort into deciles/quintiles". The breakpoint,
tie and universe conventions are research assumption RA-XS-01, not source
rules. They are exposed as explicit, identity-bearing policy values so a
manifest parameterizes them and replay identity changes if they change.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from domain import UnknownReason

RA_XS_01 = "RA-XS-01"


class TiePolicy(StrEnum):
    SHARE_LOWEST_RANK = "share_lowest_rank"


class BreakpointUniverse(StrEnum):
    FULL_ELIGIBLE_SET = "full_eligible_set"


@dataclass(frozen=True, slots=True)
class QuantilePolicy:
    groups: int
    tie_policy: TiePolicy = TiePolicy.SHARE_LOWEST_RANK
    breakpoint_universe: BreakpointUniverse = BreakpointUniverse.FULL_ELIGIBLE_SET
    assumption_id: str = RA_XS_01

    def __post_init__(self) -> None:
        if self.groups < 2:
            raise ValueError("QuantilePolicy.groups must be at least two")


@dataclass(frozen=True, slots=True)
class QuantileAssignment:
    policy: QuantilePolicy
    eligible_count: int
    groups: tuple[tuple[str, int], ...]
    excluded: tuple[tuple[str, str], ...]

    def group_of(self, subject: str) -> int | None:
        return dict(self.groups).get(subject)

    def members(self, group: int) -> tuple[str, ...]:
        return tuple(subject for subject, value in self.groups if value == group)


def assign_quantiles(
    values: Mapping[str, Decimal | UnknownReason], policy: QuantilePolicy
) -> QuantileAssignment | UnknownReason:
    """RA-XS-01: rank r = 1 + #{x_j < x_i}; group = ceil(Q · r / N) over the full eligible set.

    A subject whose sort value is UNKNOWN is excluded (never assigned a rank).
    """
    for subject, value in values.items():
        if isinstance(value, Decimal):
            if not value.is_finite():
                raise ValueError(f"sort value for {subject!r} must be finite")
        elif not isinstance(value, UnknownReason):
            raise TypeError(f"sort value for {subject!r} must be Decimal or UnknownReason")
    eligible = {subject: value for subject, value in values.items() if isinstance(value, Decimal)}
    excluded = tuple(
        sorted(
            (subject, value.code)
            for subject, value in values.items()
            if isinstance(value, UnknownReason)
        )
    )
    count = len(eligible)
    if count == 0:
        return UnknownReason("empty_eligible_set")
    ordered = sorted(eligible.values())
    groups: list[tuple[str, int]] = []
    for subject in sorted(eligible):
        value = eligible[subject]
        rank = 1 + _count_below(ordered, value)
        groups.append((subject, -(-policy.groups * rank // count)))  # ceil(Q·r/N)
    return QuantileAssignment(policy, count, tuple(groups), excluded)


def _count_below(ordered: list[Decimal], value: Decimal) -> int:
    low, high = 0, len(ordered)
    while low < high:
        middle = (low + high) // 2
        if ordered[middle] < value:
            low = middle + 1
        else:
            high = middle
    return low
