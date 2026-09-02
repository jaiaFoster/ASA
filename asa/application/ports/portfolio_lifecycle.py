from typing import Protocol
from uuid import UUID

from asa.contracts.portfolio_lifecycle import (
    ExecutionReadinessArtifact,
    PositionAssociation,
    PositionLifecycleObservation,
    TrackedCandidate,
)


class PortfolioLifecycleRepository(Protocol):
    def put_execution_readiness(self, artifact: ExecutionReadinessArtifact) -> None: ...

    def execution_readiness(
        self, strategy_id: str, symbol: str
    ) -> ExecutionReadinessArtifact | None: ...

    def add_candidate(self, candidate: TrackedCandidate) -> TrackedCandidate: ...

    def candidates(self) -> tuple[TrackedCandidate, ...]: ...

    def candidate(self, candidate_id: UUID) -> TrackedCandidate | None: ...

    def append_association(self, association: PositionAssociation) -> None: ...

    def append_lifecycle_observation(self, observation: PositionLifecycleObservation) -> None: ...

    def lifecycle_observations(
        self, candidate_id: UUID
    ) -> tuple[PositionLifecycleObservation, ...]: ...

    def associations(self, candidate_id: UUID) -> tuple[PositionAssociation, ...]: ...
