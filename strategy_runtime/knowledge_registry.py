"""Generic strategy_id -> knowledge-binding catalog (SPRINT-014
S14-PR-05A, Architect checkpoint: ninth/tenth review).

Mirrors strategy_runtime.registry.StrategyRegistry's own established
shape exactly (immutable constructor over one explicit, finite tuple of
entries; duplicate-key detection inside __init__; a typed "unknown key"
error) so a second, generic-composition-only registry never invents a
competing convention. No dynamic discovery, no ``.register()`` mutator --
a KnowledgeCompositionRegistry is always built from one explicit tuple.

``KnowledgeBinding`` is a ``Protocol``, not an import of the concrete
``strategies.knowledge_contracts.KnowledgeMapping`` dataclass a binding
actually constructs (Architect checkpoint: tenth review -- "Move the
generic binding/declaration contract under strategies/ ... let the
downstream generic orchestrator consume it"): strategy_runtime must never
import strategies/, mirroring StrategyRegistry's own
``StrategyAdapter = Callable[[RuntimeContext], TResult]`` -- a locally
defined generic shape, never a concrete strategy-owned type import.
KnowledgeMapping satisfies this Protocol purely structurally.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, Protocol, TypeVar

from analytics.features import DerivedFactRequest, DerivedFactSet
from domain import CanonicalFact, UnknownReason
from facts.canonical_projection import CanonicalFactRequest

TPayload = TypeVar("TPayload")


class KnowledgeBinding(Protocol[TPayload]):
    """The structural shape the generic composition seam needs from a
    strategy-owned binding: which canonical facts to project, a callback
    computing which derived facts to materialize *from the just-projected
    canonical facts* (never before them -- Architect checkpoint, tenth
    review, item 2), and a callback assembling the final strategy-owned
    payload. No method here computes anything itself; both callables are
    binding-owned.
    """

    canonical_fact_requests: tuple[CanonicalFactRequest, ...]
    compute_derived_fact_requests: Callable[
        [tuple[CanonicalFact, ...]], tuple[DerivedFactRequest, ...] | UnknownReason
    ]
    build_payload: Callable[[tuple[CanonicalFact, ...], DerivedFactSet], TPayload]


class UnknownKnowledgeBindingError(KeyError):
    """Raised when a strategy_id has no registered knowledge binding."""


class DuplicateKnowledgeBindingError(ValueError):
    """Raised when two entries register the same strategy_id in one
    KnowledgeCompositionRegistry.
    """


class KnowledgeCompositionRegistry(Generic[TPayload]):
    __slots__ = ("_entries",)

    def __init__(
        self, entries: tuple[tuple[str, KnowledgeBinding[TPayload]], ...] = ()
    ) -> None:
        registered: dict[str, KnowledgeBinding[TPayload]] = {}
        for strategy_id, mapping in entries:
            if strategy_id in registered:
                raise DuplicateKnowledgeBindingError(strategy_id)
            registered[strategy_id] = mapping
        self._entries = registered

    def strategy_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def is_registered(self, strategy_id: str) -> bool:
        return strategy_id in self._entries

    def mapping_for(self, strategy_id: str) -> KnowledgeBinding[TPayload]:
        try:
            return self._entries[strategy_id]
        except KeyError:
            raise UnknownKnowledgeBindingError(strategy_id) from None
