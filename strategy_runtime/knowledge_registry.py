"""Generic strategy_id -> KnowledgeMapping catalog (SPRINT-014 S14-PR-05A,
Architect checkpoint: ninth review).

Mirrors strategy_runtime.registry.StrategyRegistry's own established
shape exactly (immutable constructor over one explicit, finite tuple of
entries; duplicate-key detection inside __init__; a typed "unknown key"
error) so a second, generic-composition-only registry never invents a
competing convention. No dynamic discovery, no ``.register()`` mutator --
a KnowledgeCompositionRegistry is always built from one explicit tuple.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from analytics.features import KnowledgeMapping

TPayload = TypeVar("TPayload")


class UnknownKnowledgeBindingError(KeyError):
    """Raised when a strategy_id has no registered KnowledgeMapping."""


class DuplicateKnowledgeBindingError(ValueError):
    """Raised when two entries register the same strategy_id in one
    KnowledgeCompositionRegistry.
    """


class KnowledgeCompositionRegistry(Generic[TPayload]):
    __slots__ = ("_entries",)

    def __init__(
        self, entries: tuple[tuple[str, KnowledgeMapping[TPayload]], ...] = ()
    ) -> None:
        registered: dict[str, KnowledgeMapping[TPayload]] = {}
        for strategy_id, mapping in entries:
            if strategy_id in registered:
                raise DuplicateKnowledgeBindingError(strategy_id)
            registered[strategy_id] = mapping
        self._entries = registered

    def strategy_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def is_registered(self, strategy_id: str) -> bool:
        return strategy_id in self._entries

    def mapping_for(self, strategy_id: str) -> KnowledgeMapping[TPayload]:
        try:
            return self._entries[strategy_id]
        except KeyError:
            raise UnknownKnowledgeBindingError(strategy_id) from None
