import json
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from asa.application.portfolio_lifecycle import (
    CandidateNotFoundError,
    ProposalIdentityCollisionError,
    TrackCandidateService,
)
from asa.application.portfolio_valuation import project_exit_state
from asa.application.ports.forward_outcomes import ForwardOutcomeRepository
from asa.application.ports.portfolio_lifecycle import PortfolioLifecycleRepository
from asa.contracts.forward_outcome import ForwardOutcomeObservation
from asa.contracts.portfolio_lifecycle import (
    PositionAssociation,
    PositionLifecycleObservation,
    TrackedCandidate,
)
from strategy_runtime.forward_outcome import (
    HORIZON_POLICY_VERSION,
    FrozenStructure,
    horizon_schedule,
    parse_frozen_structure,
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
    resolved_proposal_identity: str | None
    resolved_proposal: dict[str, object] | None

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
            resolved_proposal_identity=candidate.resolved_proposal_identity,
            resolved_proposal=(
                None
                if candidate.resolved_proposal_json is None
                else json.loads(candidate.resolved_proposal_json)
            ),
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


class ForwardOutcomeResponse(BaseModel):
    horizon_id: str
    status: str
    due_at: datetime
    observed_at: datetime | None = None
    collected_at: datetime | None = None
    underlying_price: str | None = None
    modeled_mark: str | None = None
    modeled_pnl: str | None = None
    mark_basis: str | None = None
    mark_model_version: str | None = None
    unknown_reasons: list[str] = Field(default_factory=list)
    content_identity: str | None = None


class TrackedCandidateOutcomesResponse(BaseModel):
    tracked_candidate_id: UUID
    frozen_proposal_identity: str | None
    horizon_policy_version: str
    basis: str
    outcomes: list[ForwardOutcomeResponse]


def _text_or_none(value: object) -> str | None:
    return None if value is None else str(value)


def outcome_rows(
    anchor: datetime,
    structure: FrozenStructure | None,
    recorded_items: tuple[ForwardOutcomeObservation, ...],
) -> list[ForwardOutcomeResponse]:
    """Recorded outcomes plus computed, unstored pending horizons, in due order."""
    recorded = {item.horizon_id: item for item in recorded_items}
    outcomes: list[ForwardOutcomeResponse] = []
    for due in horizon_schedule(anchor, structure):
        item = recorded.get(due.horizon_id)
        if item is None:
            outcomes.append(
                ForwardOutcomeResponse(
                    horizon_id=due.horizon_id, status="pending", due_at=due.due_at
                )
            )
            continue
        outcomes.append(
            ForwardOutcomeResponse(
                horizon_id=item.horizon_id,
                status=item.status.value,
                due_at=item.due_at,
                observed_at=item.observed_at,
                collected_at=item.collected_at,
                underlying_price=_text_or_none(item.underlying_price),
                modeled_mark=_text_or_none(item.modeled_mark),
                modeled_pnl=_text_or_none(item.modeled_pnl),
                mark_basis=item.mark_basis,
                mark_model_version=item.mark_model_version,
                unknown_reasons=list(item.unknown_reasons),
                content_identity=item.content_identity,
            )
        )
    return outcomes


def build_portfolio_lifecycle_router(
    service: TrackCandidateService,
    repository: PortfolioLifecycleRepository,
    authorize: Callable[[Request], None],
    forward_outcome_repository: ForwardOutcomeRepository | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(authorize)])

    @router.get(
        "/portfolio/tracked-candidates/{candidate_id}/outcomes",
        response_model=TrackedCandidateOutcomesResponse,
    )
    def tracked_candidate_outcomes(candidate_id: UUID) -> TrackedCandidateOutcomesResponse:
        """Recorded forward outcomes plus computed, unstored pending horizons."""
        candidate = repository.candidate(candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="tracked candidate not found")
        structure = parse_frozen_structure(
            candidate.resolved_proposal_identity, candidate.resolved_proposal_json
        )
        outcomes = outcome_rows(
            candidate.evidence_observed_at,
            structure,
            ()
            if forward_outcome_repository is None
            else forward_outcome_repository.for_candidate(candidate_id),
        )
        return TrackedCandidateOutcomesResponse(
            tracked_candidate_id=candidate_id,
            frozen_proposal_identity=candidate.resolved_proposal_identity,
            horizon_policy_version=HORIZON_POLICY_VERSION,
            basis="paper_modeled_not_brokerage_fill; user_tracked_corpus",
            outcomes=outcomes,
        )

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
        except ProposalIdentityCollisionError:
            raise HTTPException(
                status_code=409,
                detail="tracked proposal identity collision for this observation",
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
