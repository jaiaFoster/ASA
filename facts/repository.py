"""In-memory, append-only Canonical Fact repository (ASA-CORE-003).

Immutable version history per ``(fact_type, effective_time)`` group (the
v1 grouping key — see ``reconciliation/rules.py``): append-only, no update,
no delete, no mutation of stored records. Query results are tuples of the
stored (frozen) CanonicalFact objects, so no returned collection can
mutate repository state.

Versioning is enforced here as a repository-level invariant — in addition
to ``reconciliation.engine.reconcile``'s own version computation — so an
out-of-sequence or stale-state append fails loudly (``NonMonotonicVersionError``)
rather than corrupting version history.
"""
from __future__ import annotations

from datetime import datetime

from domain.canonical_fact import CanonicalFact
from domain.observation import Observation
from facts.errors import (
    DuplicateFactError,
    FactIdentityCollisionError,
    FactNotFoundError,
    NonMonotonicVersionError,
)
from reconciliation.engine import reconcile
from reconciliation.rules import FactGroupKey, require_single_group


class InMemoryCanonicalFactRepository:
    """Append-only in-memory Canonical Fact store with monotonic versioning."""

    def __init__(self) -> None:
        self._groups: dict[FactGroupKey, list[CanonicalFact]] = {}
        self._by_id: dict[str, CanonicalFact] = {}
        self._all: list[CanonicalFact] = []

    def append(self, fact: CanonicalFact) -> None:
        existing = self._by_id.get(fact.fact_id)
        if existing is not None:
            if existing == fact:
                raise DuplicateFactError(fact.fact_id, fact.version)
            raise FactIdentityCollisionError(fact.fact_id)

        key: FactGroupKey = (fact.fact_type, fact.effective_time)
        history = self._groups.setdefault(key, [])
        expected_version = 1 if not history else history[-1].version + 1
        if fact.version != expected_version:
            raise NonMonotonicVersionError(
                fact.fact_type, fact.effective_time, expected_version, fact.version
            )

        history.append(fact)
        self._by_id[fact.fact_id] = fact
        self._all.append(fact)

    def latest(self, fact_type: str, effective_time: datetime) -> CanonicalFact:
        history = self._groups.get((fact_type, effective_time))
        if not history:
            raise FactNotFoundError(fact_type, effective_time)
        return history[-1]

    def history(self, fact_type: str, effective_time: datetime) -> tuple[CanonicalFact, ...]:
        """Version-ordered (oldest first) history for one group; empty if none."""
        return tuple(self._groups.get((fact_type, effective_time), ()))

    def by_type(self, fact_type: str) -> tuple[CanonicalFact, ...]:
        return tuple(fact for fact in self._all if fact.fact_type == fact_type)

    def by_effective_time(self, effective_time: datetime) -> tuple[CanonicalFact, ...]:
        return tuple(fact for fact in self._all if fact.effective_time == effective_time)

    def reconcile_and_append(
        self,
        observations: tuple[Observation, ...],
        reconciled_at: datetime,
    ) -> CanonicalFact | None:
        """Reconcile one group and append the result if it is a new version.

        Convenience orchestration: looks up this group's latest known
        version, reconciles against it, and appends only when reconciling
        produces a new version. Returns the appended fact, or ``None`` if
        the reconciliation was an idempotent replay (no new version).
        """
        require_single_group(observations)  # raises before any indexing on empty input
        fact_type = observations[0].observation_type
        effective_time = observations[0].effective_time
        try:
            previous = self.latest(fact_type, effective_time)
        except FactNotFoundError:
            previous = None

        fact, is_new_version = reconcile(observations, reconciled_at, previous_fact=previous)
        if not is_new_version:
            return None
        self.append(fact)
        return fact
