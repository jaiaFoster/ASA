"""Generic immutable P10/P12 option-portfolio structures (SP-05A)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_DOWN, Decimal, localcontext
from enum import StrEnum
from typing import Protocol

from analytics.option_facts import delta_neutral_hedge_quantity
from analytics.quantile_assignment import QuantileAssignment, QuantilePolicy, assign_quantiles
from domain import OptionLeg, UnknownReason


class PortfolioWeightPolicy(StrEnum):
    EQUAL = "equal"
    SOURCE_DEFINED = "source_defined"


class PortfolioBookSide(StrEnum):
    LONG = "long"
    SHORT = "short"


class IdentifiedPosition(Protocol):
    @property
    def identity(self) -> str: ...


@dataclass(frozen=True, slots=True)
class DeltaHedgedOptionPosition:
    """P10: one exact option leg plus a static signed underlying hedge."""

    subject: str
    option_leg: OptionLeg
    underlying_quantity: Decimal
    hedge_formula_id: str = "DF-DELTA-NEUTRAL-HEDGE-QUANTITY"
    hedge_formula_version: str = "1.0.0"

    def __post_init__(self) -> None:
        if not self.subject or self.subject != self.subject.strip():
            raise ValueError("P10 subject must be normalized")
        if not isinstance(self.option_leg, OptionLeg):
            raise ValueError("P10 option_leg must be canonical OptionLeg")
        if not self.underlying_quantity.is_finite():
            raise ValueError("P10 underlying quantity must be finite")

    @property
    def identity(self) -> str:
        return _identity(
            "asa.p10.delta_hedged_option",
            (
                self.subject,
                self.option_leg.identity,
                str(self.underlying_quantity),
                self.hedge_formula_id,
                self.hedge_formula_version,
            ),
        )


@dataclass(frozen=True, slots=True)
class CrossSectionalMember:
    subject: str
    position_identity: str
    quantile: int
    weight: Decimal
    side: PortfolioBookSide = PortfolioBookSide.LONG

    def __post_init__(self) -> None:
        if not self.subject or not self.position_identity or self.quantile < 1:
            raise ValueError("P12 member identity and quantile are required")
        if not self.weight.is_finite() or self.weight <= 0:
            raise ValueError("P12 member weight must be positive and finite")


@dataclass(frozen=True, slots=True)
class CrossSectionalPortfolio:
    """P12: point-in-time portfolio over exact immutable member positions."""

    as_of: datetime
    evidence_identity: str
    quantile_assignment: QuantileAssignment
    weight_policy: PortfolioWeightPolicy
    members: tuple[CrossSectionalMember, ...]

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("P12 as_of must be timezone-aware")
        if not self.evidence_identity:
            raise ValueError("P12 evidence identity is required")
        subjects = tuple(item.subject for item in self.members)
        if not subjects or len(subjects) != len(set(subjects)):
            raise ValueError("P12 members must be non-empty and subject-unique")
        for side in {item.side for item in self.members}:
            if sum(
                (item.weight for item in self.members if item.side is side), Decimal(0)
            ) != Decimal(1):
                raise ValueError("P12 member weights must sum exactly to one per book side")

    @property
    def identity(self) -> str:
        return _identity(
            "asa.p12.cross_sectional_portfolio",
            (
                self.as_of.isoformat(),
                self.evidence_identity,
                self.weight_policy.value,
                self.quantile_assignment.policy.assumption_id,
                self.quantile_assignment.policy.groups,
                self.quantile_assignment.policy.tie_policy.value,
                self.quantile_assignment.policy.breakpoint_universe.value,
                tuple(
                    (m.subject, m.position_identity, m.quantile, str(m.weight), m.side.value)
                    for m in self.members
                ),
            ),
        )


def build_delta_hedged_option_position(
    subject: str, option_leg: OptionLeg, *, contract_multiplier: Decimal
) -> DeltaHedgedOptionPosition | UnknownReason:
    hedge = delta_neutral_hedge_quantity(
        option_leg.contract.delta,
        option_leg.quantity,
        contract_multiplier,
        long_option=option_leg.position.value == "long",
    )
    if isinstance(hedge, UnknownReason):
        return hedge
    return DeltaHedgedOptionPosition(subject, option_leg, hedge)


def build_cross_sectional_portfolio(
    *,
    as_of: datetime,
    evidence_identity: str,
    sort_values: Mapping[str, Decimal | UnknownReason],
    positions: Mapping[str, IdentifiedPosition],
    quantile_policy: QuantilePolicy,
    included_quantiles: frozenset[int],
    weight_policy: PortfolioWeightPolicy,
    source_weights: Mapping[str, Decimal] | None = None,
    short_quantiles: frozenset[int] = frozenset(),
) -> CrossSectionalPortfolio | UnknownReason:
    assignment = assign_quantiles(sort_values, quantile_policy)
    if isinstance(assignment, UnknownReason):
        return assignment
    selected = tuple(
        (subject, group)
        for subject, group in assignment.groups
        if group in included_quantiles and subject in positions
    )
    if not selected:
        return UnknownReason("empty_selected_cross_section")
    ordered_selected = tuple(sorted(selected))
    if weight_policy is PortfolioWeightPolicy.EQUAL:
        raw_weights = {subject: Decimal(1) for subject, _ in ordered_selected}
    else:
        if source_weights is None or any(
            subject not in source_weights or source_weights[subject] <= 0 for subject, _ in selected
        ):
            return UnknownReason("missing_source_defined_weight")
        raw_weights = {subject: source_weights[subject] for subject, _ in ordered_selected}
    weights: dict[str, Decimal] = {}
    sides = {
        subject: PortfolioBookSide.SHORT if group in short_quantiles else PortfolioBookSide.LONG
        for subject, group in ordered_selected
    }
    for side in sorted(set(sides.values()), key=lambda item: item.value):
        side_subjects = tuple(
            subject for subject, _group in ordered_selected if sides[subject] is side
        )
        raw_total = sum((raw_weights[subject] for subject in side_subjects), Decimal(0))
        if not raw_total.is_finite() or raw_total <= 0:
            return UnknownReason("invalid_source_defined_weight")
        residual_subject = max(side_subjects, key=lambda subject: (raw_weights[subject], subject))
        with localcontext() as context:
            context.rounding = ROUND_DOWN
            weights.update(
                {
                    subject: raw_weights[subject] / raw_total
                    for subject in side_subjects
                    if subject != residual_subject
                }
            )
        weights[residual_subject] = Decimal(1) - sum(
            (weights[subject] for subject in side_subjects if subject != residual_subject),
            Decimal(0),
        )
    members = tuple(
        CrossSectionalMember(
            subject, positions[subject].identity, group, weights[subject], sides[subject]
        )
        for subject, group in ordered_selected
    )
    return CrossSectionalPortfolio(as_of, evidence_identity, assignment, weight_policy, members)


def _identity(namespace: str, values: object) -> str:
    return hashlib.sha256(
        json.dumps((namespace, values), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
