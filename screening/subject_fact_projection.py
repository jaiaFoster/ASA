"""Generic sealed-snapshot canonical-fact projection mechanics
(SPRINT-014 S14-PR-05A, Architect checkpoint: sixth review -- "keep
snapshot -> fact/analytics mechanics generic ... a narrow generic
screening composition helper may import facts, but its architecture rule
should be narrow rather than expanding the entire package").

The one file in screening/ permitted to import facts/
(tests/architecture/test_screening_boundaries.py's own narrow, file-
scoped exception, not a package-wide allowance): resolution lookup needs
market_data (MarketSnapshot/ResolutionResult) and canonical fact
projection needs facts.canonical_projection.project_canonical_fact --
strategies/ can reach facts/ but not market_data/, so no strategy-owned
module can do this bridging itself.

No strategy identity, no manifest, no scoring, no richness normalization,
no context construction lives here -- those stay entirely strategy-owned
(e.g. strategies/earnings_calendar_evaluation.py). This module answers
three generic questions any sealed-snapshot consumer needs: "which
ResolutionResult resolved this capability", "project this scalar,
already extracted by the caller, into a CanonicalFact with a
subject/fact_type/snapshot-derived, strategy-independent identity", and
(added at the tenth-review checkpoint, restoring an invariant the
now-deleted screening/earnings_calendar_facts.py used to enforce as an
Earnings-named check) "does this already-resolved evidence bundle
genuinely belong to this sealed snapshot at all."
"""

from __future__ import annotations

from datetime import datetime

from domain import CanonicalFact, MarketCapability, ResolvedCapabilityEvidence
from facts.canonical_projection import canonical_fact_id, project_canonical_fact
from market_data.resolution import ResolutionResult
from market_data.snapshot import MarketSnapshot


class SealedEvidenceProvenanceError(ValueError):
    """Raised for a sealed-evidence internal-consistency violation -- most
    narrowly, when a ResolvedCapabilityEvidence bundle references at least
    one observation id absent from the sealed snapshot it is being composed
    against (SPRINT-014 S14-PR-05A, Architect checkpoint: tenth review, item
    4), but reused generically by every generic composition/preparation
    seam in this sprint (strategy_runtime/knowledge_composition.py,
    strategy_runtime/adapters/earnings_calendar_subject_first.py) for the
    whole family of "this composition already established some fact about
    the sealed evidence -- a claimed observation id, a resolved value's own
    domain type, a selection computed from this same evidence -- and the
    snapshot's own resolution now contradicts it" failures. A generic
    invariant/provenance failure -- never a typed UnknownReason -- because
    every one of these means the caller's own composition pipeline is
    internally inconsistent (composing mismatched snapshots, or evidence
    that violates an invariant the pipeline itself already relied on), not
    that a genuine, expected data gap exists.
    """


def verify_resolved_evidence_belongs_to_snapshot(
    snapshot: MarketSnapshot, evidence: ResolvedCapabilityEvidence
) -> None:
    """Verify every observation id ``evidence`` cites is actually present
    in ``snapshot``'s own observations. Generic across every capability
    and every consumer -- callers loop over whichever evidence fields
    their own typed bundle carries (e.g. a strategy's own PhaseTwoEvidence
    dataclass) and call this once per field, before doing anything with
    the evidence's own resolved value.
    """
    known_observation_ids = {item.observation_id for item in snapshot.observations}
    missing = set(evidence.observation_ids) - known_observation_ids
    if missing:
        raise SealedEvidenceProvenanceError(
            f"resolved evidence for demand {evidence.demand_id!r} references "
            f"observation id(s) {sorted(missing)} absent from the supplied sealed snapshot"
        )


def resolution_for(snapshot: MarketSnapshot, capability: MarketCapability) -> ResolutionResult:
    """The one ResolutionResult a sealed snapshot carries for
    ``capability``. Raises ValueError if the snapshot never requested
    that capability at all -- a genuine caller-side configuration defect,
    never a data gap a typed UNKNOWN represents.
    """
    for item in snapshot.resolution_results:
        if item.capability is capability:
            return item
    raise ValueError(f"snapshot has no resolution for {capability.value}")


def project_scalar_canonical_fact(
    resolution: ResolutionResult,
    *,
    value: object,
    subject: str,
    fact_type: str,
    snapshot_digest: str,
    effective_time: datetime,
    version: int = 1,
) -> CanonicalFact | None:
    """Project one already-extracted scalar ``value`` into a CanonicalFact
    grounded in ``resolution``'s own provenance, with a strategy-
    independent identity (Architect checkpoint item 2): two different
    consumers projecting the same ``fact_type`` for the same ``subject``
    from the same ``snapshot_digest`` always receive the same fact_id,
    computed by canonical_fact_id() -- never a strategy-scoped prefix.
    Returns None when the resolution is UNRESOLVED, matching
    project_canonical_fact's own explicit-UNKNOWN contract.
    """
    return project_canonical_fact(
        resolution,
        value=value,
        fact_id=canonical_fact_id(fact_type, subject, snapshot_digest),
        version=version,
        fact_type=fact_type,
        created_time=effective_time,
    )
