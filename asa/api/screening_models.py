"""Response models for the public /api/v1/screening* and /api/v1/capabilities
endpoints (API-003, API-004, SPRINT-008).

Built on asa.api.agent_models.TimestampedResource so every screening result
exposes updated_at/age_seconds through the one place that computes it, per
this sprint's own architecture_principles ("every_resource_is_independently_
timestamped").
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from asa.api.agent_models import TimestampedResource
from strategy_runtime.catalog import SignalCatalogEntry
from strategy_runtime.executable_structures import ExecutableStructureAssessment
from strategy_runtime.lifecycle import OpportunityHistory, OpportunityObservation
from strategy_runtime.modeled_pnl import ModeledPnLSurface
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
_EXPLANATION_PREFIXES = (
    "fact.",
    "derived_fact.",
    "formula_version.",
    "gate.",
    "decision.",
)


def _wire_metrics(result: UniversalScreeningResult) -> dict[str, str]:
    """TypedValue -> str, reproducing exactly the plain-string wire format
    every caller of this API already parses. A Decimal's str() form
    round-trips exactly through TypedValue.of_decimal()/.native() (Python's
    own Decimal.__str__ is stable under that round trip), so this is
    byte-identical to the pre-EPIC-R2 str(strategy_native_score) wire value.
    """
    return {
        key: str(value.native())
        for key, value in result.metrics.items()
        if not key.startswith(_EXPLANATION_PREFIXES)
    }


def _prefixed_values(result: UniversalScreeningResult, prefix: str) -> dict[str, str]:
    return {
        key.removeprefix(prefix): str(value.native())
        for key, value in result.metrics.items()
        if key.startswith(prefix)
    }


def _decision_sequence(result: UniversalScreeningResult, key: str) -> list[str]:
    metric = result.metrics.get(key)
    if metric is None:
        return []
    native = metric.native()
    return [str(item) for item in native] if isinstance(native, list) else []


def _wire_values(result: dict[str, object]) -> dict[str, str]:
    return {key: str(value) for key, value in result.items()}


def _wire_explanation(result: UniversalScreeningResult) -> str | None:
    return result.verdict or (result.blockers[0] if result.blockers else None)


class SignalCapabilityResponse(BaseModel):
    signal_id: str
    signal_version: str
    manifest_id: str
    required_capabilities: list[str]

    @classmethod
    def from_definition(cls, definition: SignalCatalogEntry) -> SignalCapabilityResponse:
        return cls(
            signal_id=definition.signal_id,
            signal_version=definition.signal_version,
            manifest_id=definition.manifest_id,
            required_capabilities=[item.value for item in definition.required_capabilities],
        )


class CapabilitiesResponse(BaseModel):
    signals: list[SignalCapabilityResponse]


class ScreeningOperationalHealthResponse(BaseModel):
    last_attempted_batch_at: datetime | None
    last_successful_batch_at: datetime | None
    oldest_subject_age: int | None
    overdue_subject_count: int
    last_batch_subject_count: int
    last_batch_pair_count: int
    last_batch_failure_count: int
    last_batch_incomplete_diagnostic_count: int


class ReasonCountResponse(BaseModel):
    reason: str
    count: int


class StrategyHealthFunnelResponse(BaseModel):
    strategy_id: str
    active_subjects: int
    evaluated: int
    missing_data: int
    no_signal: int
    retained_nonactive: int
    evidence_sufficient: int
    structure_eligible_or_constructible: int
    gates_passed: int
    watch: int
    passed: int
    typed_unknown_counts: list[ReasonCountResponse]
    typed_rejection_counts: list[ReasonCountResponse]


class StrategyHealthResponse(BaseModel):
    strategies: list[StrategyHealthFunnelResponse]


class ScreeningResultResponse(TimestampedResource):
    signal_id: str
    signal_version: str
    symbol: str
    outcome: str
    evaluation_state: str
    verdict: str | None
    explanation: str | None
    metrics: dict[str, str]
    observation_id: str | None = None
    opportunity_id: str | None = None
    opportunity_history_url: str | None = None
    row_type: str | None = None
    lifecycle_stage: str | None = None
    status: str | None = None
    data_quality: str | None = None
    freshness: str | None = None
    economics: dict[str, str] = Field(default_factory=dict)
    metric_types: dict[str, str] = Field(default_factory=dict)
    economics_types: dict[str, str] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)
    canonical_facts: dict[str, str] = Field(default_factory=dict)
    named_derived_facts: dict[str, str] = Field(default_factory=dict)
    formula_versions: dict[str, str] = Field(default_factory=dict)
    gate_results: dict[str, str] = Field(default_factory=dict)
    direction: str | None = None
    structure: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    subject_snapshot_at: datetime
    observed_at: datetime
    received_at: datetime
    evaluated_at: datetime
    persisted_at: datetime
    market_session_date: date | None = None
    market_session_status: str = "unknown"
    last_refresh_attempt_at: datetime
    last_successful_refresh_at: datetime
    next_refresh_at: datetime | None = None
    data_advanced_on_last_refresh: bool = False
    freshness_status: str = "unknown"
    usability_status: str = "unknown"
    usability_reason: str = "temporal metadata unavailable"
    warning_codes: list[str] = Field(default_factory=list)
    acquisition_started_at: datetime
    acquisition_completed_at: datetime
    input_time_skew_seconds: int = Field(ge=0, default=0)

    @classmethod
    def from_universal_result(cls, result: UniversalScreeningResult) -> ScreeningResultResponse:
        """Build the public response from the canonical universal result."""
        temporal = result.temporal
        observed_at = temporal.observed_at if temporal is not None else result.observed_at
        subject_snapshot_at = (
            temporal.subject_snapshot_at if temporal is not None else result.observed_at
        )
        received_at = temporal.received_at if temporal is not None else result.observed_at
        evaluated_at = temporal.evaluated_at if temporal is not None else result.observed_at
        persisted_at = temporal.persisted_at if temporal is not None else result.observed_at
        canonical_age = (
            temporal.age_seconds
            if temporal is not None
            else TimestampedResource.age_seconds_since(observed_at)
        )
        freshness_status = (
            temporal.freshness_status
            if temporal is not None
            else ("live" if canonical_age <= 86_400 else "stale")
        )
        return cls(
            signal_id=result.strategy_id,
            signal_version=result.strategy_version,
            symbol=result.symbol,
            outcome=(
                result.verdict.lower()
                if result.verdict is not None
                else _OUTCOME_WIRE_VALUES[result.evaluation_state]
            ),
            evaluation_state=_OUTCOME_WIRE_VALUES[result.evaluation_state],
            verdict=result.verdict,
            explanation=_wire_explanation(result),
            metrics=_wire_metrics(result),
            observation_id=result.observation_id,
            opportunity_id=result.opportunity_id,
            opportunity_history_url=(
                f"/api/v1/screening/opportunities/{result.opportunity_id}/history"
                if result.opportunity_id is not None
                else None
            ),
            row_type=result.row_type.value,
            lifecycle_stage=result.lifecycle_stage,
            status=result.recommendation_state,
            data_quality=result.data_quality,
            freshness=(
                "fresh" if freshness_status in {"fresh", "live", "prior_session"} else "stale"
            ),
            economics=_wire_values(
                {key: value.native() for key, value in result.economics.items()}
            ),
            metric_types={key: value.value_type.value for key, value in result.metrics.items()},
            economics_types={
                key: value.value_type.value for key, value in result.economics.items()
            },
            blockers=list(result.blockers),
            warnings=list(result.warnings),
            provenance=list(result.provenance),
            canonical_facts=_prefixed_values(result, "fact."),
            named_derived_facts=_prefixed_values(result, "derived_fact."),
            formula_versions=_prefixed_values(result, "formula_version."),
            gate_results=_prefixed_values(result, "gate."),
            direction=(
                str(result.metrics["decision.direction"].native())
                if "decision.direction" in result.metrics
                else None
            ),
            structure=(
                str(result.metrics["decision.structure"].native())
                if "decision.structure" in result.metrics
                else None
            ),
            reason_codes=_decision_sequence(result, "decision.reason_codes"),
            assumptions=_decision_sequence(result, "decision.assumptions"),
            updated_at=persisted_at,
            age_seconds=canonical_age,
            subject_snapshot_at=subject_snapshot_at,
            observed_at=observed_at,
            received_at=received_at,
            evaluated_at=evaluated_at,
            persisted_at=persisted_at,
            market_session_date=(temporal.market_session_date if temporal is not None else None),
            market_session_status=(
                temporal.market_session_status if temporal is not None else "unknown"
            ),
            last_refresh_attempt_at=(
                temporal.last_refresh_attempt_at if temporal is not None else result.observed_at
            ),
            last_successful_refresh_at=(
                temporal.last_successful_refresh_at if temporal is not None else result.observed_at
            ),
            next_refresh_at=(temporal.next_refresh_at if temporal is not None else None),
            data_advanced_on_last_refresh=(
                temporal.data_advanced_on_last_refresh if temporal is not None else False
            ),
            freshness_status=freshness_status,
            usability_status=(temporal.usability_status if temporal is not None else "unknown"),
            usability_reason=(
                temporal.usability_reason
                if temporal is not None
                else "temporal metadata unavailable"
            ),
            warning_codes=(list(temporal.warning_codes) if temporal is not None else []),
            acquisition_started_at=(
                temporal.acquisition_started_at if temporal is not None else result.observed_at
            ),
            acquisition_completed_at=(
                temporal.acquisition_completed_at if temporal is not None else result.observed_at
            ),
            input_time_skew_seconds=(
                temporal.input_time_skew_seconds if temporal is not None else 0
            ),
        )


class ScreeningResultsEnvelope(BaseModel):
    results: list[ScreeningResultResponse]
    total: int
    limit: int
    offset: int
    snapshot_identity: str
    scope: Literal["all_latest", "active_universe"]
    retained_nonactive_total: int


class ExactOptionLegResponse(BaseModel):
    canonical_contract_identity: str
    instrument_id_scheme: str
    instrument_id_value: str
    role: str
    call_or_put: str
    expiration: date
    strike: str
    long_or_short: str
    quantity: str
    bid: str | None
    ask: str | None
    midpoint: str | None
    actual_delta: str | None
    target_delta: str | None
    source_observed_at: datetime


class SelectionDiagnosticResponse(BaseModel):
    role: str
    target_delta: str | None
    actual_delta: str | None
    absolute_delta_deviation: str | None


class ModeledEntryResponse(BaseModel):
    reference: str = "midpoint"
    semantics: str = "modeled_reference_only"
    per_leg_references: dict[str, str]
    modeled_net_debit_or_credit: str
    model_version: str
    calculated_at: datetime


class ExecutableStructureAssessmentResponse(BaseModel):
    assessment_identity: str
    originating_result_identity: str
    subject: str
    intended_structure_kind: str
    status: str
    available_structure_kind: str | None
    exact_legs: list[ExactOptionLegResponse]
    selection_diagnostics: list[SelectionDiagnosticResponse]
    modeled_entry: ModeledEntryResponse | None
    evidence_snapshot_identity: str
    assessed_at: datetime
    reason_code: str | None

    @classmethod
    def from_assessment(
        cls, assessment: ExecutableStructureAssessment
    ) -> ExecutableStructureAssessmentResponse:
        return cls(
            assessment_identity=assessment.identity,
            originating_result_identity=assessment.originating_result_identity,
            subject=assessment.subject,
            intended_structure_kind=assessment.intended_structure_kind.value,
            status=assessment.status.value,
            available_structure_kind=(
                None
                if assessment.available_structure_kind is None
                else assessment.available_structure_kind.value
            ),
            exact_legs=[
                ExactOptionLegResponse(
                    canonical_contract_identity=item.canonical_contract_identity,
                    instrument_id_scheme=item.leg.contract.option_contract_id.scheme,
                    instrument_id_value=item.leg.contract.option_contract_id.value,
                    role=item.leg.role,
                    call_or_put=item.leg.contract.option_type.value,
                    expiration=item.leg.contract.expiration,
                    strike=str(item.leg.contract.strike),
                    long_or_short=item.leg.position.value,
                    quantity=str(item.leg.quantity),
                    bid=None
                    if item.leg.contract.bid is None
                    else str(item.leg.contract.bid),
                    ask=None
                    if item.leg.contract.ask is None
                    else str(item.leg.contract.ask),
                    midpoint=None if item.midpoint is None else str(item.midpoint),
                    actual_delta=None
                    if item.leg.contract.delta is None
                    else str(item.leg.contract.delta),
                    target_delta=None
                    if item.target_delta is None
                    else str(item.target_delta),
                    source_observed_at=item.leg.contract.observed_at,
                )
                for item in assessment.exact_legs
            ],
            selection_diagnostics=[
                SelectionDiagnosticResponse(
                    role=item.role,
                    target_delta=None
                    if item.target_delta is None
                    else str(item.target_delta),
                    actual_delta=None
                    if item.actual_delta is None
                    else str(item.actual_delta),
                    absolute_delta_deviation=(
                        None
                        if item.absolute_delta_deviation is None
                        else str(item.absolute_delta_deviation)
                    ),
                )
                for item in assessment.selection_diagnostics
            ],
            modeled_entry=(
                None
                if assessment.modeled_entry_economics is None
                else ModeledEntryResponse(
                    per_leg_references={
                        identity: str(value)
                        for identity, value in assessment.modeled_entry_economics.per_leg_midpoints
                    },
                    modeled_net_debit_or_credit=str(
                        assessment.modeled_entry_economics.modeled_net_debit_or_credit
                    ),
                    model_version=assessment.modeled_entry_economics.model_version,
                    calculated_at=assessment.modeled_entry_economics.calculated_at,
                )
            ),
            evidence_snapshot_identity=assessment.evidence_snapshot_identity,
            assessed_at=assessment.assessed_at,
            reason_code=assessment.reason_code,
        )


class ModeledPnLPointResponse(BaseModel):
    underlying_price: str
    modeled_pnl: str


class ModeledPnLSurfaceResponse(BaseModel):
    surface_identity: str
    structure_assessment_identity: str
    valuation_model_and_version: str
    valuation_time: datetime
    spot_reference: str
    points: list[ModeledPnLPointResponse]
    entry_fill_assumption: str
    volatility_assumptions: dict[str, str]
    annual_risk_free_rate: str
    annual_dividend_yield: str
    contract_multiplier: str
    semantics: str = "modeled_PnL_not_guaranteed_payoff"

    @classmethod
    def from_surface(cls, surface: ModeledPnLSurface) -> ModeledPnLSurfaceResponse:
        return cls(
            surface_identity=surface.identity,
            structure_assessment_identity=surface.structure_assessment_identity,
            valuation_model_and_version=surface.valuation_model_and_version,
            valuation_time=surface.valuation_time,
            spot_reference=str(surface.spot_reference),
            points=[
                ModeledPnLPointResponse(
                    underlying_price=str(item.underlying_price),
                    modeled_pnl=str(item.modeled_pnl),
                )
                for item in surface.points
            ],
            entry_fill_assumption=surface.entry_fill_assumption,
            volatility_assumptions={
                identity: str(value) for identity, value in surface.volatility_assumptions
            },
            annual_risk_free_rate=str(surface.annual_risk_free_rate),
            annual_dividend_yield=str(surface.annual_dividend_yield),
            contract_multiplier=str(surface.contract_multiplier),
        )


class ScreeningExecutionReadinessResponse(BaseModel):
    """Additive composition; the signal and assessment remain independent."""

    signal: ScreeningResultResponse
    execution_assessment: ExecutableStructureAssessmentResponse
    modeled_pnl: ModeledPnLSurfaceResponse | None = None


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
    provider_contacted: bool
    result_changed: bool
    refresh_failed: bool

    @classmethod
    def from_universal_result(  # type: ignore[override]
        cls,
        result: UniversalScreeningResult,
        *,
        request_count: int,
        provider_contacted: bool | None = None,
        result_changed: bool = True,
        refresh_failed: bool = False,
    ) -> RefreshResultResponse:
        base = ScreeningResultResponse.from_universal_result(result)
        return cls(
            request_count=request_count,
            provider_contacted=(
                request_count > 0 if provider_contacted is None else provider_contacted
            ),
            result_changed=result_changed,
            refresh_failed=refresh_failed,
            **base.model_dump(),
        )


class OpportunityObservationResponse(BaseModel):
    opportunity_id: str
    signal_id: str
    symbol: str
    lifecycle_stage: str
    verdict: str
    recommended_action: str
    observed_at: str

    @classmethod
    def from_observation(
        cls, observation: OpportunityObservation
    ) -> OpportunityObservationResponse:
        return cls(
            opportunity_id=observation.opportunity_id,
            signal_id=observation.strategy_id,
            symbol=observation.symbol,
            lifecycle_stage=observation.lifecycle_stage,
            verdict=observation.verdict,
            recommended_action=observation.recommended_action.value,
            observed_at=observation.observed_at.isoformat(),
        )


class OpportunityHistoryResponse(BaseModel):
    opportunity_id: str
    observations: list[OpportunityObservationResponse]
    total: int
    limit: int
    offset: int

    @classmethod
    def from_history(
        cls, history: OpportunityHistory, *, limit: int, offset: int
    ) -> OpportunityHistoryResponse:
        page = history.observations[offset : offset + limit]
        return cls(
            opportunity_id=history.opportunity_id,
            observations=[OpportunityObservationResponse.from_observation(item) for item in page],
            total=len(history.observations),
            limit=limit,
            offset=offset,
        )
