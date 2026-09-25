"""Enroll system-actionable option proposals into forward outcomes (ND-01).

Binding Architect decision:
``project/reports/OUTCOME-INTELLIGENCE-001-ND-01-ARCHITECT-DECISION.md``.

- Input is only this tick's authoritative latest row and the readiness
  artifact projected from exactly that row. A stale artifact is never
  enrolled.
- Only a canonical ``OptionTradeProposal`` is enrolled, meaning one that is
  constructible as intended. Stock and unavailable proposals are skipped.
- Sampling ``oi-enroll-v1``:
  - the first proposal per (signal, version, symbol, New York session) wins;
  - at most ``MAXIMUM_ENROLLMENTS_PER_SESSION`` enrollments per session,
    taken in deterministic (signal, symbol) order;
  - nothing is backfilled.
- Freezing goes through ``freeze_proposal``, the same path user tracking
  uses. There is no strategy-ID branch.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from asa.application.ports.portfolio_lifecycle import PortfolioLifecycleRepository
from asa.application.ports.proposal_enrollment import ProposalEnrollmentRepository
from asa.application.proposal_freezing import freeze_proposal
from asa.contracts.proposal_enrollment import (
    ENROLLMENT_POLICY_VERSION,
    ProposalEnrollment,
    enrollment_id,
)
from market_data.session_calendar import NEW_YORK
from strategy_runtime.persistence import LatestResultRepository

MAXIMUM_ENROLLMENTS_PER_SESSION = 8


@dataclass(frozen=True, slots=True)
class EnrollmentSummary:
    enrolled: int = 0
    already_enrolled: int = 0
    not_actionable: int = 0
    stale_or_missing_artifact: int = 0
    enrollment_deferred_by_cap: int = 0


class ProposalEnrollmentService:
    def __init__(
        self,
        results: LatestResultRepository,
        lifecycle: PortfolioLifecycleRepository,
        enrollments: ProposalEnrollmentRepository,
        *,
        maximum_per_session: int = MAXIMUM_ENROLLMENTS_PER_SESSION,
    ) -> None:
        self._results = results
        self._lifecycle = lifecycle
        self._enrollments = enrollments
        self._maximum_per_session = maximum_per_session

    def enroll(self, pairs: Iterable[tuple[str, str]], now: datetime) -> EnrollmentSummary:
        counts = dict.fromkeys(EnrollmentSummary.__dataclass_fields__, 0)
        for signal_id, symbol in sorted(set(pairs)):
            row = self._results.get_one(signal_id, symbol)
            if row is None:
                counts["stale_or_missing_artifact"] += 1
                continue
            frozen = freeze_proposal(row, self._lifecycle.execution_readiness(signal_id, symbol))
            if frozen is None:
                counts["stale_or_missing_artifact"] += 1
                continue
            if not frozen.is_canonical_trade_proposal:
                counts["not_actionable"] += 1
                continue
            evidence_observed_at = (
                row.temporal.observed_at if row.temporal is not None else row.observed_at
            ).astimezone(UTC)
            session_date = evidence_observed_at.astimezone(NEW_YORK).date()
            if self._enrollments.slot_taken(
                row.signal_id, row.signal_version, row.symbol, session_date
            ):
                counts["already_enrolled"] += 1
                continue
            if self._enrollments.count_for_session(session_date) >= self._maximum_per_session:
                counts["enrollment_deferred_by_cap"] += 1
                continue
            added = self._enrollments.add(
                ProposalEnrollment(
                    id=enrollment_id(frozen.identity),
                    enrollment_policy_version=ENROLLMENT_POLICY_VERSION,
                    originating_observation_id=row.observation_id,
                    opportunity_id=row.opportunity_id,
                    signal_id=row.signal_id,
                    signal_version=row.signal_version,
                    symbol=row.symbol,
                    session_date=session_date,
                    evidence_observed_at=evidence_observed_at,
                    enrolled_at=now.astimezone(UTC),
                    resolved_proposal_identity=frozen.identity,
                    resolved_proposal_json=frozen.canonical_json,
                )
            )
            counts["enrolled" if added else "already_enrolled"] += 1
        return EnrollmentSummary(**counts)
