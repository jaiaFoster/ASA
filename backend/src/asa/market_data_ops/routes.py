"""POST /ops/market-data/validate -- protected, bounded live Market Data validation."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Request, status
from market_data.live_transport import build_live_transport as build_transport_for_provider
from pydantic import BaseModel, Field, SecretStr

from asa.market_data_ops.auth import OperationsRunLimiter, token_matches
from asa.market_data_ops.service import ALLOWED_PROVIDER_IDS, run_bounded_validation

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND)


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


def build_operations_router(
    operations_token: SecretStr | None,
    transport_factory: Callable[[str], object] = build_transport_for_provider,
    max_runs_per_hour: int | None = 50,
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

    return router
