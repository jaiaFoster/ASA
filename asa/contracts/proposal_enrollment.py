"""System enrollment of actionable proposals into forward outcomes (ND-01).

A ``system_actionable`` enrollment is structurally separate from a user's
``TrackedCandidate``. It never appears in portfolio or tracking surfaces and
is never reconciled against broker positions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

ENROLLMENT_POLICY_VERSION = "oi-enroll-v1"
USER_TRACKED = "user_tracked"
SYSTEM_ACTIONABLE = "system_actionable"


def enrollment_id(resolved_proposal_identity: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"asa:enrolled:{resolved_proposal_identity}")


@dataclass(frozen=True, slots=True)
class ProposalEnrollment:
    id: UUID
    enrollment_policy_version: str
    originating_observation_id: str
    opportunity_id: str | None
    signal_id: str
    signal_version: str
    symbol: str
    session_date: date
    evidence_observed_at: datetime
    enrolled_at: datetime
    resolved_proposal_identity: str
    resolved_proposal_json: str

    def __post_init__(self) -> None:
        if self.id != enrollment_id(self.resolved_proposal_identity):
            raise ValueError("enrollment id must derive from the frozen proposal identity")
        if self.enrolled_at < self.evidence_observed_at:
            raise ValueError("enrollment cannot precede its evidence")
