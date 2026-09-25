"""Read-only system-enrollment outcomes (ND-01).

``system_actionable`` enrollments are served only here: never through the
portfolio or tracking endpoints. Each row carries its ``enrollment_source``.
The "also tracked by user" flag is derived by join, never stored.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from asa.api.portfolio_lifecycle_routes import ForwardOutcomeResponse, outcome_rows
from asa.application.ports.portfolio_lifecycle import PortfolioLifecycleRepository
from asa.application.ports.proposal_enrollment import ProposalEnrollmentRepository
from asa.contracts.proposal_enrollment import SYSTEM_ACTIONABLE
from strategy_runtime.forward_outcome import HORIZON_POLICY_VERSION, parse_frozen_structure


class SystemEnrollmentOutcomesResponse(BaseModel):
    enrollment_id: UUID
    enrollment_source: str
    enrollment_policy_version: str
    signal_id: str
    signal_version: str
    symbol: str
    opportunity_id: str | None
    session_date: date
    evidence_observed_at: datetime
    enrolled_at: datetime
    frozen_proposal_identity: str
    # Re-enrollment across sessions is allowed; reports show distinct
    # opportunity and exact-leg-set counts next to the row count (§4).
    exact_leg_set: list[str]
    also_tracked_by_user: bool
    horizon_policy_version: str
    basis: str
    outcomes: list[ForwardOutcomeResponse]


def build_forward_outcome_router(
    enrollments: ProposalEnrollmentRepository,
    lifecycle: PortfolioLifecycleRepository,
    authorize: Callable[[Request], None],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(authorize)])

    @router.get(
        "/forward-outcomes/system-enrollments",
        response_model=list[SystemEnrollmentOutcomesResponse],
    )
    def system_enrollment_outcomes() -> list[SystemEnrollmentOutcomesResponse]:
        tracked = {
            item.resolved_proposal_identity
            for item in lifecycle.candidates()
            if item.resolved_proposal_identity is not None
        }
        rows: list[SystemEnrollmentOutcomesResponse] = []
        for item in sorted(
            enrollments.enrollments(), key=lambda value: (value.session_date, str(value.id))
        ):
            structure = parse_frozen_structure(
                item.resolved_proposal_identity, item.resolved_proposal_json
            )
            rows.append(
                SystemEnrollmentOutcomesResponse(
                    enrollment_id=item.id,
                    enrollment_source=SYSTEM_ACTIONABLE,
                    enrollment_policy_version=item.enrollment_policy_version,
                    signal_id=item.signal_id,
                    signal_version=item.signal_version,
                    symbol=item.symbol,
                    opportunity_id=item.opportunity_id,
                    session_date=item.session_date,
                    evidence_observed_at=item.evidence_observed_at,
                    enrolled_at=item.enrolled_at,
                    frozen_proposal_identity=item.resolved_proposal_identity,
                    exact_leg_set=sorted(
                        ()
                        if structure is None
                        else {leg.canonical_contract_identity for leg in structure.legs}
                    ),
                    also_tracked_by_user=item.resolved_proposal_identity in tracked,
                    horizon_policy_version=HORIZON_POLICY_VERSION,
                    basis="paper_modeled_not_brokerage_fill; system_actionable_corpus",
                    outcomes=outcome_rows(
                        item.evidence_observed_at, structure, enrollments.outcomes_for(item.id)
                    ),
                )
            )
        return rows

    return router
