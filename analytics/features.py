"""Canonical derived-feature result contract (ANALYTICS-001).

One immutable, canonically serializable output of one registered analytics
feature computation. Every field here is deliberately generic -- this
module implements no financial formula itself (implied volatility, DTE,
RSI, ...); it only defines the shape every such computation's result must
take, so any future feature is reusable through the same contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from domain import EvidenceReference
from domain.values import require_tz_aware


def _normalized_text(value: str, owner: str, field_name: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{owner}.{field_name} must be non-empty normalized text")


@dataclass(frozen=True, slots=True)
class DerivedFeatureResult:
    """One immutable, canonically serializable derived-feature computation.

    ``parameters`` records the exact named inputs the computation used
    (already-normalized string values only, never a raw object) so the
    result stays explainable and reproducible without needing to keep the
    original canonical market-data objects around.
    """

    feature_id: str
    feature_version: str
    subject_identity: str
    as_of: datetime
    value: Decimal
    parameters: tuple[tuple[str, str], ...]
    input_provenance: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        for name in ("feature_id", "feature_version", "subject_identity"):
            _normalized_text(getattr(self, name), "DerivedFeatureResult", name)
        require_tz_aware(self.as_of, "DerivedFeatureResult", "as_of")
        parameter_names = tuple(name for name, _ in self.parameters)
        if len(set(parameter_names)) != len(parameter_names):
            raise ValueError("DerivedFeatureResult.parameters keys must be unique")
        for name, param_value in self.parameters:
            if not name or name != name.strip():
                raise ValueError("DerivedFeatureResult.parameters keys must be normalized text")
            if param_value != param_value.strip():
                raise ValueError(
                    "DerivedFeatureResult.parameters values must be normalized text"
                )
