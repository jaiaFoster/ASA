from typing import Protocol
from uuid import UUID

from asa.contracts.portfolio_lifecycle import PositionAssociation, TrackedCandidate


class PortfolioLifecycleRepository(Protocol):
    def add_candidate(self, candidate: TrackedCandidate) -> TrackedCandidate: ...

    def candidates(self) -> tuple[TrackedCandidate, ...]: ...

    def candidate(self, candidate_id: UUID) -> TrackedCandidate | None: ...

    def append_association(self, association: PositionAssociation) -> None: ...

