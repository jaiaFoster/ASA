"""Generic, registry/callback-driven read-only knowledge composition
(SPRINT-014 S14-PR-05A, Architect checkpoint: ninth review -- "the
orchestrator that invokes bindings must be generic and registry/callback-
driven", never an if/elif branch naming any one strategy's own id).

``compose_strategy_knowledge`` is Sprint 14's target flow, restored
literally and in the correct order (Architect checkpoint: tenth review,
item 2): strategy-owned structural selection has already run by the time
this function is called; this function then (1) projects every requested
canonical fact, (2) hands those just-projected facts to the binding's own
``compute_derived_fact_requests`` callback so registered analytics runs
*after* canonical projection, never before it, and (3) materializes
whatever derived-fact requests that callback returns. It never computes a
value itself (no compute_* call, no financial formula) -- every value it
materializes was computed by the callback it just invoked, using the
facts this function itself already projected.

Every canonical/derived fact's own ``effective_time`` is the sealed
snapshot's own ``as_of`` -- never a caller-supplied value (Architect
checkpoint: tenth review, item 1). A future production caller cannot
recreate the same-snapshot/different-identity defect this closed, because
there is no temporal parameter here for it to pass.

Trusts a request's ``value`` (matching facts.canonical_projection.
project_canonical_fact's own explicit trust boundary) but no longer trusts
a request's own claimed *provenance* (Architect checkpoint: tenth review,
item 3): a CanonicalFactRequest's claimed observation_id is checked
against the snapshot's own resolution for that capability, and a
DerivedFactRequest's own input_evidence is checked against the facts this
composition actually just projected and the snapshot's own observations --
never merely against a plausible-looking capability or an empty evidence
tuple. A CANONICAL_FACT evidence reference must match this composition's
own projected fact by both id *and* version (Architect checkpoint:
eleventh review -- EvidenceReference is a pinned reference to a specific
version, not merely an id); an OBSERVATION reference must exist in the
sealed snapshot and carry no version (observations are unversioned,
append-only); any other evidence kind (currently INDICATOR) is rejected
outright -- this seam validates two kinds, never passes a third through
unchecked. Every mismatch raises SealedEvidenceProvenanceError, the same
invariant/provenance failure screening.subject_fact_projection's own
sealed-evidence check raises -- never a typed UnknownReason.

Contains no strategy name, no strategy-specific import, and no branch on
strategy_id beyond one generic KnowledgeCompositionRegistry.mapping_for()
lookup -- proven by tests/architecture/test_knowledge_composition_boundaries.py's
own textual sweep, and directly by a synthetic second-binding
registration exercised in the generic composition test suite under
tests/strategy_runtime/.
"""

from __future__ import annotations

from analytics.derived_fact_materialization import materialize_derived_fact
from analytics.derived_facts import DERIVED_FACT_REGISTRY
from analytics.features import DerivedFactSet
from domain import CanonicalFact, EvidenceKind, UnknownReason
from market_data.snapshot import MarketSnapshot
from screening.subject_fact_projection import (
    SealedEvidenceProvenanceError,
    project_scalar_canonical_fact,
    resolution_for,
)
from strategy_runtime.knowledge import ReadOnlyStrategyInput, TPayload
from strategy_runtime.knowledge_registry import KnowledgeCompositionRegistry


