"""In-memory, append-only Observation repository (ASA-CORE-002).

Deterministic storage semantics for immutable Observations (ADR-001):
append-only, no update, no delete, no mutation of stored records. Query
results are tuples (immutable) of the stored Observation objects (which are
themselves frozen), so no returned collection can mutate repository state.

Query semantics (documented, deterministic):
- ``all``            — insertion order.
- ``by_provider``    — insertion order among matching records.
- ``by_type``        — insertion order among matching records.
- ``by_time_range``  — inclusive start, exclusive end, on ``effective_time``,
                       preserving insertion order among matches.
- ``get`` on a missing identity raises ``ObservationNotFoundError``.

Duplicate behavior:
- same identity, same record      → ``DuplicateObservationError``
- same identity, different record → ``IdentityCollisionError`` (original
                                    record preserved)
"""
from __future__ import annotations

from datetime import datetime

from domain.observation import Observation
from observation.errors import (
    DuplicateObservationError,
    IdentityCollisionError,
    ObservationNotFoundError,
)


class InMemoryObservationRepository:
    """Append-only in-memory Observation store with deterministic ordering."""

    def __init__(self) -> None:
        # dict preserves insertion order; keys are observation_ids.
        self._records: dict[str, Observation] = {}

    def append(self, observation: Observation) -> None:
        existing = self._records.get(observation.observation_id)
        if existing is not None:
            if existing == observation:
                raise DuplicateObservationError(observation.observation_id)
            raise IdentityCollisionError(observation.observation_id)
        self._records[observation.observation_id] = observation

    def get(self, observation_id: str) -> Observation:
        try:
            return self._records[observation_id]
        except KeyError:
            raise ObservationNotFoundError(observation_id) from None

    def exists(self, observation_id: str) -> bool:
        return observation_id in self._records

    def all(self) -> tuple[Observation, ...]:
        return tuple(self._records.values())

    def by_provider(self, provider_id: str) -> tuple[Observation, ...]:
        return tuple(
            record for record in self._records.values()
            if record.provider_id == provider_id
        )

    def by_type(self, observation_type: str) -> tuple[Observation, ...]:
        return tuple(
            record for record in self._records.values()
            if record.observation_type == observation_type
        )

    def by_time_range(self, start: datetime, end: datetime) -> tuple[Observation, ...]:
        """Records with ``start <= effective_time < end``, in insertion order."""
        return tuple(
            record for record in self._records.values()
            if start <= record.effective_time < end
        )
