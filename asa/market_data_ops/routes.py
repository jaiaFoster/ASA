"""POST /ops/market-data/validate -- protected, bounded live Market Data validation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, SecretStr

from asa.market_data_ops.auth import OperationsRunLimiter, token_matches
from asa.market_data_ops.service import ALLOWED_PROVIDER_IDS, run_bounded_validation
from domain import MarketCapability
from market_data.attempts import (
    MAXIMUM_QUERY_LIMIT,
    AcquisitionAttemptRepository,
    AcquisitionOutcome,
    AttemptQuery,
)
from market_data.live_transport import build_live_transport as build_transport_for_provider

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND)
_BAD_QUERY = status.HTTP_422_UNPROCESSABLE_ENTITY


class ValidateRequest(BaseModel):
    providers: list[str] = Field(default_factory=lambda: list(ALLOWED_PROVIDER_IDS))
    dry_run: bool = False


class CapabilityCheckResponse(BaseModel):
    capability: str
    normalized_check_status: str
    diagnostic_detail_code: str
    request_count: int
    latency: int | None
    entitlement_status: str
    schema_status: str
    freshness_status: str
    quota_metadata_when_safe: dict[str, str] | None
    redacted_failure_summary: str | None


class ProviderResultResponse(BaseModel):
    provider: str
    configuration_status: str
    checks: list[CapabilityCheckResponse]


class ValidateResponse(BaseModel):
    overall_status: str
    dry_run: bool
    generated_at: str
    providers: list[ProviderResultResponse]


class AttemptResponse(BaseModel):
    screening_cycle_id: str
    pair_evaluation_id: str
    sequence: int
    capability: str
    provider_id: str
    priority: int
    fulfillment_status: str
    outcome: str
    diagnostic_code: str | None
    retryable: bool
    safe_summary: str | None
    recorded_at: str


class AttemptListResponse(BaseModel):
    attempts: list[AttemptResponse]
    limit: int
    offset: int
    returned_count: int


class AttemptSummaryResponse(BaseModel):
    generated_at: str
    outcome_counts: dict[str, int]


def build_operations_router(
    operations_token: SecretStr | None,
    transport_factory: Callable[[str], object] = build_transport_for_provider,
    max_runs_per_hour: int | None = 50,
    acquisition_attempt_repository: AcquisitionAttemptRepository | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/ops")
    limiter = OperationsRunLimiter(max_runs_per_hour=max_runs_per_hour)

    def _authorize(request: Request) -> None:
        if operations_token is None:
            raise _NOT_FOUND
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise _NOT_FOUND
        presented = header[len("Bearer ") :]
        if not token_matches(presented, operations_token.get_secret_value()):
            raise _NOT_FOUND

    @router.post("/market-data/validate", response_model=ValidateResponse)
    def validate_market_data(payload: ValidateRequest, request: Request) -> ValidateResponse:
        _authorize(request)
        requested = tuple(payload.providers) or ALLOWED_PROVIDER_IDS
        invalid = set(requested) - set(ALLOWED_PROVIDER_IDS)
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="unsupported provider requested",
            )
        if not limiter.try_acquire():
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS)
        try:
            outcome = run_bounded_validation(
                requested_provider_ids=requested,
                dry_run=payload.dry_run,
                transport_factory=transport_factory,
            )
        finally:
            limiter.release()
        return ValidateResponse(
            overall_status=outcome.overall_status,
            dry_run=outcome.dry_run,
            generated_at=outcome.generated_at.isoformat(),
            providers=[
                ProviderResultResponse(
                    provider=provider.provider_id,
                    configuration_status=provider.configuration_status,
                    checks=[
                        CapabilityCheckResponse(
                            capability=check.capability.value,
                            normalized_check_status=check.normalized_check_status,
                            diagnostic_detail_code=check.diagnostic_detail_code,
                            request_count=check.request_count,
                            latency=check.latency_milliseconds,
                            entitlement_status=check.entitlement_status,
                            schema_status=check.schema_status,
                            freshness_status=check.freshness_status,
                            quota_metadata_when_safe=check.quota_metadata_when_safe,
                            redacted_failure_summary=check.redacted_failure_summary,
                        )
                        for check in provider.checks
                    ],
                )
                for provider in outcome.providers
            ],
        )

    def _build_attempt_query(
        screening_cycle_id: str | None,
        pair_evaluation_id: str | None,
        provider_id: str | None,
        capability: str | None,
        outcome_filter: str | None,
        recorded_after: str | None,
        recorded_before: str | None,
        limit: int,
        offset: int,
    ) -> AttemptQuery:
        try:
            parsed_capability = None if capability is None else MarketCapability(capability)
            parsed_outcome = (
                None if outcome_filter is None else AcquisitionOutcome(outcome_filter)
            )
            parsed_after = (
                None if recorded_after is None else datetime.fromisoformat(recorded_after)
            )
            parsed_before = (
                None if recorded_before is None else datetime.fromisoformat(recorded_before)
            )
            return AttemptQuery(
                screening_cycle_id=screening_cycle_id,
                pair_evaluation_id=pair_evaluation_id,
                provider_id=provider_id,
                capability=parsed_capability,
                outcome=parsed_outcome,
                recorded_after=parsed_after,
                recorded_before=parsed_before,
                limit=limit,
                offset=offset,
            )
        except ValueError as exc:
            raise HTTPException(status_code=_BAD_QUERY, detail="invalid query parameters") from exc

    @router.get("/screening/attempts", response_model=AttemptListResponse)
    def list_attempts(
        request: Request,
        screening_cycle_id: str | None = None,
        pair_evaluation_id: str | None = None,
        provider_id: str | None = None,
        capability: str | None = None,
        outcome: str | None = None,
        recorded_after: str | None = None,
        recorded_before: str | None = None,
        limit: int = Query(default=100, ge=1, le=MAXIMUM_QUERY_LIMIT),
        offset: int = Query(default=0, ge=0),
    ) -> AttemptListResponse:
        _authorize(request)
        if acquisition_attempt_repository is None:
            raise _NOT_FOUND
        parsed = _build_attempt_query(
            screening_cycle_id, pair_evaluation_id, provider_id, capability, outcome,
            recorded_after, recorded_before, limit, offset,
        )
        results = acquisition_attempt_repository.query(parsed)
        return AttemptListResponse(
            attempts=[
                AttemptResponse(
                    screening_cycle_id=item.screening_cycle_id,
                    pair_evaluation_id=item.pair_evaluation_id,
                    sequence=item.sequence,
                    capability=item.capability.value,
                    provider_id=item.provider_id,
                    priority=item.priority,
                    fulfillment_status=item.fulfillment_status.value,
                    outcome=item.outcome.value,
                    diagnostic_code=(
                        None if item.diagnostic_code is None else item.diagnostic_code.value
                    ),
                    retryable=item.retryable,
                    safe_summary=item.safe_summary,
                    recorded_at=item.recorded_at.isoformat(),
                )
                for item in results
            ],
            limit=parsed.limit,
            offset=parsed.offset,
            returned_count=len(results),
        )

    @router.get("/screening/attempts/summary", response_model=AttemptSummaryResponse)
    def summarize_attempts(
        request: Request,
        screening_cycle_id: str | None = None,
        pair_evaluation_id: str | None = None,
        provider_id: str | None = None,
        capability: str | None = None,
        recorded_after: str | None = None,
        recorded_before: str | None = None,
    ) -> AttemptSummaryResponse:
        _authorize(request)
        if acquisition_attempt_repository is None:
            raise _NOT_FOUND
        parsed = _build_attempt_query(
            screening_cycle_id, pair_evaluation_id, provider_id, capability, None,
            recorded_after, recorded_before, 1, 0,
        )
        counts = acquisition_attempt_repository.summarize(parsed)
        return AttemptSummaryResponse(
            generated_at=datetime.now(UTC).isoformat(),
            outcome_counts={key.value: value for key, value in counts.items()},
        )

    return router
