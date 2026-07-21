"""Deterministic Indicator engine (ASA-CORE-004, hardened in ASA-CORE-005 Phase 0).

Derives immutable Indicators from Canonical Facts via the indicator
registry (``indicators/registry.py``). Pure orchestration — no repository
access, no randomness, no strategies, no ranking, no broker/provider
access, no external services. A total, deterministic function of its
arguments, making indicator computation fully replayable.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from domain.canonical_fact import CanonicalFact
from domain.canonicalization import canonicalize_value, serialize_canonical
from domain.indicator import Indicator
from domain.references import EvidenceKind, EvidenceReference
from domain.values import require_tz_aware
from indicators.errors import InconsistentIndicatorGroupError
from indicators.registry import DEFAULT_REGISTRY, IndicatorRegistry

INDICATOR_IDENTITY_NAMESPACE = "asa.indicator"
INDICATOR_IDENTITY_VERSION = "v1"


def indicator_identity(
    indicator_type: str,
    source_fact_ids: tuple[str, ...],
    effective_time: datetime,
    calculated_value: object,
) -> str:
    """Deterministic, versioned Indicator identity (algorithm v1).

    Inputs: indicator_type, source_fact_ids, effective_time, calculated
    value — per ticket spec. sha256 over type-tagged, length-prefixed
    serialization, mirroring ``reconciliation.rules.fact_identity``'s
    algorithm style under a distinct namespace. No UUIDs, no sequence
    numbers, no insertion time, no randomness. Content-addressed: unlike
    ``fact_identity`` (which omits source ids), including
    ``source_fact_ids`` here means two computations over different fact
    sets that happen to resolve to the same value do not collide.
    """
    require_tz_aware(effective_time, "indicator_identity", "effective_time")
    sorted_fact_ids = tuple(sorted(source_fact_ids))
    payload = "\n".join(
        (
            INDICATOR_IDENTITY_NAMESPACE,
            INDICATOR_IDENTITY_VERSION,
            serialize_canonical(indicator_type),
            serialize_canonical(sorted_fact_ids),
            serialize_canonical(effective_time),
            serialize_canonical(calculated_value),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_indicator(
    indicator_type: str,
    facts: tuple[CanonicalFact, ...],
    effective_time: datetime,
    created_time: datetime,
    params: dict | None = None,
    previous_indicator: Indicator | None = None,
    registry: IndicatorRegistry = DEFAULT_REGISTRY,
) -> tuple[Indicator, bool]:
    """Compute one Indicator version from Canonical Facts.

    ``facts`` is the full candidate set the registered calculation may
    read from (it sorts and slices internally — see
    ``indicators/calculations.py``). ``previous_indicator`` is the latest
    known version for this ``(indicator_type, effective_time)`` group
    (``None`` for the first computation).

    **Version assignment** mirrors ``reconciliation.engine.reconcile``:
    ``1`` if none prior; unchanged (idempotent replay, no new version) if
    the calculated value is semantically equal (canonicalized comparison
    — ASA-CORE-005 Phase 0 hardening, was a plain ``!=`` before) to
    ``previous_indicator``'s; ``+1`` otherwise.

    **No stale provenance** (ASA-CORE-005 Phase 0 hardening): the returned
    ``Indicator`` always reflects *this call's* actual inputs — fresh
    ``computed_from``/``created_time``/``indicator_id`` built from the
    facts and timestamps just supplied — never a verbatim, possibly
    long-stale previous object. When ``is_new_version`` is ``False``, the
    returned object carries ``previous_indicator.version`` (no new version
    number is warranted) but is otherwise a fresh snapshot of this
    computation; callers must not persist it (its ``indicator_id`` will
    generally differ from whatever is actually stored under that version,
    since the contributing fact set may have grown even though the value
    didn't change) — it exists only to report "what the value is right
    now," not to be appended.

    Returns ``(indicator, is_new_version)``.
    """
    require_tz_aware(effective_time, "compute_indicator", "effective_time")
    require_tz_aware(created_time, "compute_indicator", "created_time")
    params = params or {}

    if previous_indicator is not None:
        if previous_indicator.indicator_type != indicator_type:
            raise InconsistentIndicatorGroupError(
                f"previous_indicator.indicator_type {previous_indicator.indicator_type!r} "
                f"does not match requested indicator_type {indicator_type!r}"
            )
        if previous_indicator.effective_time != effective_time:
            raise InconsistentIndicatorGroupError(
                f"previous_indicator.effective_time {previous_indicator.effective_time!r} "
                f"does not match requested effective_time {effective_time!r}"
            )

    definition = registry.get(indicator_type)
    calculated_value, contributing_facts = definition.compute(facts, params)
    canonical_value = canonicalize_value(calculated_value)

    source_fact_ids = tuple(sorted({fact.fact_id for fact in contributing_facts}))
    computed_from = tuple(
        EvidenceReference(kind=EvidenceKind.CANONICAL_FACT,
                          referenced_id=fact.fact_id, version=fact.version)
        for fact in sorted(contributing_facts, key=lambda f: f.fact_id)
    )

    is_new_version = (
        previous_indicator is None
        or canonicalize_value(previous_indicator.value) != canonical_value
    )
    version = (
        1 if previous_indicator is None
        else previous_indicator.version if not is_new_version
        else previous_indicator.version + 1
    )

    indicator = Indicator(
        indicator_id=indicator_identity(
            indicator_type, source_fact_ids, effective_time, canonical_value
        ),
        version=version,
        indicator_type=indicator_type,
        logic_version=definition.logic_version,
        value=canonical_value,
        computed_from=computed_from,
        effective_time=effective_time,
        created_time=created_time,
    )
    return indicator, is_new_version
