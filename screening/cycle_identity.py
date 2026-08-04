"""Screening-cycle and pair-evaluation identity (SPRINT-013 S13-02).

screening owns minting this identity; it does not own persistence (that is
asa/integrations), the attempt contract (market_data), or query surfaces
(asa/market_data_ops). A cycle spans one scheduled-refresh invocation across
every (strategy_id, subject) pair; a pair evaluation is one
(strategy_id, subject) iteration within that cycle.

Cycle identity is never derived from raw wall-clock time alone -- it is a
deterministic hash of a canonical (invocation_type, slot_id, scope_id)
tuple, so re-processing the same due schedule slot (e.g. after a retry)
yields the identical cycle_id (idempotent at the cycle level), and
overlapping invocations of different kinds (e.g. a scheduled run and a
concurrent manual run) can never collide, because invocation_type is part
of the hashed tuple.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from domain.values import require_tz_aware


def _require_normalized(value: str, owner: str, field_name: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{owner} requires a non-empty normalized {field_name}")
    if ":" in value:
        raise ValueError(f"{owner} {field_name} must not contain ':' (used as a key separator)")


def scope_identity(universe: tuple[tuple[str, str], ...]) -> str:
    """Deterministic, order-independent identity for a screening universe
    (the set of (strategy_id, subject) pairs one cycle covers). Two calls
    with the same pairs in any order return the same scope id.
    """
    if not universe:
        raise ValueError("scope_identity requires a non-empty universe")
    payload = ",".join(sorted(f"{strategy_id}:{subject}" for strategy_id, subject in universe))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def manual_invocation_slot_id(now: datetime) -> str:
    """A slot substitute for invocations with no ScheduledRefreshSlot (a
    manual or on-demand run outside the exchange-calendar schedule).
    Timezone-normalized to UTC before hashing, so the same instant always
    yields the same id regardless of the caller's tzinfo representation.
    Never used alone as a cycle_id -- only as one component of the
    (invocation_type, slot_id, scope_id) tuple new_screening_cycle_id hashes.
    """
    require_tz_aware(now, "manual_invocation_slot_id", "now")
    normalized = now.astimezone(UTC).isoformat()
    return f"manual_{hashlib.sha256(normalized.encode()).hexdigest()[:16]}"


def new_screening_cycle_id(*, invocation_type: str, slot_id: str, scope_id: str) -> str:
    """Deterministic identity for one screening cycle, derived from a
    canonical (invocation_type, slot_id, scope_id) tuple. The same tuple
    always yields the same cycle_id.
    """
    for name, value in (
        ("invocation_type", invocation_type),
        ("slot_id", slot_id),
        ("scope_id", scope_id),
    ):
        _require_normalized(value, "new_screening_cycle_id", name)
    payload = f"{invocation_type}:{slot_id}:{scope_id}"
    return f"cycle_{hashlib.sha256(payload.encode()).hexdigest()}"


def pair_evaluation_id(screening_cycle_id: str, strategy_id: str, subject_identity: str) -> str:
    """Deterministic identity for one (strategy_id, subject) evaluation
    within a cycle -- a pure composite key, already unique per cycle (each
    pair is evaluated at most once per cycle) and reproducible for
    tests/replay. ``:`` is rejected in the components (not just the cycle
    id, which is itself a fixed-format hash) so two distinct pairs can
    never collide onto the same composite string.
    """
    _require_normalized(screening_cycle_id, "pair_evaluation_id", "screening_cycle_id")
    _require_normalized(strategy_id, "pair_evaluation_id", "strategy_id")
    _require_normalized(subject_identity, "pair_evaluation_id", "subject_identity")
    return f"{screening_cycle_id}:{strategy_id}:{subject_identity}"
