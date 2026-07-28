"""Deterministic Derived Fact computation engine."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from analytics.clock import Clock
from analytics.features import (
    DerivedFact,
    DerivedFactQualityStatus,
    DerivedFactValue,
)
from analytics.registry import AnalyticsFeatureDefinition
from domain import EvidenceReference

FeatureComputation = Callable[[Mapping[str, object]], DerivedFactValue]


def compute_feature(
    definition: AnalyticsFeatureDefinition,
    computation: FeatureComputation,
    inputs: Mapping[str, object],
    *,
    clock: Clock,
    unit: str,
    input_evidence: tuple[EvidenceReference, ...] = (),
    quality_status: DerivedFactQualityStatus = DerivedFactQualityStatus.VALID,
) -> DerivedFact:
    """Compute one registered fact without acquisition, policy, or isolation."""

    return DerivedFact(
        derived_fact_id=definition.feature_id,
        value=computation(inputs),
        unit=unit,
        formula_version=definition.feature_version,
        effective_time=clock.now(),
        input_evidence=input_evidence,
        quality_status=quality_status,
    )
