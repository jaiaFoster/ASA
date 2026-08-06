"""Materialize registered analytics features into immutable,
identity-bearing DerivedFact records (SPRINT-014 S14-PR-04).

DerivedFact/DerivedFactSet (analytics/features.py) and AnalyticsRegistry
(analytics/registry.py) already exist, frozen and tested, but no compute
function has ever actually populated one -- analytics/derived_facts.py's
own compute_* functions return raw Decimal/int/bool values today, consumed
directly by screening/live_adapters.py without ever being wrapped into a
DerivedFact. This module is that missing wrapper: given a value an existing
compute_* function already produced, materialize it as one DerivedFact
whose identity deterministically encodes the feature, subject, and
snapshot digest it was computed from -- so the same (feature, subject,
snapshot) combination always yields the same derived_fact_id (I-07), which
is what "compute once per snapshot and parameter set" (I-08) means in
practice: a caller can check whether that ID already exists in an
already-materialized DerivedFactSet before recomputing.

Never a strategy verdict, never a private per-strategy formula -- this
module materializes a value already computed by a registered feature
definition; it computes nothing itself.
"""

from __future__ import annotations

from datetime import datetime

from analytics.features import DerivedFact, DerivedFactQualityStatus, DerivedFactValue
from analytics.registry import AnalyticsRegistry
from domain import EvidenceReference


def derived_fact_id(feature_id: str, subject: str, snapshot_digest: str) -> str:
    """Deterministic identity for one materialized derived fact: the same
    (feature, subject, snapshot) combination always yields the same ID,
    regardless of when or how many times it is computed.
    """
    return f"{feature_id}:{subject}:{snapshot_digest}"


def materialize_derived_fact(
    registry: AnalyticsRegistry,
    feature_id: str,
    subject: str,
    snapshot_digest: str,
    *,
    value: DerivedFactValue,
    unit: str,
    effective_time: datetime,
    input_evidence: tuple[EvidenceReference, ...],
    quality_status: DerivedFactQualityStatus,
) -> DerivedFact:
    """Wrap an already-computed feature value into one DerivedFact, using
    the registry's own recorded feature_version -- never a second,
    independently maintained version string. Raises UnknownFeatureIdError
    (via registry.get) if ``feature_id`` is not a registered feature.
    """
    definition = registry.get(feature_id)
    return DerivedFact(
        derived_fact_id=derived_fact_id(feature_id, subject, snapshot_digest),
        value=value,
        unit=unit,
        formula_version=definition.feature_version,
        effective_time=effective_time,
        input_evidence=input_evidence,
        quality_status=quality_status,
    )
