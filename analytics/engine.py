"""Deterministic derived-feature computation engine (ANALYTICS-001).

Invokes one registered feature's pure computation function against
already-canonical input values (never fetched here -- acquisition is
explicitly out of scope, per this sprint's must_not_duplicate_market_data
_acquisition invariant) and wraps the result in the canonical
DerivedFeatureResult envelope. Implements no financial formula itself.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal

from domain import EvidenceReference
from analytics.clock import Clock
from analytics.features import DerivedFeatureResult
from analytics.registry import AnalyticsFeatureDefinition

# A feature computation is a pure function of its named inputs to one
# Decimal value. Different features take wildly different inputs (implied
# volatility needs price/strike/spot/rate/time; DTE needs two dates; a
# moving average needs a price series) -- a uniform Mapping[str, object]
# signature keeps the engine itself generic while each computation stays
# free to validate and interpret its own inputs.
FeatureComputation = Callable[[Mapping[str, object]], Decimal]


def compute_feature(
    definition: AnalyticsFeatureDefinition,
    computation: FeatureComputation,
    inputs: Mapping[str, object],
    *,
    subject_identity: str,
    clock: Clock,
    parameters: tuple[tuple[str, str], ...] = (),
    input_provenance: tuple[EvidenceReference, ...] = (),
) -> DerivedFeatureResult:
    """Execute one registered feature's computation and wrap it canonically.

    ``inputs`` drives the actual computation and may hold any object a
    computation needs (canonical domain values included). ``parameters`` is
    a separate, caller-curated, already-normalized record of the simple
    scalar inputs worth keeping for explainability (e.g. an as-of date or an
    expiration) -- deliberately not auto-derived from ``inputs`` by
    stringifying every value, since a canonical domain object's repr is
    neither normalized text nor a meaningful record on its own.

    Raises whatever the computation itself raises for invalid or
    insufficient input -- this engine performs no isolation of its own;
    unlike a screening strategy run, a feature computation is a synchronous
    helper call within a larger, already-isolated caller.
    """
    value = computation(inputs)
    return DerivedFeatureResult(
        definition.feature_id,
        definition.feature_version,
        subject_identity,
        clock.now(),
        value,
        parameters,
        input_provenance,
    )
