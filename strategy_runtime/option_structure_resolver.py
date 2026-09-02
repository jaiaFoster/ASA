"""Deterministic exact-option resolver over one canonical sealed chain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from domain import OptionChain, OptionContract, OptionLeg, OptionLegPosition, OptionType
from strategy_runtime.contract import StructureKind
from strategy_runtime.executable_structures import (
    ExecutableStructureAssessment,
    ExecutableStructureStatus,
    ModeledEntryEconomics,
    ResolvedOptionLeg,
    SelectionDiagnostic,
)

_MIDPOINT_MODEL_VERSION = "midpoint-v1"


@dataclass(frozen=True, slots=True)
class OptionLegIntent:
    role: str
    option_type: OptionType
    expiration: date
    position: OptionLegPosition
    quantity: Decimal
    selected_contract_identity: str | None = None
    selected_strike: Decimal | None = None
    target_delta: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.role or self.role != self.role.strip():
            raise ValueError("OptionLegIntent.role must be normalized non-empty text")
        selectors = tuple(
            item is not None
            for item in (
                self.selected_contract_identity,
                self.selected_strike,
                self.target_delta,
            )
        )
        if sum(selectors) != 1:
            raise ValueError("OptionLegIntent requires exactly one selection authority")
        if self.quantity <= 0:
            raise ValueError("OptionLegIntent.quantity must be positive")
        if self.target_delta is not None and not Decimal("-1") <= self.target_delta <= Decimal("1"):
            raise ValueError("OptionLegIntent.target_delta must be within [-1, 1]")


@dataclass(frozen=True, slots=True)
class OptionStructureIntent:
    subject: str
    intended_structure_kind: StructureKind
    legs: tuple[OptionLegIntent, ...]

    def __post_init__(self) -> None:
        if not self.subject or self.subject != self.subject.strip():
            raise ValueError("OptionStructureIntent.subject must be normalized non-empty text")
        if self.intended_structure_kind not in {StructureKind.CALENDAR, StructureKind.VERTICAL}:
            raise ValueError("OptionStructureIntent supports active v1 structures only")
        if len(self.legs) != 2:
            raise ValueError("OptionStructureIntent v1 structures require exactly two legs")
        roles = tuple(item.role for item in self.legs)
        if len(roles) != len(set(roles)):
            raise ValueError("OptionStructureIntent roles must be unique")


def _matching_contracts(chain: OptionChain, intent: OptionLegIntent) -> tuple[OptionContract, ...]:
    candidates = tuple(
        contract
        for contract in chain.contracts
        if contract.expiration == intent.expiration and contract.option_type is intent.option_type
    )
    if intent.selected_contract_identity is not None:
        return tuple(
            item for item in candidates if item.identity == intent.selected_contract_identity
        )
    if intent.selected_strike is not None:
        return tuple(item for item in candidates if item.strike == intent.selected_strike)
    with_delta = tuple(item for item in candidates if item.delta is not None)
    if not with_delta:
        return ()
    assert intent.target_delta is not None
    return tuple(
        sorted(
            with_delta,
            key=lambda item: (
                abs(abs(item.delta) - abs(intent.target_delta)),  # type: ignore[arg-type]
                item.identity,
            ),
        )
    )


def _resolve_leg(chain: OptionChain, intent: OptionLegIntent) -> ResolvedOptionLeg | None:
    candidates = _matching_contracts(chain, intent)
    if not candidates:
        return None
    contract = (
        min(candidates, key=lambda item: item.identity)
        if intent.target_delta is None
        else candidates[0]
    )
    return ResolvedOptionLeg(
        OptionLeg(contract, intent.position, intent.quantity, intent.role),
        intent.target_delta,
    )


def _midpoint_entry(
    legs: tuple[ResolvedOptionLeg, ...], assessed_at: datetime
) -> ModeledEntryEconomics | None:
    values = tuple(item.midpoint for item in legs)
    if any(value is None for value in values):
        return None
    typed = tuple(value for value in values if value is not None)
    total = Decimal(0)
    per_leg: list[tuple[str, Decimal]] = []
    for resolved, midpoint in zip(legs, typed, strict=True):
        sign = Decimal(1) if resolved.leg.position is OptionLegPosition.LONG else Decimal(-1)
        total += midpoint * resolved.leg.quantity * sign
        per_leg.append((resolved.leg.identity, midpoint))
    return ModeledEntryEconomics(tuple(per_leg), total, _MIDPOINT_MODEL_VERSION, assessed_at)


def _shape(legs: tuple[ResolvedOptionLeg, ...]) -> StructureKind:
    first, second = (item.leg.contract for item in legs)
    same_expiration = first.expiration == second.expiration
    same_strike = first.strike == second.strike
    same_type = first.option_type is second.option_type
    if same_strike and same_type and not same_expiration:
        return StructureKind.CALENDAR
    if same_expiration and same_type and not same_strike:
        return StructureKind.VERTICAL
    return StructureKind.CUSTOM


def resolve_option_structure(
    *,
    intent: OptionStructureIntent,
    chain: OptionChain,
    originating_result_identity: str,
    evidence_snapshot_identity: str,
    assessed_at: datetime,
) -> ExecutableStructureAssessment:
    """Resolve an intent without acquisition, inference, or structure substitution."""

    resolved = tuple(_resolve_leg(chain, item) for item in intent.legs)
    if any(item is None for item in resolved):
        missing_delta = any(
            leg.target_delta is not None
            and not any(
                contract.delta is not None
                for contract in chain.contracts
                if contract.expiration == leg.expiration
                and contract.option_type is leg.option_type
            )
            for leg, item in zip(intent.legs, resolved, strict=True)
            if item is None
        )
        return ExecutableStructureAssessment(
            originating_result_identity,
            intent.subject,
            intent.intended_structure_kind,
            ExecutableStructureStatus.UNKNOWN
            if missing_delta
            else ExecutableStructureStatus.NOT_CONSTRUCTIBLE,
            (),
            (),
            None,
            evidence_snapshot_identity,
            assessed_at,
            reason_code="missing_actual_delta" if missing_delta else "no_compatible_contract",
        )

    exact = tuple(item for item in resolved if item is not None)
    actual_shape = _shape(exact)
    diagnostics = tuple(
        SelectionDiagnostic(item.leg.role, item.target_delta, item.leg.contract.delta)
        for item in exact
    )
    if actual_shape is not intent.intended_structure_kind:
        return ExecutableStructureAssessment(
            originating_result_identity,
            intent.subject,
            intent.intended_structure_kind,
            ExecutableStructureStatus.DIFFERENT_STRUCTURE_AVAILABLE,
            exact,
            diagnostics,
            _midpoint_entry(exact, assessed_at),
            evidence_snapshot_identity,
            assessed_at,
            reason_code="resolved_legs_form_different_structure",
            available_structure_kind=actual_shape,
        )
    return ExecutableStructureAssessment(
        originating_result_identity,
        intent.subject,
        intent.intended_structure_kind,
        ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED,
        exact,
        diagnostics,
        _midpoint_entry(exact, assessed_at),
        evidence_snapshot_identity,
        assessed_at,
        available_structure_kind=actual_shape,
    )
