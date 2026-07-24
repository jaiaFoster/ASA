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
from strategy_runtime.result import EvaluationState, UniversalScreeningResult

# SPRINT-009R/EPIC-R5: the public wire vocabulary predates strategy_runtime and must not
# change under callers -- EvaluationState.ADAPTER_EXCEPTION is the same execution-level
# outcome screening.results.ScreeningOutcomeStatus.STRATEGY_EXCEPTION already named, just
# renamed internally (strategy_runtime.execution's own vocabulary, see execution.py's own
# ExecutionStatus.ADAPTER_EXCEPTION). Translate it back at this one boundary so the response
# body a caller already parses never changes.
_OUTCOME_WIRE_VALUES = {
    EvaluationState.PASS: "pass",
    EvaluationState.NO_SIGNAL: "no_signal",
    EvaluationState.MISSING_DATA: "missing_data",
    EvaluationState.MALFORMED_OUTPUT: "malformed_output",
    EvaluationState.ADAPTER_EXCEPTION: "strategy_exception",
}


def _wire_metrics(result: UniversalScreeningResult) -> dict[str, str]:
    """TypedValue -> str, reproducing exactly the plain-string wire format
    every caller of this API already parses. A Decimal's str() form
    round-trips exactly through TypedValue.of_decimal()/.native() (Python's
    own Decimal.__str__ is stable under that round trip), so this is
    byte-identical to the pre-EPIC-R2 str(strategy_native_score) wire value.
    """
    return {key: str(value.native()) for key, value in result.metrics.items()}


def _wire_explanation(result: UniversalScreeningResult) -> str | None:
    return result.verdict or (result.blockers[0] if result.blockers else None)


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

    @classmethod
    def from_universal_result(cls, result: UniversalScreeningResult) -> ScreeningResultResponse:
        """SPRINT-009R/EPIC-R5: the strategy_runtime-backed equivalent of
        from_record() -- same public response shape, sourced from
        UniversalScreeningResult instead of the legacy ScreeningStateRecord.
        """
        return cls(
            signal_id=result.strategy_id,
            signal_version=result.strategy_version,
            symbol=result.symbol,
            outcome=_OUTCOME_WIRE_VALUES[result.evaluation_state],
            explanation=_wire_explanation(result),
            metrics=_wire_metrics(result),
            updated_at=result.observed_at,
            age_seconds=TimestampedResource.age_seconds_since(result.observed_at),
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

    @classmethod
    def from_universal_result(  # type: ignore[override]
        cls, result: UniversalScreeningResult, *, request_count: int
    ) -> RefreshResultResponse:
        base = ScreeningResultResponse.from_universal_result(result)
        return cls(request_count=request_count, **base.model_dump())
