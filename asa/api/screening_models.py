"""Response models for the public /api/v1/screening* and /api/v1/capabilities
endpoints (API-003, API-004, SPRINT-008).

Built on asa.api.agent_models.TimestampedResource so every screening result
exposes updated_at/age_seconds through the one place that computes it, per
this sprint's own architecture_principles ("every_resource_is_independently_
timestamped").
"""

from __future__ import annotations

from pydantic import BaseModel

from asa.api.agent_models import TimestampedResource
from screening.registry import SignalDefinition
from screening.state import ScreeningStateRecord


class SignalCapabilityResponse(BaseModel):
    signal_id: str
    signal_version: str
    manifest_id: str
    required_capabilities: list[str]

    @classmethod
    def from_definition(cls, definition: SignalDefinition) -> SignalCapabilityResponse:
        return cls(
            signal_id=definition.signal_id,
            signal_version=definition.signal_version,
            manifest_id=definition.manifest_id,
            required_capabilities=[item.value for item in definition.required_capabilities],
        )


class CapabilitiesResponse(BaseModel):
    signals: list[SignalCapabilityResponse]


class ScreeningResultResponse(TimestampedResource):
    signal_id: str
    signal_version: str
    symbol: str
    outcome: str
    explanation: str | None
    metrics: dict[str, str]

    @classmethod
    def from_record(cls, record: ScreeningStateRecord) -> ScreeningResultResponse:
        return cls(
            signal_id=record.signal_id,
            signal_version=record.signal_version,
            symbol=record.symbol,
            outcome=record.outcome,
            explanation=record.explanation,
            metrics=record.metrics,
            updated_at=record.updated_at,
            age_seconds=TimestampedResource.age_seconds_since(record.updated_at),
        )


class ScreeningResultsEnvelope(BaseModel):
    results: list[ScreeningResultResponse]
    total: int
    limit: int
    offset: int


class RefreshResultResponse(ScreeningResultResponse):
    """Extends, not duplicates, ScreeningResultResponse -- a refresh result
    is a screening result plus how many live provider requests it took
    (API-004's own "request_accounting" requirement). Never the raw
    RequestAccountingEntry records themselves: provider identity, quota
    detail, and retry mechanics stay internal
    (architecture_principles: "provider_implementations_remain_completely_
    internal"), not exposed in a public response.
    """

    request_count: int

    @classmethod
    def from_record(  # type: ignore[override]
        cls, record: ScreeningStateRecord, *, request_count: int
    ) -> RefreshResultResponse:
        base = ScreeningResultResponse.from_record(record)
        return cls(request_count=request_count, **base.model_dump())
