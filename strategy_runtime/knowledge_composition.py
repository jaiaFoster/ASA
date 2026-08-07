"""Generic, registry/callback-driven read-only knowledge composition
(SPRINT-014 S14-PR-05A, Architect checkpoint: ninth review -- "the
orchestrator that invokes bindings must be generic and registry/callback-
driven", never an if/elif branch naming any one strategy's own id).

``compose_strategy_knowledge`` is Sprint 14's target flow, restored
literally: strategy-owned structural selection has already run by the
time this function is called (its own output is what a binding's
KnowledgeMapping was built from); this function performs the next two
steps -- canonical fact projection, then registered-analytics derived-
fact materialization -- generically, before handing the result on to
strategy evaluation. It never computes a value itself (no compute_*
call, no financial formula): every value it projects/materializes was
already computed by whatever KnowledgeMapping the caller registered.

Contains no strategy name, no strategy-specific import, and no branch on
strategy_id beyond one generic KnowledgeCompositionRegistry.mapping_for()
lookup -- proven by tests/architecture/test_knowledge_composition_boundaries.py's
own textual sweep, and directly by tests/strategy_runtime/test_knowledge_composition.py's
synthetic second-binding registration.
"""

from __future__ import annotations

from datetime import datetime

from analytics.derived_fact_materialization import materialize_derived_fact
from analytics.derived_facts import DERIVED_FACT_REGISTRY
from analytics.features import DerivedFactSet
from domain import CanonicalFact, UnknownReason
from market_data.snapshot import MarketSnapshot
from screening.subject_fact_projection import project_scalar_canonical_fact, resolution_for
from strategy_runtime.knowledge import ReadOnlyStrategyInput, TPayload
from strategy_runtime.knowledge_registry import KnowledgeCompositionRegistry


def compose_strategy_knowledge(
    snapshot: MarketSnapshot,
    registry: KnowledgeCompositionRegistry[TPayload],
    strategy_id: str,
    *,
    subject: str,
    effective_time: datetime,
) -> ReadOnlyStrategyInput[TPayload] | UnknownReason:
    """Project every canonical fact and materialize every derived fact
    ``registry.mapping_for(strategy_id)`` requests, then hand both --
    plus the mapping's own already-built payload -- back as one immutable
    ReadOnlyStrategyInput. Raises UnknownKnowledgeBindingError (via
    ``registry.mapping_for``) for an unregistered strategy_id -- a
    genuine caller-side defect, never a typed UNKNOWN. Returns a typed
    UnknownReason (never raises otherwise) if any requested canonical
    fact's own grounding resolution is UNRESOLVED.
    """
    mapping = registry.mapping_for(strategy_id)

    canonical_facts: list[CanonicalFact] = []
    for request in mapping.canonical_fact_requests:
        resolution = resolution_for(snapshot, request.capability)
        fact = project_scalar_canonical_fact(
            resolution,
            value=request.value,
            subject=request.subject,
            fact_type=request.fact_type,
            snapshot_digest=snapshot.snapshot_digest,
            effective_time=effective_time,
        )
        if fact is None:
            return UnknownReason("resolution_unresolved")
        canonical_facts.append(fact)

    derived_facts = tuple(
        materialize_derived_fact(
            DERIVED_FACT_REGISTRY,
            request.feature_id,
            request.subject,
            snapshot.snapshot_digest,
            value=request.value,
            unit=request.unit,
            effective_time=effective_time,
            input_evidence=request.input_evidence,
            quality_status=request.quality_status,
            parameters=request.parameters,
        )
        for request in mapping.derived_fact_requests
    )
    derived_fact_set = DerivedFactSet(derived_facts)

    payload = mapping.build_payload(tuple(canonical_facts), derived_fact_set)
    return ReadOnlyStrategyInput(
        snapshot_id=snapshot.snapshot_id,
        snapshot_digest=snapshot.snapshot_digest,
        effective_time=effective_time,
        canonical_facts=tuple(canonical_facts),
        derived_facts=derived_fact_set,
        payload=payload,
    )
