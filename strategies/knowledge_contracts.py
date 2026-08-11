"""The generic binding/declaration contract a strategy-specific
integration binding returns (SPRINT-014 S14-PR-05A, Architect checkpoint:
tenth review, corrective knowledge-contract pass -- "KnowledgeMapping does
not belong in analytics/features.py. It contains a strategy payload-
construction callback and canonical-fact requests; analytics is supposed
to own calculations/derived facts, not strategy-binding orchestration.
Move the generic binding/declaration contract under strategies/").

Lives here, not strategy_runtime/, because strategy_runtime must never
import strategies/ (mirrors strategy_runtime.registry.StrategyRegistry's
own established genericity: a StrategyAdapter is a bare
``Callable[[RuntimeContext], TResult]`` strategy_runtime defines locally,
never a concrete strategy-owned type strategy_runtime imports).
strategy_runtime/knowledge_registry.py's own KnowledgeBinding Protocol
describes the same structural shape this dataclass provides, so a
KnowledgeMapping instance satisfies it purely structurally -- no import
relationship between the two packages exists in either direction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from analytics.features import DerivedFactRequest, DerivedFactSet
from domain import CanonicalFact, UnknownReason
from facts.canonical_projection import CanonicalFactRequest

TPayload = TypeVar("TPayload")


@dataclass(frozen=True, slots=True)
class KnowledgeMapping(Generic[TPayload]):
    """A strategy-specific integration binding's complete declaration for
    one composition: which canonical facts to project, a callback that
    computes and describes which derived facts to materialize *from the
    just-projected canonical facts* (Architect checkpoint: tenth review,
    item 2 -- "structural selection -> canonical fact projection ->
    registered analytics execution -> DerivedFactSet materialization",
    literally restored by deferring analytics computation until the
    generic orchestrator hands back projected CanonicalFacts, never
    precomputed beforehand), and how to assemble the final strategy-owned
    payload once both are ready. The generic orchestrator never has to
    know the payload's own shape, nor what ``compute_derived_fact_requests``
    actually computes -- it only calls it, once, with the facts it just
    projected.
    """

    canonical_fact_requests: tuple[CanonicalFactRequest, ...]
    compute_derived_fact_requests: Callable[
        [tuple[CanonicalFact, ...]], tuple[DerivedFactRequest, ...] | UnknownReason
    ]
    build_payload: Callable[[tuple[CanonicalFact, ...], DerivedFactSet], TPayload]
