"""Read-only sealed evidence bundle for subject-first strategies
(SPRINT-014 S14-PR-05).

The one thing a migrated strategy's RuntimeContext may carry instead of a
live CapabilityFulfillmentService (I-09: strategy-facing code receives no
provider, transport, budget, or fulfillment object). SubjectSealedEvidence
bundles three already-owned, already-frozen types -- it does not define or
duplicate any of them: MarketSnapshot (market_data/snapshot.py) is sealed
before this ticket ever runs; canonical_facts (domain.canonical_fact.
CanonicalFact, projected via facts/canonical_projection.py) and
derived_facts (analytics.features.DerivedFactSet, materialized via
analytics/derived_fact_materialization.py) are read-only projections over
that same sealed snapshot. A strategy consuming this bundle can acquire
nothing further -- there is no provider, transport, or budget object
anywhere in this type for it to reach through.
"""

from __future__ import annotations

from dataclasses import dataclass

from analytics.features import DerivedFactSet
from domain.canonical_fact import CanonicalFact
from market_data.snapshot import MarketSnapshot


@dataclass(frozen=True, slots=True)
class SubjectSealedEvidence:
    snapshot: MarketSnapshot
    canonical_facts: tuple[CanonicalFact, ...]
    derived_facts: DerivedFactSet

    def __post_init__(self) -> None:
        fact_ids = tuple(item.fact_id for item in self.canonical_facts)
        if len(set(fact_ids)) != len(fact_ids):
            raise ValueError("SubjectSealedEvidence.canonical_facts fact_ids must be unique")
        ordered = tuple(sorted(self.canonical_facts, key=lambda item: item.fact_id))
        object.__setattr__(self, "canonical_facts", ordered)

    def canonical_fact(self, fact_id: str) -> CanonicalFact | None:
        for fact in self.canonical_facts:
            if fact.fact_id == fact_id:
                return fact
        return None
