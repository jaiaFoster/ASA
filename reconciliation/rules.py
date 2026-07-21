"""Deterministic reconciliation rules (ASA-CORE-003).

Pure functions only — no I/O, no repository access, no randomness, no
machine learning, no provider weighting. Every function here is a total,
deterministic function of its explicit arguments, so ``reconciliation/``
can be replayed byte-identically given the same Observation set.

**v1 grouping key.** A Canonical Fact "group" — the set of Observations
reconciled together into successive versions of one logical fact — is
identified by ``(fact_type, effective_time)`` alone. Observation carries no
separate subject/instrument identifier field (ASA-CORE-002); this is a
documented, tested v1 simplification, not an oversight. It means two
different real-world subjects sharing a ``fact_type`` at the same
``effective_time`` (e.g. two different symbols' market prices at the same
instant) are not currently disambiguated. Tracked as a non-blocking
follow-up (see PR for the linked GitHub Issue) — out of scope to resolve
here since the only current provider (ASA-CORE-002's synthetic provider)
and this ticket's test fixtures are single-subject.

**v1 reconciliation policy — unweighted agreement, no provider priority.**
ADR-001 describes reconciliation as "provider priority combined with a
confidence input." This ticket explicitly prohibits provider weighting, and
the ``Provider`` domain object (ASA-CORE-001) carries no priority field to
weight by. v1 therefore resolves disagreement by **provider agreement
count** — the canonical value supported by the most distinct providers
wins; ties break on the lexicographically smallest canonical serialized
value, never on provider identity. This is fully deterministic, treats
every provider identically (no weighting), and makes Confidence and
Provenance functionally meaningful (ADR-001's Alternative 3 concern),
though it does not yet implement ADR-001's provider-priority tiebreak.
Tracked as a non-blocking follow-up pending a Provider-priority
configuration mechanism, which does not exist yet.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime

from domain.observation import Observation
from domain.provenance import ProviderDisagreement
from domain.values import require_tz_aware
from observation.canonicalization import canonicalize_value, serialize_canonical
from reconciliation.errors import EmptyObservationGroupError, InconsistentGroupError

FACT_IDENTITY_NAMESPACE = "asa.canonical_fact"
FACT_IDENTITY_VERSION = "v1"

FactGroupKey = tuple[str, datetime]


def group_by_fact_identity(
    observations: tuple[Observation, ...],
) -> dict[FactGroupKey, tuple[Observation, ...]]:
    """Group Observations by ``(fact_type, effective_time)`` (v1 key).

    Grouping is independent of input order: two calls with the same
    Observations in different orders produce groups with identical
    membership (though tuple order within a group follows input order,
    which downstream rules treat as insignificant — see
    ``resolve_value``'s and ``build_provenance``'s deterministic sorting).
    """
    groups: dict[FactGroupKey, list[Observation]] = defaultdict(list)
    for obs in observations:
        key = (obs.observation_type, obs.effective_time)
        groups[key].append(obs)
    return {key: tuple(members) for key, members in groups.items()}


def require_single_group(observations: tuple[Observation, ...]) -> None:
    if not observations:
        raise EmptyObservationGroupError()
    fact_type = observations[0].observation_type
    effective_time = observations[0].effective_time
    for obs in observations[1:]:
        if obs.observation_type != fact_type:
            raise InconsistentGroupError(
                f"mixed observation_type in reconciliation group: "
                f"{fact_type!r} vs {obs.observation_type!r}"
            )
        if obs.effective_time != effective_time:
            raise InconsistentGroupError(
                f"mixed effective_time in reconciliation group: "
                f"{effective_time!r} vs {obs.effective_time!r}"
            )


def resolve_value(
    observations: tuple[Observation, ...],
) -> tuple[object, tuple[ProviderDisagreement, ...], str]:
    """Resolve one group's Observations to a value (v1 policy, see module doc).

    Returns ``(selected_canonical_value, disagreements, selected_provider_id)``.
    ``disagreements`` preserves every Observation whose canonical value
    differs from the selected value — never discarded. Deterministic and
    independent of input order.
    """
    require_single_group(observations)

    # canonical serialized form -> (canonical value, set of distinct provider_ids, observations)
    by_value: dict[str, tuple[object, set[str], list[Observation]]] = {}
    for obs in observations:
        canonical = canonicalize_value(obs.value)
        key = serialize_canonical(canonical)
        if key not in by_value:
            by_value[key] = (canonical, set(), [])
        by_value[key][1].add(obs.provider_id)
        by_value[key][2].append(obs)

    # Winner: most distinct supporting providers; tie-break on canonical
    # serialized value (deterministic, content-based — never provider identity).
    winning_key = max(
        by_value.keys(),
        key=lambda k: (len(by_value[k][1]), k),
    )
    selected_value = by_value[winning_key][0]

    supporting_provider_ids = sorted(by_value[winning_key][1])
    selected_provider_id = supporting_provider_ids[0]

    disagreements: list[ProviderDisagreement] = []
    for key, (_, _, obs_list) in by_value.items():
        if key == winning_key:
            continue
        for obs in obs_list:
            disagreements.append(
                ProviderDisagreement(
                    provider_id=obs.provider_id,
                    observation_id=obs.observation_id,
                    reported_value=obs.value,
                )
            )
    disagreements.sort(key=lambda d: (d.provider_id, d.observation_id))

    return selected_value, tuple(disagreements), selected_provider_id


def compute_confidence(
    observations: tuple[Observation, ...],
    selected_provider_ids: frozenset[str],
) -> float:
    """Deterministic reconciliation confidence in [0, 1] (v1 formula).

    ``agreement_ratio`` — fraction of distinct contributing providers that
    support the selected value. ``corroboration_factor`` — 0.5 for a
    single supporting provider, 1.0 for two or more (multiple independent
    providers agreeing raises confidence; a single-provider Observation
    set lowers it, per ADR-001). This is an explicit, documented v1
    formula; ADR-001 itself defers the exact formula to a future
    engineering document, so no further design ADR is required for this
    choice specifically (see module docstring for the two items that are
    tracked as follow-ups).
    """
    all_provider_ids = {obs.provider_id for obs in observations}
    agreement_ratio = len(selected_provider_ids) / len(all_provider_ids)
    corroboration_factor = 1.0 if len(selected_provider_ids) >= 2 else 0.5
    return agreement_ratio * corroboration_factor


def fact_identity(fact_type: str, effective_time: datetime, value: object) -> str:
    """Deterministic, versioned Canonical Fact identity (algorithm v1).

    Inputs: fact_type, canonical normalized value, effective_time — per
    ticket spec. sha256 over type-tagged, length-prefixed serialization,
    mirroring ``observation.identity.observation_identity``'s algorithm
    style under a distinct namespace. No UUIDs, no sequence numbers, no
    insertion time, no randomness.

    Note (documented limitation — see module docstring / PR issue list):
    because inputs are exactly the three above, two reconciliations of the
    same group that resolve to the same value produce the same identity
    even if they occur at different versions (e.g. a value that changes
    and later reverts). ``facts/repository.py`` treats a same-identity,
    different-content append as an explicit collision error rather than
    silently corrupting state — fails closed, never silent.
    """
    require_tz_aware(effective_time, "fact_identity", "effective_time")
    payload = "\n".join(
        (
            FACT_IDENTITY_NAMESPACE,
            FACT_IDENTITY_VERSION,
            serialize_canonical(fact_type),
            serialize_canonical(effective_time),
            serialize_canonical(value),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
