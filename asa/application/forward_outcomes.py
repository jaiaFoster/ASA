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

ND-01: subjects come from two structurally separate sources. They are
``user_tracked`` candidates and, when an enrollment repository is wired,
``system_actionable`` enrollments. User subjects are served first. The
per-tick subject cap is shared, and deferrals are reported per source.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from functools import partial
from uuid import UUID

from asa.application.ports.forward_outcomes import (
    ForwardOutcomeRepository,
    OutcomeEvidence,
    OutcomeEvidenceSource,
)
from asa.application.ports.portfolio_lifecycle import PortfolioLifecycleRepository
from asa.application.ports.proposal_enrollment import ProposalEnrollmentRepository
from asa.contracts.forward_outcome import ForwardOutcomeObservation
from asa.contracts.proposal_enrollment import SYSTEM_ACTIONABLE, USER_TRACKED
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
    deferred_by_source: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OutcomeSubject:
    """One frozen proposal to observe, from either enrollment source."""

    source: str
    key: UUID
    symbol: str
    anchor: datetime
    start_at: datetime
    proposal_identity: str | None
    proposal_json: str | None
    recorded: Callable[[], set[str]]
    append: Callable[[ForwardOutcomeObservation], ForwardOutcomeObservation]


def _record(
    candidate: OutcomeSubject,
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
        "candidate": str(candidate.key),
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
        subject_id=candidate.key,
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


def _recorded(read: Callable[[UUID], tuple[ForwardOutcomeObservation, ...]], key: UUID) -> set[str]:
    return {row.horizon_id for row in read(key)}


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
        enrollments: ProposalEnrollmentRepository | None = None,
        maximum_subjects_per_tick: int = DEFAULT_MAXIMUM_SUBJECTS_PER_TICK,
    ) -> None:
        self._lifecycle = lifecycle
        self._outcomes = outcomes
        self._enrollments = enrollments
        self._evidence = evidence
        self._maximum_subjects = maximum_subjects_per_tick

    def _subjects(self) -> list[OutcomeSubject]:
        outcomes = self._outcomes
        subjects = [
            OutcomeSubject(
                USER_TRACKED,
                item.id,
                item.symbol,
                item.evidence_observed_at,
                item.tracked_at,
                item.resolved_proposal_identity,
                item.resolved_proposal_json,
                partial(_recorded, outcomes.for_candidate, item.id),
                outcomes.append,
            )
            for item in sorted(self._lifecycle.candidates(), key=lambda item: str(item.id))
        ]
        enrollments = self._enrollments
        if enrollments is not None:
            subjects.extend(
                OutcomeSubject(
                    SYSTEM_ACTIONABLE,
                    item.id,
                    item.symbol,
                    item.evidence_observed_at,
                    item.enrolled_at,
                    item.resolved_proposal_identity,
                    item.resolved_proposal_json,
                    partial(_recorded, enrollments.outcomes_for, item.id),
                    enrollments.append_outcome,
                )
                for item in sorted(enrollments.enrollments(), key=lambda item: str(item.id))
            )
        return subjects

    def collect(self, now: datetime) -> CollectionSummary:
        counts = {
            "observed": 0,
            "missed": 0,
            "not_observable": 0,
            "pending": 0,
            "evidence_outside_window": 0,
            "deferred_by_subject_cap": 0,
        }
        deferred: dict[str, int] = {}
        # Keyed by (symbol, frozen expirations): evidence fetched for one
        # subject's expirations never stands in for another's legs.
        evidence_by_subject: dict[tuple[str, tuple[date, ...]], OutcomeEvidence] = {}
        for subject in self._subjects():
            structure = parse_frozen_structure(subject.proposal_identity, subject.proposal_json)
            recorded = subject.recorded()
            for due in horizon_schedule(subject.anchor, structure):
                if due.horizon_id in recorded:
                    continue
                before = counts["deferred_by_subject_cap"]
                self._collect_one(subject, structure, due, now, evidence_by_subject, counts)
                if counts["deferred_by_subject_cap"] > before:
                    deferred[subject.source] = deferred.get(subject.source, 0) + 1
        return CollectionSummary(**counts, deferred_by_source=dict(sorted(deferred.items())))

    def _collect_one(
        self,
        candidate: OutcomeSubject,
        structure: FrozenStructure | None,
        due: HorizonDue,
        now: datetime,
        evidence_by_subject: dict[tuple[str, tuple[date, ...]], OutcomeEvidence],
        counts: dict[str, int],
    ) -> None:
        if due.due_at < candidate.start_at:
            candidate.append(
                _record(
                    candidate, due, OutcomeStatus.NOT_OBSERVABLE_BEFORE_TRACKING, now, structure
                )
            )
            counts["not_observable"] += 1
            return
        if window_has_passed(due.due_at, now):
            candidate.append(_record(candidate, due, OutcomeStatus.MISSED, now, structure))
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
        candidate.append(
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
