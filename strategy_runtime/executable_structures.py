"""Provider-neutral option execution-readiness artifacts.

These immutable records are downstream of a strategy result and sealed market
knowledge. They describe constructibility; they never redefine the signal or
grant acquisition/execution authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import cast

from domain import OptionLeg, deserialize_financial_contract, serialize_financial_contract
from strategy_runtime.contract import StructureKind


def _text(value: str, owner: str, field: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{owner}.{field} must be normalized non-empty text")


def _aware(value: datetime, owner: str, field: str) -> None:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{owner}.{field} must be timezone-aware")


class ExecutableStructureStatus(StrEnum):
    CONSTRUCTIBLE_AS_INTENDED = "constructible_as_intended"
    DIFFERENT_STRUCTURE_AVAILABLE = "different_structure_available"
    NOT_CONSTRUCTIBLE = "not_constructible"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ResolvedOptionLeg:
    """One exact canonical leg plus optional strategy-declared delta target."""

    leg: OptionLeg
    target_delta: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.leg, OptionLeg):
            raise ValueError("ResolvedOptionLeg.leg must be an OptionLeg")
        if self.target_delta is not None and not Decimal("-1") <= self.target_delta <= Decimal("1"):
            raise ValueError("ResolvedOptionLeg.target_delta must be within [-1, 1]")

    @property
    def canonical_contract_identity(self) -> str:
        return self.leg.contract.identity

    @property
    def midpoint(self) -> Decimal | None:
        contract = self.leg.contract
        if contract.bid is None or contract.ask is None:
            return None
        return (contract.bid + contract.ask) / Decimal(2)


@dataclass(frozen=True, slots=True)
class SelectionDiagnostic:
    role: str
    target_delta: Decimal | None
    actual_delta: Decimal | None

    def __post_init__(self) -> None:
        _text(self.role, "SelectionDiagnostic", "role")
        for field in ("target_delta", "actual_delta"):
            value = getattr(self, field)
            if value is not None and not Decimal("-1") <= value <= Decimal("1"):
                raise ValueError(f"SelectionDiagnostic.{field} must be within [-1, 1]")

    @property
    def absolute_delta_deviation(self) -> Decimal | None:
        if self.target_delta is None or self.actual_delta is None:
            return None
        return abs(abs(self.actual_delta) - abs(self.target_delta))


@dataclass(frozen=True, slots=True)
class ModeledEntryEconomics:
    per_leg_midpoints: tuple[tuple[str, Decimal], ...]
    modeled_net_debit_or_credit: Decimal
    model_version: str
    calculated_at: datetime

    def __post_init__(self) -> None:
        _text(self.model_version, "ModeledEntryEconomics", "model_version")
        _aware(self.calculated_at, "ModeledEntryEconomics", "calculated_at")
        identities = tuple(identity for identity, _ in self.per_leg_midpoints)
        if not identities or len(identities) != len(set(identities)):
            raise ValueError("ModeledEntryEconomics requires unique per-leg identities")
        for identity in identities:
            _text(identity, "ModeledEntryEconomics", "per_leg_midpoints")


@dataclass(frozen=True, slots=True)
class ExecutableStructureAssessment:
    originating_result_identity: str
    subject: str
    intended_structure_kind: StructureKind
    status: ExecutableStructureStatus
    exact_legs: tuple[ResolvedOptionLeg, ...]
    selection_diagnostics: tuple[SelectionDiagnostic, ...]
    modeled_entry_economics: ModeledEntryEconomics | None
    evidence_snapshot_identity: str
    assessed_at: datetime
    reason_code: str | None = None
    available_structure_kind: StructureKind | None = None

    def __post_init__(self) -> None:
        for field in ("originating_result_identity", "subject", "evidence_snapshot_identity"):
            _text(getattr(self, field), "ExecutableStructureAssessment", field)
        _aware(self.assessed_at, "ExecutableStructureAssessment", "assessed_at")
        if self.intended_structure_kind not in {StructureKind.CALENDAR, StructureKind.VERTICAL}:
            raise ValueError("ExecutableStructureAssessment supports active v1 structures only")
        if self.status is ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED:
            if (
                not self.exact_legs
                or self.available_structure_kind is not self.intended_structure_kind
            ):
                raise ValueError("constructible assessment requires exact intended legs")
            if self.reason_code is not None:
                raise ValueError("constructible assessment cannot carry a failure reason")
        elif self.status is ExecutableStructureStatus.DIFFERENT_STRUCTURE_AVAILABLE:
            if not self.exact_legs or self.available_structure_kind in {
                None,
                self.intended_structure_kind,
            }:
                raise ValueError("different-structure assessment requires truthful alternate legs")
            if self.reason_code is None:
                raise ValueError("different-structure assessment requires a reason")
        else:
            if self.exact_legs or self.available_structure_kind is not None:
                raise ValueError("unresolved assessment cannot claim exact available legs")
            if self.reason_code is None:
                raise ValueError("unresolved assessment requires a typed reason")
        if self.reason_code is not None:
            _text(self.reason_code, "ExecutableStructureAssessment", "reason_code")
        leg_identities = tuple(item.leg.identity for item in self.exact_legs)
        if len(leg_identities) != len(set(leg_identities)):
            raise ValueError("ExecutableStructureAssessment exact legs must be unique")
        diagnostic_roles = tuple(item.role for item in self.selection_diagnostics)
        if len(diagnostic_roles) != len(set(diagnostic_roles)):
            raise ValueError("ExecutableStructureAssessment diagnostic roles must be unique")
        if self.modeled_entry_economics is not None:
            if not self.exact_legs:
                raise ValueError("modeled entry economics require exact legs")
            entry_identities = {
                identity for identity, _ in self.modeled_entry_economics.per_leg_midpoints
            }
            if entry_identities != set(leg_identities):
                raise ValueError("modeled entry economics must cover the exact legs")

    @property
    def identity(self) -> str:
        payload = {
            "assessed_at": self.assessed_at.isoformat(),
            "available_structure_kind": (
                None
                if self.available_structure_kind is None
                else self.available_structure_kind.value
            ),
            "evidence_snapshot_identity": self.evidence_snapshot_identity,
            "exact_legs": [
                {
                    "leg_identity": item.leg.identity,
                    "target_delta": None
                    if item.target_delta is None
                    else str(item.target_delta),
                }
                for item in self.exact_legs
            ],
            "intended_structure_kind": self.intended_structure_kind.value,
            "modeled_entry_economics": (
                None
                if self.modeled_entry_economics is None
                else {
                    "calculated_at": self.modeled_entry_economics.calculated_at.isoformat(),
                    "model_version": self.modeled_entry_economics.model_version,
                    "modeled_net_debit_or_credit": str(
                        self.modeled_entry_economics.modeled_net_debit_or_credit
                    ),
                    "per_leg_midpoints": [
                        [identity, str(value)]
                        for identity, value in self.modeled_entry_economics.per_leg_midpoints
                    ],
                }
            ),
            "originating_result_identity": self.originating_result_identity,
            "reason_code": self.reason_code,
            "selection_diagnostics": [
                {
                    "actual_delta": None
                    if item.actual_delta is None
                    else str(item.actual_delta),
                    "role": item.role,
                    "target_delta": None
                    if item.target_delta is None
                    else str(item.target_delta),
                }
                for item in self.selection_diagnostics
            ],
            "status": self.status.value,
            "subject": self.subject,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


def execution_assessment_to_data(
    assessment: ExecutableStructureAssessment,
) -> dict[str, object]:
    """Canonical JSON-safe public projection, owned with the artifact."""

    return {
        "assessment_identity": assessment.identity,
        "originating_result_identity": assessment.originating_result_identity,
        "subject": assessment.subject,
        "intended_structure_kind": assessment.intended_structure_kind.value,
        "status": assessment.status.value,
        "available_structure_kind": (
            None
            if assessment.available_structure_kind is None
            else assessment.available_structure_kind.value
        ),
        "exact_legs": [
            {
                "canonical_contract_identity": item.canonical_contract_identity,
                "instrument_id_scheme": item.leg.contract.option_contract_id.scheme,
                "instrument_id_value": item.leg.contract.option_contract_id.value,
                "role": item.leg.role,
                "call_or_put": item.leg.contract.option_type.value,
                "expiration": item.leg.contract.expiration.isoformat(),
                "strike": str(item.leg.contract.strike),
                "long_or_short": item.leg.position.value,
                "quantity": str(item.leg.quantity),
                "bid": None if item.leg.contract.bid is None else str(item.leg.contract.bid),
                "ask": None if item.leg.contract.ask is None else str(item.leg.contract.ask),
                "midpoint": None if item.midpoint is None else str(item.midpoint),
                "actual_delta": (
                    None if item.leg.contract.delta is None else str(item.leg.contract.delta)
                ),
                "target_delta": None if item.target_delta is None else str(item.target_delta),
                "source_observed_at": item.leg.contract.observed_at.isoformat(),
            }
            for item in assessment.exact_legs
        ],
        "selection_diagnostics": [
            {
                "role": item.role,
                "target_delta": None if item.target_delta is None else str(item.target_delta),
                "actual_delta": None if item.actual_delta is None else str(item.actual_delta),
                "absolute_delta_deviation": (
                    None
                    if item.absolute_delta_deviation is None
                    else str(item.absolute_delta_deviation)
                ),
            }
            for item in assessment.selection_diagnostics
        ],
        "modeled_entry": (
            None
            if assessment.modeled_entry_economics is None
            else {
                "reference": "midpoint",
                "semantics": "modeled_reference_only",
                "per_leg_references": {
                    identity: str(value)
                    for identity, value in assessment.modeled_entry_economics.per_leg_midpoints
                },
                "modeled_net_debit_or_credit": str(
                    assessment.modeled_entry_economics.modeled_net_debit_or_credit
                ),
                "model_version": assessment.modeled_entry_economics.model_version,
                "calculated_at": assessment.modeled_entry_economics.calculated_at.isoformat(),
            }
        ),
        "evidence_snapshot_identity": assessment.evidence_snapshot_identity,
        "assessed_at": assessment.assessed_at.isoformat(),
        "reason_code": assessment.reason_code,
    }


def serialize_execution_assessment(assessment: ExecutableStructureAssessment) -> str:
    """Canonical durable form retaining exact legs for later analytical modeling."""

    payload = {
        "originating_result_identity": assessment.originating_result_identity,
        "subject": assessment.subject,
        "intended_structure_kind": assessment.intended_structure_kind.value,
        "status": assessment.status.value,
        "exact_legs": [
            {
                "leg": json.loads(serialize_financial_contract(item.leg)),
                "target_delta": None if item.target_delta is None else str(item.target_delta),
            }
            for item in assessment.exact_legs
        ],
        "selection_diagnostics": [
            {
                "role": item.role,
                "target_delta": None if item.target_delta is None else str(item.target_delta),
                "actual_delta": None if item.actual_delta is None else str(item.actual_delta),
            }
            for item in assessment.selection_diagnostics
        ],
        "modeled_entry": (
            None
            if assessment.modeled_entry_economics is None
            else {
                "per_leg_midpoints": [
                    [identity, str(value)]
                    for identity, value in assessment.modeled_entry_economics.per_leg_midpoints
                ],
                "modeled_net_debit_or_credit": str(
                    assessment.modeled_entry_economics.modeled_net_debit_or_credit
                ),
                "model_version": assessment.modeled_entry_economics.model_version,
                "calculated_at": assessment.modeled_entry_economics.calculated_at.isoformat(),
            }
        ),
        "evidence_snapshot_identity": assessment.evidence_snapshot_identity,
        "assessed_at": assessment.assessed_at.isoformat(),
        "reason_code": assessment.reason_code,
        "available_structure_kind": (
            None
            if assessment.available_structure_kind is None
            else assessment.available_structure_kind.value
        ),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def deserialize_execution_assessment(payload: str) -> ExecutableStructureAssessment:
    """Decode only the canonical form produced above and verify its identity."""

    raw = json.loads(payload)
    exact_legs = tuple(
        ResolvedOptionLeg(
            cast(
                OptionLeg,
                deserialize_financial_contract(
                json.dumps(item["leg"], sort_keys=True, separators=(",", ":")).encode()
                ),
            ),
            None if item["target_delta"] is None else Decimal(item["target_delta"]),
        )
        for item in raw["exact_legs"]
    )
    if any(not isinstance(item.leg, OptionLeg) for item in exact_legs):
        raise ValueError("execution assessment legs must decode as OptionLeg")
    entry = raw["modeled_entry"]
    assessment = ExecutableStructureAssessment(
        raw["originating_result_identity"],
        raw["subject"],
        StructureKind(raw["intended_structure_kind"]),
        ExecutableStructureStatus(raw["status"]),
        exact_legs,
        tuple(
            SelectionDiagnostic(
                item["role"],
                None if item["target_delta"] is None else Decimal(item["target_delta"]),
                None if item["actual_delta"] is None else Decimal(item["actual_delta"]),
            )
            for item in raw["selection_diagnostics"]
        ),
        (
            None
            if entry is None
            else ModeledEntryEconomics(
                tuple((item[0], Decimal(item[1])) for item in entry["per_leg_midpoints"]),
                Decimal(entry["modeled_net_debit_or_credit"]),
                entry["model_version"],
                datetime.fromisoformat(entry["calculated_at"]),
            )
        ),
        raw["evidence_snapshot_identity"],
        datetime.fromisoformat(raw["assessed_at"]),
        raw["reason_code"],
        (
            None
            if raw["available_structure_kind"] is None
            else StructureKind(raw["available_structure_kind"])
        ),
    )
    if serialize_execution_assessment(assessment) != payload:
        raise ValueError("execution assessment serialization is not canonical")
    return assessment
