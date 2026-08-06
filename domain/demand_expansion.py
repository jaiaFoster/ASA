"""Generic, provider-blind expansion result contract (SPRINT-014
S14-PR-05A, Architect checkpoint: "the strategy return contract must not
require a strategies -> screening dependency").

A pure strategy expansion function (strategies/) must be able to
construct and return this type without importing screening/ or
market_data/ -- strategies/'s own architecture boundary already forbids
both. Living in domain/ alongside CapabilityDemand (domain/
capability_demand.py) means the generic subject planner
(screening/subject_planning.py) can consume it structurally, with no
strategy-named wrapper module standing between a strategy's own pure
function and the planner.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.capability_demand import CapabilityDemand
from domain.values import DomainInvariantError


@dataclass(frozen=True, slots=True)
class UnknownReason:
    """A structured, typed reason a pure expansion function could not
    proceed -- never a free-form string. ``code`` is a stable,
    machine-comparable identifier (e.g. "missing_earnings_date",
    "no_valid_expiration_pair"); ``demand_ids`` names which resolved
    demands (if any) the decision depended on, so the reason stays
    traceable back to specific evidence without carrying the evidence
    itself.
    """

    code: str
    demand_ids: tuple[str, ...] = ()
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.code or self.code != self.code.strip():
            raise DomainInvariantError("UnknownReason.code must be normalized")
        object.__setattr__(self, "demand_ids", tuple(sorted(set(self.demand_ids))))


@dataclass(frozen=True, slots=True)
class DemandExpansion:
    """One consumer's own pure phase-two output.

    ``selections`` is a frozen, canonical mapping-of-pairs (domain/
    canonicalization.py's own established immutable-mapping convention --
    a tuple of unique, sorted ``(key, value)`` pairs, never a mutable
    dict) carrying whatever pure selection output a strategy's own policy
    produced (e.g. a chosen expiration pair's identities); opaque to the
    generic planner, which only ever carries it through unread.

    ``demands`` is deduplicated by ``CapabilityDemand.demand_id`` and
    returned in deterministic (demand_id-sorted) order regardless of the
    order a consumer's own expansion function happened to construct them
    in -- a generic planner's own union step must never depend on a
    strategy's own internal ordering.
    """

    demands: tuple[CapabilityDemand, ...] = ()
    selections: tuple[tuple[str, object], ...] = ()
    unknown_reasons: tuple[UnknownReason, ...] = ()

    def __post_init__(self) -> None:
        demand_ids = [item.demand_id for item in self.demands]
        if len(demand_ids) != len(set(demand_ids)):
            raise DomainInvariantError(
                "DemandExpansion.demands contains two demands with the same demand_id"
            )
        object.__setattr__(
            self, "demands", tuple(sorted(self.demands, key=lambda item: item.demand_id))
        )
        selection_keys = [key for key, _ in self.selections]
        if len(selection_keys) != len(set(selection_keys)):
            raise DomainInvariantError("DemandExpansion.selections keys must be unique")
        if any(not key or key != key.strip() for key in selection_keys):
            raise DomainInvariantError("DemandExpansion.selections keys must be normalized")
        object.__setattr__(
            self, "selections", tuple(sorted(self.selections, key=lambda item: item[0]))
        )