def compose_strategy_knowledge(
    snapshot: MarketSnapshot,
    registry: KnowledgeCompositionRegistry[TPayload],
    strategy_id: str,
    *,
    subject: str,
) -> ReadOnlyStrategyInput[TPayload] | UnknownReason:
    """Project every canonical fact ``registry.mapping_for(strategy_id)``
    requests, invoke its ``compute_derived_fact_requests`` callback with
    those projected facts, then materialize whatever it returns -- handing
    both, plus the mapping's own payload, back as one immutable
    ReadOnlyStrategyInput. Raises UnknownKnowledgeBindingError (via
    ``registry.mapping_for``) for an unregistered strategy_id -- a
    genuine caller-side defect, never a typed UNKNOWN. Returns a typed
    UnknownReason (never raises otherwise) if any requested canonical
    fact's own grounding resolution is UNRESOLVED, or if the binding's own
    callback returns one (e.g. for a genuine analytics data gap only
    discoverable once that callback actually runs).
    """
    mapping = registry.mapping_for(strategy_id)

    canonical_facts: list[CanonicalFact] = []
    for request in mapping.canonical_fact_requests:
        resolution = resolution_for(snapshot, request.capability)
        selected = resolution.selected_observation
        if selected is not None and selected.observation_id != request.observation_id:
            raise SealedEvidenceProvenanceError(
                f"canonical fact request (fact_type={request.fact_type!r}, "
                f"subject={request.subject!r}) claims observation "
                f"{request.observation_id!r}, but the snapshot's own "
                f"{request.capability.value} resolution selected "
                f"{selected.observation_id!r}"
            )
        fact = project_scalar_canonical_fact(
            resolution,
            value=request.value,
            subject=request.subject,
            fact_type=request.fact_type,
            snapshot_digest=snapshot.snapshot_digest,
            effective_time=snapshot.as_of,
        )
        if fact is None:
            return UnknownReason("resolution_unresolved")
        canonical_facts.append(fact)
    canonical_facts_tuple = tuple(canonical_facts)

    derived_requests = mapping.compute_derived_fact_requests(canonical_facts_tuple)
    if isinstance(derived_requests, UnknownReason):
        return derived_requests

    # Keyed by fact_id -> version, not merely a set of ids (Architect
    # checkpoint: eleventh review): EvidenceReference is a pinned
    # reference to a *specific version* (domain/references.py's own
    # contract), so a CANONICAL_FACT evidence reference must match this
    # composition's own projected version exactly, never just its id.
    projected_fact_versions = {fact.fact_id: fact.version for fact in canonical_facts_tuple}
    known_observation_ids = {item.observation_id for item in snapshot.observations}
    for derived_request in derived_requests:
        for evidence in derived_request.input_evidence:
            if evidence.kind is EvidenceKind.CANONICAL_FACT:
                projected_version = projected_fact_versions.get(evidence.referenced_id)
                if projected_version is None or evidence.version != projected_version:
                    raise SealedEvidenceProvenanceError(
                        f"derived fact request {derived_request.feature_id!r} cites "
                        f"canonical fact {evidence.referenced_id!r} version "
                        f"{evidence.version!r}, which does not match this composition's "
                        "own just-projected canonical facts"
                    )
            elif evidence.kind is EvidenceKind.OBSERVATION:
                # Observations are unversioned, append-only records
                # (domain/references.py's own EvidenceReference contract);
                # a versioned OBSERVATION reference is itself malformed,
                # never merely an id lookup.
                unversioned = evidence.version is None
                if evidence.referenced_id not in known_observation_ids or not unversioned:
                    raise SealedEvidenceProvenanceError(
                        f"derived fact request {derived_request.feature_id!r} cites "
                        f"observation {evidence.referenced_id!r} (version="
                        f"{evidence.version!r}), which is either absent from the supplied "
                        "sealed snapshot or carries a version (observations are unversioned)"
                    )
            else:
                # Fail closed for any evidence kind this generic
                # composition path does not itself validate (currently
                # EvidenceKind.INDICATOR) -- an unrecognized kind must
                # never pass through unchecked.
                raise SealedEvidenceProvenanceError(
                    f"derived fact request {derived_request.feature_id!r} cites evidence "
                    f"kind {evidence.kind.value!r}, which this composition seam does not "
                    "validate and therefore does not accept"
                )

    derived_facts = tuple(
        materialize_derived_fact(
            DERIVED_FACT_REGISTRY,
            derived_request.feature_id,
            derived_request.subject,
            snapshot.snapshot_digest,
            value=derived_request.value,
            unit=derived_request.unit,
            effective_time=snapshot.as_of,
            input_evidence=derived_request.input_evidence,
            quality_status=derived_request.quality_status,
            parameters=derived_request.parameters,
        )
        for derived_request in derived_requests
    )
    derived_fact_set = DerivedFactSet(derived_facts)

    payload = mapping.build_payload(canonical_facts_tuple, derived_fact_set)
    return ReadOnlyStrategyInput(
        snapshot_id=snapshot.snapshot_id,
        snapshot_digest=snapshot.snapshot_digest,
        effective_time=snapshot.as_of,
        canonical_facts=canonical_facts_tuple,
        derived_facts=derived_fact_set,
        payload=payload,
    )
