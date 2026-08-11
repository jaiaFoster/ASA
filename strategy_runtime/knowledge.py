"""Generic read-only strategy knowledge envelope (SPRINT-014 S14-PR-05A,
Architect checkpoint: ninth review -- "the generic read-only knowledge
composition increment").

``ReadOnlyStrategyInput`` is the one immutable envelope Sprint 14's target
flow hands to a strategy's own read-only evaluation step: a sealed
snapshot's own identity, the canonical facts and immutable DerivedFactSet
already materialized from it, and one strategy-owned, runtime-opaque
payload. No plan, fulfillment, provider, transport, budget, repository, or
diagnostic type appears anywhere here -- a strategy's own evaluation step
receives exactly this and nothing else.

``CanonicalFactRequest`` (domain/canonical_fact.py) and
``DerivedFactRequest``/``KnowledgeMapping`` (analytics/features.py) are the
generic, strategy-blind vocabulary any strategy-specific integration
binding uses to tell the generic orchestrator
(strategy_runtime/knowledge_composition.py) *what* to project and
materialize. They live in domain/analytics rather than here because
strategies/ -- which must build them -- cannot import strategy_runtime
(architecture boundary); domain and analytics are the lowest layers every
consumer can already reach.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar

from analytics.features import DerivedFactSet
from domain import CanonicalFact

TPayload = TypeVar("TPayload")


@dataclass(frozen=True, slots=True)
class ReadOnlyStrategyInput(Generic[TPayload]):
    """The one thing a strategy's own read-only evaluation step consumes.

    ``payload`` is opaque to every generic component that touches this
    type (the orchestrator that builds it, any future generic runtime
    dispatcher) -- only the strategy-owned evaluator that receives it
    knows its shape.
    """

    snapshot_id: str
    snapshot_digest: str
    effective_time: datetime
    canonical_facts: tuple[CanonicalFact, ...]
    derived_facts: DerivedFactSet
    payload: TPayload
