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

import hashlib
import json
from datetime import datetime

from analytics.features import DerivedFact, DerivedFactQualityStatus, DerivedFactValue
from analytics.registry import AnalyticsRegistry
from domain import EvidenceReference

DerivedFactParameters = tuple[tuple[str, str], ...]


def _parameter_identity(parameters: DerivedFactParameters) -> str:
    ordered = tuple(sorted(parameters))
    payload = json.dumps(ordered, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def derived_fact_id(
    feature_id: str,
    subject: str,
    snapshot_digest: str,
    *,
    parameters: DerivedFactParameters = (),
) -> str:
    """Deterministic identity for one materialized derived fact: the same
    (feature, subject, snapshot, parameters) combination always yields the
    same ID, regardless of when or how many times it is computed.

    ``parameters`` is I-07's own selection-parameter component (SPRINT-014
    S14-PR-05A, Architect checkpoint: seventh review) -- Sprint 14
    requires derived identity to include subject, time, fact/version,
    parameters, and snapshot digest; the original three-argument shape
    silently omitted the parameters component entirely, which is unsafe
    for any feature whose *value* depends on which of several equally
    valid selections (e.g. which contract, which expiration pair) a
    strategy's own pure policy happened to pick from the same
    subject/snapshot -- two different selections would otherwise collide
    on one derived_fact_id for two different values. Backward compatible
    by construction: omitting ``parameters`` (the default, still correct
    for every feature whose value cannot vary within one subject/snapshot)
    reproduces the exact same ID the original three-argument form always
    produced. When supplied, ``parameters`` must already be normalized,
    orderable key/value text pairs -- the same convention
    DemandExpansion.selections already establishes -- never carried inside
    ``subject`` itself.
    """
    if not parameters:
        return f"{feature_id}:{subject}:{snapshot_digest}"
    return f"{feature_id}:{subject}:{snapshot_digest}:{_parameter_identity(parameters)}"


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
    parameters: DerivedFactParameters = (),
) -> DerivedFact:
    """Wrap an already-computed feature value into one DerivedFact, using
    the registry's own recorded feature_version -- never a second,
    independently maintained version string. Raises UnknownFeatureIdError
    (via registry.get) if ``feature_id`` is not a registered feature.
    """
    definition = registry.get(feature_id)
    return DerivedFact(
        derived_fact_id=derived_fact_id(
            feature_id, subject, snapshot_digest, parameters=parameters
        ),
        value=value,
        unit=unit,
        formula_version=definition.feature_version,
        effective_time=effective_time,
        input_evidence=input_evidence,
        quality_status=quality_status,
    )
