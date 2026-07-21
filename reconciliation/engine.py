"""Deterministic reconciliation engine (ASA-CORE-003).

Pure orchestration over ``reconciliation/rules.py``: given one group's
Observations (all sharing ``fact_type`` and ``effective_time`` — see
``rules.py`` module docstring for the v1 grouping key), produces the next
immutable ``CanonicalFact`` version. No I/O, no repository access, no
randomness, no machine learning, no provider weighting — a total,
deterministic function of its arguments, making reconciliation fully
replayable.
"""
from __future__ import annotations

from datetime import datetime

from domain.canonical_fact import CanonicalFact
from domain.provenance import Provenance
from domain.references import Confidence
from domain.values import require_tz_aware
from domain.canonicalization import canonicalize_value
from reconciliation.errors import InconsistentGroupError
from reconciliation.rules import (
    require_single_group,
    compute_confidence,
    fact_identity,
    resolve_value,
)
from domain.observation import Observation


def reconcile(
    observations: tuple[Observation, ...],
    reconciled_at: datetime,
    previous_fact: CanonicalFact | None = None,
) -> tuple[CanonicalFact, bool]:
    """Reconcile one group's Observations into a Canonical Fact.

    ``previous_fact`` is the latest known version for this group (``None``
    if this is the first reconciliation). Version assignment: ``1`` if no
    previous fact; ``previous_fact.version`` (unchanged) if the resolved
    canonical value equals ``previous_fact``'s value (idempotent replay —
    no new version); ``previous_fact.version + 1`` otherwise.

    Returns ``(fact, is_new_version)``. When ``is_new_version`` is False,
    ``fact`` is byte-identical to ``previous_fact`` in every field except
    possibly ``provenance``/``confidence`` (new corroborating evidence can
    arrive without changing the resolved value); callers that only care
    about the stored version history should not append in that case.

    Raises ``InconsistentGroupError`` if ``previous_fact`` belongs to a
    different (fact_type, effective_time) group than ``observations``.
    """
    require_single_group(observations)
    require_tz_aware(reconciled_at, "reconcile", "reconciled_at")

    fact_type = observations[0].observation_type
    effective_time = observations[0].effective_time

    if previous_fact is not None:
        if previous_fact.fact_type != fact_type:
            raise InconsistentGroupError(
                f"previous_fact.fact_type {previous_fact.fact_type!r} does not "
                f"match observation group's fact_type {fact_type!r}"
            )
        if previous_fact.effective_time != effective_time:
            raise InconsistentGroupError(
                f"previous_fact.effective_time {previous_fact.effective_time!r} does "
                f"not match observation group's effective_time {effective_time!r}"
            )

    selected_value, disagreements, selected_provider_id = resolve_value(observations)

    contributing_observation_ids = tuple(
        sorted(obs.observation_id for obs in observations)
    )
    contributing_provider_ids = tuple(
        sorted({obs.provider_id for obs in observations})
    )
    selected_provider_ids = frozenset(
        obs.provider_id for obs in observations
        if canonicalize_value(obs.value) == selected_value
    )

    is_new_version = (
        previous_fact is None
        or canonicalize_value(previous_fact.value) != selected_value
    )

    if not is_new_version:
        return previous_fact, False

    version = 1 if previous_fact is None else previous_fact.version + 1
    confidence_score = compute_confidence(observations, selected_provider_ids)

    provenance = Provenance(
        contributing_observation_ids=contributing_observation_ids,
        contributing_provider_ids=contributing_provider_ids,
        selected_provider_id=selected_provider_id,
        disagreements=disagreements,
        reconciled_at=reconciled_at,
    )

    fact = CanonicalFact(
        fact_id=fact_identity(fact_type, effective_time, selected_value),
        version=version,
        fact_type=fact_type,
        value=selected_value,
        confidence=Confidence(score=confidence_score),
        provenance=provenance,
        effective_time=effective_time,
        created_time=reconciled_at,
    )
    return fact, True
