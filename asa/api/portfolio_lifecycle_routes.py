from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from asa.application.portfolio_lifecycle import CandidateNotFoundError, TrackCandidateService
from asa.application.portfolio_valuation import project_exit_state
from asa.application.ports.portfolio_lifecycle import PortfolioLifecycleRepository
from asa.contracts.portfolio_lifecycle import (
    PositionAssociation,
    PositionLifecycleObservation,
    TrackedCandidate,
)


class TrackCandidateRequest(BaseModel):
    strategy_id: str = Field(min_length=1, max_length=64)
    symbol: str = Field(min_length=1, max_length=32)
    observation_id: str = Field(min_length=1, max_length=128)


class TrackedCandidateResponse(BaseModel):
    id: UUID
    originating_observation_id: str
    opportunity_id: str | None
    strategy_id: str
    strategy_version: str
    symbol: str
    tracked_at: datetime
    originating_observed_at: datetime
    evidence_observed_at: datetime
    exact_option_symbols: list[str]

    @classmethod
    def from_domain(cls, candidate: TrackedCandidate) -> "TrackedCandidateResponse":
        return cls(
            id=candidate.id,
            originating_observation_id=candidate.originating_observation_id,
            opportunity_id=candidate.opportunity_id,
            strategy_id=candidate.strategy_id,
            strategy_version=candidate.strategy_version,
            symbol=candidate.symbol,
            tracked_at=candidate.tracked_at,
            originating_observed_at=candidate.originating_observed_at,
            evidence_observed_at=candidate.evidence_observed_at,
            exact_option_symbols=list(candidate.exact_option_symbols),
        )


class LifecycleObservationResponse(BaseModel):
    state: str
    broker_position_key: str | None
    broker_observed_at: datetime
    strategy_result_observed_at: datetime
    evidence_observed_at: datetime

    @classmethod
    def from_domain(cls, item: PositionLifecycleObservation) -> "LifecycleObservationResponse":
        return cls(
            state=item.state.value,
            broker_position_key=item.broker_position_key,
            broker_observed_at=item.broker_observed_at,
            strategy_result_observed_at=item.strategy_result_observed_at,
            evidence_observed_at=item.evidence_observed_at,
        )


class AssociationResponse(BaseModel):
    broker_position_key: str
    state: str
    observed_at: datetime
    associated: bool

    @classmethod
    def from_domain(cls, item: PositionAssociation) -> "AssociationResponse":
        return cls(
            broker_position_key=item.broker_position_key,
            state=item.state.value,
            observed_at=item.observed_at,
            associated=item.is_associated,
        )


class TrackedCandidateDetailResponse(BaseModel):
    candidate: TrackedCandidateResponse
    lifecycle: list[LifecycleObservationResponse]
    associations: list[AssociationResponse]
    exit_policy_status: str


def build_portfolio_lifecycle_router(
    service: TrackCandidateService,
    repository: PortfolioLifecycleRepository,
    authorize: Callable[[Request], None],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(authorize)])

    @router.post(
        "/portfolio/tracked-candidates",
        response_model=TrackedCandidateResponse,
        operation_id="trackCandidate",
    )
    def track_candidate(payload: TrackCandidateRequest) -> TrackedCandidateResponse:
        try:
            candidate = service.track(
                payload.strategy_id,
                payload.symbol,
                payload.observation_id,
                datetime.now(UTC),
            )
        except CandidateNotFoundError:
            raise HTTPException(
                status_code=404,
                detail="originating screening observation is unavailable",
            ) from None
        return TrackedCandidateResponse.from_domain(candidate)

    @router.get(
        "/portfolio/tracked-candidates",
        response_model=list[TrackedCandidateResponse],
        operation_id="getTrackedCandidates",
    )
    def tracked_candidates() -> list[TrackedCandidateResponse]:
        return [TrackedCandidateResponse.from_domain(item) for item in repository.candidates()]

    @router.get(
        "/portfolio/tracked-candidates/{candidate_id}",
        response_model=TrackedCandidateDetailResponse,
        operation_id="getTrackedCandidate",
    )
    def tracked_candidate(candidate_id: UUID) -> TrackedCandidateDetailResponse:
        candidate = repository.candidate(candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="tracked candidate unavailable")
        exit_state = project_exit_state(evaluated_at=datetime.now(UTC), declared=None)
        return TrackedCandidateDetailResponse(
            candidate=TrackedCandidateResponse.from_domain(candidate),
            lifecycle=[
                LifecycleObservationResponse.from_domain(item)
                for item in repository.lifecycle_observations(candidate_id)
            ],
            associations=[
                AssociationResponse.from_domain(item)
                for item in repository.associations(candidate_id)
            ],
            exit_policy_status=exit_state.status.value,
        )

    return router
