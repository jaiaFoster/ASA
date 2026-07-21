"""Deterministic reconciliation engine (ASA-CORE-003, hardened in ASA-CORE-006 Phase 0).

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
from domain.canonicalization import canonicalize_value
from domain.provenance import Provenance
from domain.references import Confidence
from domain.values import require_tz_aware
from reconciliation.errors import InconsistentGroupError
from reconciliation.rules import (
    compute_confidence,
    fact_identity,
    require_single_group,
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
    if this is the first reconciliation).

    **Version assignment**: ``1`` if no previous fact; unchanged (idempotent
    replay, no new version) if the resolved canonical value is semantically
    equal to ``previous_fact``'s value; ``previous_fact.version + 1``
    otherwise.

    **No stale provenance** (ASA-CORE-006 Phase 0 hardening — the identical
    fix applied to ``indicators.engine.compute_indicator`` in ASA-CORE-005
    Phase 0, see GitHub Issue #47): the returned ``CanonicalFact`` always
    reflects *this call's* actual inputs — fresh
    ``provenance``/``created_time``/``fact_id`` built from the Observations
    and timestamp just supplied — never a verbatim, possibly long-stale
    ``previous_fact`` object. When ``is_new_version`` is ``False``, the
    returned object carries ``previous_fact.version`` (no new version
    number is warranted) but is otherwise a fresh snapshot of this
    reconciliation; callers must not persist it (its ``fact_id`` will
    generally differ from whatever is actually stored under that version,
    since the contributing Observation set may have grown even though the
    resolved value didn't change) — it exists only to report "what the
    value is right now," not to be appended.

    Returns ``(fact, is_new_version)``.

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
    canonical_value = canonicalize_value(selected_value)

    contributing_observation_ids = tuple(
        sorted(obs.observation_id for obs in observations)
    )
    contributing_provider_ids = tuple(
        sorted({obs.provider_id for obs in observations})
    )
    selected_provider_ids = frozenset(
        obs.provider_id for obs in observations
        if canonicalize_value(obs.value) == canonical_value
    )

    is_new_version = (
        previous_fact is None
        or canonicalize_value(previous_fact.value) != canonical_value
    )
    version = (
        1 if previous_fact is None
        else previous_fact.version if not is_new_version
        else previous_fact.version + 1
    )

    confidence_score = compute_confidence(observations, selected_provider_ids)

    provenance = Provenance(
        contributing_observation_ids=contributing_observation_ids,
        contributing_provider_ids=contributing_provider_ids,
        selected_provider_id=selected_provider_id,
        disagreements=disagreements,
        reconciled_at=reconciled_at,
    )

    fact = CanonicalFact(
        fact_id=fact_identity(fact_type, effective_time, canonical_value),
        version=version,
        fact_type=fact_type,
        value=canonical_value,
        confidence=Confidence(score=confidence_score),
        provenance=provenance,
        effective_time=effective_time,
        created_time=reconciled_at,
    )
    return fact, is_new_version
