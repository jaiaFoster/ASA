"""Forward-outcome collection use case (OUTCOME-INTELLIGENCE OI-03).

Walks tracked candidates, computes each frozen proposal's generic horizon
schedule, and appends at most one immutable outcome per (candidate, horizon).
Invariants (Architect decision, binding):

- the entry reference is only the frozen ``resolved_proposal_json``; latest
  screening state and execution readiness are never read;
- eligibility is judged by provider evidence time inside the versioned
  window around the due close -- never wall clock -- and every evidence
  timestamp used must fall inside it;
- the first eligible observation is final; a passed window is recorded as
  ``missed``; a horizon due before tracking is
  ``not_observable_before_tracking``; nothing is backfilled.

Acquisition goes only through ``OutcomeEvidenceSource`` (the shared
market-data authority in production). No broker call exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from asa.application.ports.forward_outcomes import (
    ForwardOutcomeRepository,
    OutcomeEvidence,
    OutcomeEvidenceSource,
)
from asa.application.ports.portfolio_lifecycle import PortfolioLifecycleRepository
from asa.contracts.forward_outcome import ForwardOutcomeObservation
from asa.contracts.portfolio_lifecycle import TrackedCandidate
from strategy_runtime.forward_outcome import (
    HORIZON_POLICY_VERSION,
    FrozenStructure,
    HorizonDue,
    OutcomeStatus,
    evidence_in_window,
    horizon_schedule,
    modeled_mark,
    outcome_content_identity,
    parse_frozen_structure,
    window_has_passed,
)

DEFAULT_MAXIMUM_SUBJECTS_PER_TICK = 10


@dataclass(frozen=True, slots=True)
class CollectionSummary:
    observed: int = 0
    missed: int = 0
    not_observable: int = 0
    pending: int = 0
    evidence_outside_window: int = 0
    deferred_by_subject_cap: int = 0


def _record(
    candidate: TrackedCandidate,
    due: HorizonDue,
    status: OutcomeStatus,
    now: datetime,
    structure: FrozenStructure | None,
    *,
    observed_at: datetime | None = None,
    underlying_price: Decimal | None = None,
    mark_value: Decimal | None = None,
    pnl: Decimal | None = None,
    basis: str | None = None,
    model_version: str | None = None,
    unknown_reasons: tuple[str, ...] = (),
    provenance: tuple[str, ...] = (),
) -> ForwardOutcomeObservation:
    payload = {
        "candidate": str(candidate.id),
        "horizon": due.horizon_id,
        "status": status.value,
        "due_at": due.due_at.isoformat(),
        "policy": HORIZON_POLICY_VERSION,
        "proposal": None if structure is None else structure.proposal_identity,
        "observed_at": None if observed_at is None else observed_at.isoformat(),
        "underlying_price": underlying_price,
        "mark": mark_value,
        "pnl": pnl,
        "basis": basis,
        "model": model_version,
        "unknown": list(unknown_reasons),
        "provenance": list(provenance),
    }
    return ForwardOutcomeObservation(
        tracked_candidate_id=candidate.id,
        horizon_id=due.horizon_id,
        status=status,
        due_at=due.due_at,
        collected_at=now,
        horizon_policy_version=HORIZON_POLICY_VERSION,
        frozen_proposal_identity=None if structure is None else structure.proposal_identity,
        observed_at=observed_at,
        underlying_price=underlying_price,
        modeled_mark=mark_value,
        modeled_pnl=pnl,
        mark_basis=basis,
        mark_model_version=model_version,
        unknown_reasons=unknown_reasons,
        provenance=provenance,
        content_identity=outcome_content_identity(payload),
    )


def _evidence_times(
    evidence: OutcomeEvidence, structure: FrozenStructure | None
) -> tuple[datetime | None, ...]:
    if structure is None:
        return (evidence.underlying_observed_at,)
    return (evidence.underlying_observed_at, evidence.chain_observed_at)


class ForwardOutcomeCollector:
    def __init__(
        self,
        lifecycle: PortfolioLifecycleRepository,
        outcomes: ForwardOutcomeRepository,
        evidence: OutcomeEvidenceSource,
        *,
        maximum_subjects_per_tick: int = DEFAULT_MAXIMUM_SUBJECTS_PER_TICK,
    ) -> None:
        self._lifecycle = lifecycle
        self._outcomes = outcomes
        self._evidence = evidence
        self._maximum_subjects = maximum_subjects_per_tick

    def collect(self, now: datetime) -> CollectionSummary:
        counts = {
            "observed": 0,
            "missed": 0,
            "not_observable": 0,
            "pending": 0,
            "evidence_outside_window": 0,
            "deferred_by_subject_cap": 0,
        }
        # Keyed by (symbol, frozen expirations): evidence fetched for one
        # subject's expirations never stands in for another's legs.
        evidence_by_subject: dict[tuple[str, tuple[date, ...]], OutcomeEvidence] = {}
        for candidate in sorted(self._lifecycle.candidates(), key=lambda item: str(item.id)):
            structure = parse_frozen_structure(
                candidate.resolved_proposal_identity, candidate.resolved_proposal_json
            )
            recorded = {item.horizon_id for item in self._outcomes.for_candidate(candidate.id)}
            for due in horizon_schedule(candidate.evidence_observed_at, structure):
                if due.horizon_id in recorded:
                    continue
                self._collect_one(candidate, structure, due, now, evidence_by_subject, counts)
        return CollectionSummary(**counts)

    def _collect_one(
        self,
        candidate: TrackedCandidate,
        structure: FrozenStructure | None,
        due: HorizonDue,
        now: datetime,
        evidence_by_subject: dict[tuple[str, tuple[date, ...]], OutcomeEvidence],
        counts: dict[str, int],
    ) -> None:
        if due.due_at < candidate.tracked_at:
            self._outcomes.append(
                _record(
                    candidate, due, OutcomeStatus.NOT_OBSERVABLE_BEFORE_TRACKING, now, structure
                )
            )
            counts["not_observable"] += 1
            return
        if window_has_passed(due.due_at, now):
            self._outcomes.append(_record(candidate, due, OutcomeStatus.MISSED, now, structure))
            counts["missed"] += 1
            return
        if not evidence_in_window(due.due_at, now):
            counts["pending"] += 1
            return
        expirations = tuple(
            sorted(set() if structure is None else {leg.expiration for leg in structure.legs})
        )
        key = (candidate.symbol, expirations)
        evidence = evidence_by_subject.get(key)
        if evidence is None:
            if len(evidence_by_subject) >= self._maximum_subjects:
                counts["deferred_by_subject_cap"] += 1
                return
            evidence = self._evidence.collect(candidate.symbol, expirations, now)
            evidence_by_subject[key] = evidence
        times = _evidence_times(evidence, structure)
        if any(item is None or not evidence_in_window(due.due_at, item) for item in times):
            # Retried on a later tick while the window is open; never backfilled.
            counts["evidence_outside_window"] += 1
            return
        mark = modeled_mark(
            structure,
            evidence.leg_quotes,
            horizon_id=due.horizon_id,
            underlying_price=evidence.underlying_price,
        )
        self._outcomes.append(
            _record(
                candidate,
                due,
                OutcomeStatus.OBSERVED,
                now,
                structure,
                observed_at=max(item for item in times if item is not None),
                underlying_price=evidence.underlying_price,
                mark_value=mark.mark_value,
                pnl=mark.modeled_pnl,
                basis=mark.basis,
                model_version=mark.model_version,
                unknown_reasons=(*evidence.unknown_reasons, *mark.unknown_reasons),
                provenance=evidence.provenance,
            )
        )
        counts["observed"] += 1
