from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ReconciliationState(StrEnum):
    TRACKED = "tracked"
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    NO_MATCH = "no_match"


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
    exact_option_symbols: tuple[str, ...]


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
