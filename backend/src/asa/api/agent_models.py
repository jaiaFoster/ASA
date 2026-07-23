"""Shared response conventions for the public Agent Data API
(API-001, SPRINT-008).

Every screening resource must expose updated_at and age_seconds (this
sprint's own response_requirements) -- TimestampedResource is the one
place age_seconds gets computed, so API-003/API-004's actual response
models compose it rather than each recomputing "now minus updated_at"
independently.

AgentApiError is this API's deterministic error model: every error
response from the new /api/v1/screening* endpoints has the same
{error_code, message} shape -- never a raw Python exception string or a
provider payload. Scoped to the new namespace only (via agent_api_error()),
not retrofitted onto the whole application's existing error responses,
which would be an unplanned behavior change for already-shipped endpoints.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from pydantic import BaseModel, Field


class TimestampedResource(BaseModel):
    updated_at: datetime
    age_seconds: int = Field(ge=0)

    @staticmethod
    def age_seconds_since(updated_at: datetime, *, now: datetime | None = None) -> int:
        reference = now or datetime.now(UTC)
        return max(0, int((reference - updated_at).total_seconds()))


class AgentApiError(BaseModel):
    error_code: str
    message: str


def agent_api_error(status_code: int, error_code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=AgentApiError(error_code=error_code, message=message).model_dump(),
    )
