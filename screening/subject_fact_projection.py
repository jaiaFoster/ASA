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
(e.g. strategies/earnings_calendar_evaluation.py). This module only
answers two generic questions any sealed-snapshot consumer needs: "which
ResolutionResult resolved this capability" and "project this scalar,
already extracted by the caller, into a CanonicalFact with a
subject/fact_type/snapshot-derived, strategy-independent identity."
"""

from __future__ import annotations

from datetime import datetime

from domain import CanonicalFact, MarketCapability
from facts.canonical_projection import canonical_fact_id, project_canonical_fact
from market_data.resolution import ResolutionResult
from market_data.snapshot import MarketSnapshot


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
