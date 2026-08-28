from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from asa.application.portfolio_lifecycle import CandidateNotFoundError, TrackCandidateService
from asa.contracts.portfolio_lifecycle import TrackedCandidate


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


def build_portfolio_lifecycle_router(
    service: TrackCandidateService,
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

    return router
