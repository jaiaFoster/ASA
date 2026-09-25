"""Enroll system-actionable option proposals into forward outcomes (ND-01).

Binding Architect decision:
``project/reports/OUTCOME-INTELLIGENCE-001-ND-01-ARCHITECT-DECISION.md``.

- Input is only this tick's own result: the authoritative latest row must
  be the exact observation this tick produced and must still be ``pass``,
  and the readiness artifact must be projected from exactly that row. Stale
  rows or artifacts are never enrolled.
- Each pair is isolated: one failing pair is counted and logged, and never
  aborts the rest of the tick.
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

import logging
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
_PASS = "pass"
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EnrollmentSummary:
    enrolled: int = 0
    already_enrolled: int = 0
    not_actionable: int = 0
    stale_or_missing_artifact: int = 0
    enrollment_deferred_by_cap: int = 0
    evidence_after_clock: int = 0
    enrollment_failed: int = 0


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

    def enroll(self, pairs: Iterable[tuple[str, str, str]], now: datetime) -> EnrollmentSummary:
        """``pairs`` are (signal_id, symbol, observation_id) produced this tick."""
        counts = dict.fromkeys(EnrollmentSummary.__dataclass_fields__, 0)
        for signal_id, symbol, observation_id in sorted(set(pairs)):
            try:
                counts[self._enroll_one(signal_id, symbol, observation_id, now)] += 1
            except Exception:
                counts["enrollment_failed"] += 1
                _LOGGER.warning(
                    "proposal_enrollment_pair_failed",
                    extra={"signal_id": signal_id, "symbol": symbol},
                    exc_info=True,
                )
        return EnrollmentSummary(**counts)

    def _enroll_one(self, signal_id: str, symbol: str, observation_id: str, now: datetime) -> str:
        row = self._results.get_one(signal_id, symbol)
        if (
            row is None
            or row.observation_id != observation_id
            or str(row.evaluation_state).lower() != _PASS
        ):
            return "stale_or_missing_artifact"
        frozen = freeze_proposal(row, self._lifecycle.execution_readiness(signal_id, symbol))
        if frozen is None:
            return "stale_or_missing_artifact"
        if not frozen.is_canonical_trade_proposal:
            return "not_actionable"
        evidence_observed_at = (
            row.temporal.observed_at if row.temporal is not None else row.observed_at
        ).astimezone(UTC)
        enrolled_at = now.astimezone(UTC)
        if evidence_observed_at > enrolled_at:
            return "evidence_after_clock"
        session_date = evidence_observed_at.astimezone(NEW_YORK).date()
        if self._enrollments.slot_taken(
            row.signal_id, row.signal_version, row.symbol, session_date
        ):
            return "already_enrolled"
        return self._enrollments.add(
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
                enrolled_at=enrolled_at,
                resolved_proposal_identity=frozen.identity,
                resolved_proposal_json=frozen.canonical_json,
            ),
            self._maximum_per_session,
        )
