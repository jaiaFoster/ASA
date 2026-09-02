from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ReconciliationState(StrEnum):
    TRACKED = "tracked"
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    NO_MATCH = "no_match"


class PositionLifecycleState(StrEnum):
    TRACKED = "tracked"
    OPEN = "open"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class TrackedCandidate:
    id: UUID
    originating_observation_id: str
    opportunity_id: str | None
    strategy_id: str
    strategy_version: str
    symbol: str
    tracked_at: datetime
    originating_observed_at: datetime
    evidence_observed_at: datetime
    exact_option_symbols: tuple[str, ...]
    resolved_proposal_identity: str | None = None
    resolved_proposal_json: str | None = None

    def __post_init__(self) -> None:
        if (self.resolved_proposal_identity is None) != (
            self.resolved_proposal_json is None
        ):
            raise ValueError("resolved proposal identity and payload must appear together")


@dataclass(frozen=True, slots=True)
class ExecutionReadinessArtifact:
    """Immutable API-ready proposal captured downstream of one result."""

    originating_observation_id: str
    strategy_id: str
    symbol: str
    assessment_identity: str
    canonical_json: str
    assessment_json: str
    assessed_at: datetime


@dataclass(frozen=True, slots=True)
class PositionAssociation:
    tracked_candidate_id: UUID
    broker_position_key: str
    state: ReconciliationState
    observed_at: datetime

    @property
    def is_associated(self) -> bool:
        """Only a unique match confers provenance; ambiguity is evidence, not association."""
        return self.state is ReconciliationState.MATCHED


@dataclass(frozen=True, slots=True)
class PositionLifecycleObservation:
    tracked_candidate_id: UUID
    state: PositionLifecycleState
    broker_position_key: str | None
    broker_observed_at: datetime
    strategy_result_observed_at: datetime
    evidence_observed_at: datetime
