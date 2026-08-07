"""Immutable, typed, provenance-bearing Derived Fact contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Generic, TypeVar

from domain import CanonicalFact, CanonicalFactRequest, EvidenceReference
from domain.values import require_tz_aware

TPayload = TypeVar("TPayload")

DerivedFactValue = Decimal | int | bool | date | tuple[Decimal, ...]


class DerivedFactQualityStatus(StrEnum):
    """Data quality only; never a strategy verdict."""

    VALID = "valid"
    DEGRADED = "degraded"
    INSUFFICIENT = "insufficient"


def _normalized_text(value: str, owner: str, field_name: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{owner}.{field_name} must be non-empty normalized text")


def _value_data(value: DerivedFactValue) -> object:
    if isinstance(value, Decimal):
        return {"type": "decimal", "value": str(value)}
    if isinstance(value, datetime):
        return {"type": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"type": "date", "value": value.isoformat()}
    if isinstance(value, tuple):
        return {"type": "decimal_tuple", "value": [str(item) for item in value]}
    if isinstance(value, bool):
        return {"type": "boolean", "value": value}
    return {"type": "integer", "value": value}


@dataclass(frozen=True, slots=True)
class DerivedFact:
    """One deterministic point-in-time calculation over canonical evidence."""

    derived_fact_id: str
    value: DerivedFactValue
    unit: str
    formula_version: str
    effective_time: datetime
    input_evidence: tuple[EvidenceReference, ...]
    quality_status: DerivedFactQualityStatus

    def __post_init__(self) -> None:
        for name in ("derived_fact_id", "unit", "formula_version"):
            _normalized_text(getattr(self, name), "DerivedFact", name)
        require_tz_aware(self.effective_time, "DerivedFact", "effective_time")
        if len(set(self.input_evidence)) != len(self.input_evidence):
            raise ValueError("DerivedFact.input_evidence must be unique")
        object.__setattr__(
            self,
            "input_evidence",
            tuple(
                sorted(
                    self.input_evidence,
                    key=lambda item: (
                        item.kind.value,
                        item.referenced_id,
                        item.version or 0,
                    ),
                )
            ),
        )

    @property
    def identity(self) -> str:
        payload = {
            "namespace": "asa.derived_fact",
            "version": "v1",
            "derived_fact_id": self.derived_fact_id,
            "value": _value_data(self.value),
            "unit": self.unit,
            "formula_version": self.formula_version,
            "effective_time": self.effective_time.isoformat(),
            "input_evidence": [
                {
                    "kind": item.kind.value,
                    "referenced_id": item.referenced_id,
                    "version": item.version,
                }
                for item in self.input_evidence
            ],
            "quality_status": self.quality_status.value,
        }
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class DerivedFactSet:
    """Named facts with deterministic ordering and lookup."""

    facts: tuple[DerivedFact, ...]

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.facts, key=lambda item: item.derived_fact_id))
        identifiers = tuple(item.derived_fact_id for item in ordered)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("DerivedFactSet fact IDs must be unique")
        object.__setattr__(self, "facts", ordered)

    def get(self, derived_fact_id: str) -> DerivedFact:
        for fact in self.facts:
            if fact.derived_fact_id == derived_fact_id:
                return fact
        raise KeyError(derived_fact_id)


@dataclass(frozen=True, slots=True)
class DerivedFactRequest:
    """One already-computed analytics value a binding wants materialized
    into a DerivedFact (SPRINT-014 S14-PR-05A, Architect checkpoint: ninth
    review). The binding computes ``value`` itself -- this request carries
    only the data materialize_derived_fact() itself needs; the generic
    orchestrator performs that one call, never the computation.
    """

    feature_id: str
    subject: str
    value: DerivedFactValue
    unit: str
    input_evidence: tuple[EvidenceReference, ...]
    quality_status: DerivedFactQualityStatus
    parameters: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class KnowledgeMapping(Generic[TPayload]):
    """A strategy-specific integration binding's complete, already-computed
    recipe for one composition (SPRINT-014 S14-PR-05A, Architect
    checkpoint: ninth review) -- the canonical/derived fact requests a
    generic orchestrator must resolve, plus a callback assembling the
    strategy-owned payload from the resolved facts. The orchestrator never
    knows ``TPayload``'s shape.
    """

    canonical_fact_requests: tuple[CanonicalFactRequest, ...]
    derived_fact_requests: tuple[DerivedFactRequest, ...]
    build_payload: Callable[[tuple[CanonicalFact, ...], DerivedFactSet], TPayload]
