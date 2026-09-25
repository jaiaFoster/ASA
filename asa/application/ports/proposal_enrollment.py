"""Port for system proposal enrollments and their forward outcomes (ND-01)."""

from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

from asa.contracts.forward_outcome import ForwardOutcomeObservation
from asa.contracts.proposal_enrollment import ProposalEnrollment


class ProposalEnrollmentRepository(Protocol):
    def add(self, enrollment: ProposalEnrollment, maximum_per_session: int) -> str:
        """Insert-only, atomically enforcing the per-session cap.

        Returns ``enrolled``, or, changing nothing, ``already_enrolled`` (the
        proposal or its (signal, version, symbol, session) slot exists) or
        ``enrollment_deferred_by_cap``.
        """

    def count_for_session(self, session_date: date) -> int: ...

    def slot_taken(
        self, signal_id: str, signal_version: str, symbol: str, session_date: date
    ) -> bool: ...

    def enrollments(self) -> tuple[ProposalEnrollment, ...]: ...

    def enrollment(self, enrollment_id: UUID) -> ProposalEnrollment | None: ...

    def append_outcome(self, observation: ForwardOutcomeObservation) -> ForwardOutcomeObservation:
        """Append-only; identical content is idempotent, a different one raises."""

    def outcomes_for(self, enrollment_id: UUID) -> tuple[ForwardOutcomeObservation, ...]: ...
