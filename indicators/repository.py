"""In-memory, append-only Indicator repository (ASA-CORE-004).

Immutable version history per ``(indicator_type, effective_time)`` group
(the v1 grouping key — mirrors ``facts/repository.py``'s
``(fact_type, effective_time)`` and the same documented multi-subject
limitation, see PR issue list): append-only, no update, no delete, no
mutation of stored records. Query results are tuples of the stored
(frozen) Indicator objects, so no returned collection can mutate
repository state.

Versioning is enforced here as a repository-level invariant — in addition
to ``indicators.engine.compute_indicator``'s own version computation — so
an out-of-sequence or stale-state append fails loudly
(``NonMonotonicIndicatorVersionError``) rather than corrupting version
history.
"""
from __future__ import annotations

from datetime import datetime

from domain.indicator import Indicator
from indicators.errors import (
    DuplicateIndicatorError,
    IndicatorIdentityCollisionError,
    IndicatorNotFoundError,
    NonMonotonicIndicatorVersionError,
)

IndicatorGroupKey = tuple[str, datetime]


class InMemoryIndicatorRepository:
    """Append-only in-memory Indicator store with monotonic versioning."""

    def __init__(self) -> None:
        self._groups: dict[IndicatorGroupKey, list[Indicator]] = {}
        self._by_id: dict[str, Indicator] = {}
        self._all: list[Indicator] = []

    def append(self, indicator: Indicator) -> None:
        existing = self._by_id.get(indicator.indicator_id)
        if existing is not None:
            if existing == indicator:
                raise DuplicateIndicatorError(indicator.indicator_id, indicator.version)
            raise IndicatorIdentityCollisionError(indicator.indicator_id)

        key: IndicatorGroupKey = (indicator.indicator_type, indicator.effective_time)
        history = self._groups.setdefault(key, [])
        expected_version = 1 if not history else history[-1].version + 1
        if indicator.version != expected_version:
            raise NonMonotonicIndicatorVersionError(
                indicator.indicator_type, indicator.effective_time,
                expected_version, indicator.version,
            )

        history.append(indicator)
        self._by_id[indicator.indicator_id] = indicator
        self._all.append(indicator)

    def latest(self, indicator_type: str, effective_time: datetime) -> Indicator:
        history = self._groups.get((indicator_type, effective_time))
        if not history:
            raise IndicatorNotFoundError(indicator_type, effective_time)
        return history[-1]

    def history(self, indicator_type: str, effective_time: datetime) -> tuple[Indicator, ...]:
        """Version-ordered (oldest first) history for one group; empty if none."""
        return tuple(self._groups.get((indicator_type, effective_time), ()))

    def by_indicator_type(self, indicator_type: str) -> tuple[Indicator, ...]:
        return tuple(ind for ind in self._all if ind.indicator_type == indicator_type)

    def by_fact(self, fact_id: str) -> tuple[Indicator, ...]:
        """All Indicators whose provenance cites the given Canonical Fact id."""
        return tuple(
            ind for ind in self._all
            if any(ref.referenced_id == fact_id for ref in ind.computed_from)
        )
