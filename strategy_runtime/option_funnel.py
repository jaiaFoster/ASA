"""Provider-neutral option opportunity funnel diagnostics (OPTIONS-TRUTH OT-02).

The funnel is a projection over existing authorities: subject-plan acquisition
diagnostics, the persisted universal result, and (when present) the immutable
execution-readiness assessment.  It owns no persistence and performs no
acquisition or financial interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from strategy_runtime.executable_structures import (
    ExecutableStructureAssessment,
    ExecutableStructureStatus,
)
from strategy_runtime.result import EvaluationState, UniversalScreeningResult
from strategy_runtime.values import JsonValue, TypedValue

if TYPE_CHECKING:
    from strategy_runtime.contract import StrategyContract


_ACQUISITION_METRIC = "diagnostic.acquisition_demands"


@dataclass(frozen=True, slots=True)
class CapabilityDemandDiagnostic:
    demand_id: str
    capability: str
    acquisition_result: str
    evidence_usability: str
    reused_across_consumers: bool
    attempt_count: int
    missing_reason: str | None

    def __post_init__(self) -> None:
        for name in ("demand_id", "capability", "acquisition_result", "evidence_usability"):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise ValueError(f"CapabilityDemandDiagnostic.{name} must be normalized")
        if self.attempt_count < 0:
            raise ValueError("CapabilityDemandDiagnostic.attempt_count must be non-negative")
        if self.evidence_usability == "resolved" and self.missing_reason is not None:
            raise ValueError("resolved evidence cannot carry a missing reason")
        if self.evidence_usability != "resolved" and not self.missing_reason:
            raise ValueError("unresolved evidence requires a missing reason")

    def to_data(self) -> dict[str, JsonValue]:
        return {
            "demand_id": self.demand_id,
            "capability": self.capability,
            "acquisition_result": self.acquisition_result,
            "evidence_usability": self.evidence_usability,
            "reused_across_consumers": self.reused_across_consumers,
            "attempt_count": self.attempt_count,
            "missing_reason": self.missing_reason,
        }

    @classmethod
    def from_data(cls, data: dict[str, object]) -> CapabilityDemandDiagnostic:
        attempt_count = data["attempt_count"]
        if not isinstance(attempt_count, int):
            raise ValueError("attempt_count must be an integer")
        return cls(
            demand_id=str(data["demand_id"]),
            capability=str(data["capability"]),
            acquisition_result=str(data["acquisition_result"]),
            evidence_usability=str(data["evidence_usability"]),
            reused_across_consumers=bool(data["reused_across_consumers"]),
            attempt_count=attempt_count,
            missing_reason=(
                None if data.get("missing_reason") is None else str(data["missing_reason"])
            ),
        )


@dataclass(frozen=True, slots=True)
class OptionFunnelTrace:
    strategy_id: str
    symbol: str
    candidate_inclusion_reason: str
    declared_capabilities: tuple[str, ...]
    acquisition: tuple[CapabilityDemandDiagnostic, ...]
    gate_outcomes: tuple[tuple[str, bool | None], ...]
    signal_verdict: str | None
    evaluation_state: str
    structure_status: str | None
    constructibility_reason: str | None
    terminal_state: str
    terminal_reason: str


def attach_acquisition_diagnostics(
    result: UniversalScreeningResult,
    diagnostics: tuple[CapabilityDemandDiagnostic, ...],
) -> UniversalScreeningResult:
    """Persist diagnostics through the result's existing typed metric envelope."""
    metrics = dict(result.metrics)
    metrics[_ACQUISITION_METRIC] = TypedValue.of_structured(
        [item.to_data() for item in diagnostics]
    )
    return replace(result, metrics=metrics)


def acquisition_diagnostics_from_result(
    result: UniversalScreeningResult,
) -> tuple[CapabilityDemandDiagnostic, ...]:
    value = result.metrics.get(_ACQUISITION_METRIC)
    if value is None:
        return ()
    native = value.native()
    if not isinstance(native, list):
        raise ValueError("diagnostic.acquisition_demands must be a list")
    diagnostics: list[CapabilityDemandDiagnostic] = []
    for item in native:
        if not isinstance(item, dict):
            raise ValueError("each acquisition diagnostic must be an object")
        diagnostics.append(CapabilityDemandDiagnostic.from_data(item))
    return tuple(diagnostics)


def build_option_funnel_trace(
    result: UniversalScreeningResult,
    contract: StrategyContract,
    assessment: ExecutableStructureAssessment | None,
) -> OptionFunnelTrace:
    """Compose the complete diagnostic projection without acquiring data."""
    declared = tuple(
        sorted(
            {
                capability.value
                for requirement in contract.requirements
                for capability in requirement.capabilities
            }
        )
    )
    gates: tuple[tuple[str, bool | None], ...] = tuple(
        sorted(
            (
                key.removeprefix("gate."),
                _gate_outcome(value),
            )
            for key, value in result.metrics.items()
            if key.startswith("gate.")
        )
    )
    structure_status = None if assessment is None else assessment.status.value
    constructibility_reason = None if assessment is None else assessment.reason_code
    terminal_state, terminal_reason = _terminal(result, assessment)
    return OptionFunnelTrace(
        strategy_id=result.strategy_id,
        symbol=result.symbol,
        candidate_inclusion_reason="active_universe_strategy_pair",
        declared_capabilities=declared,
        acquisition=acquisition_diagnostics_from_result(result),
        gate_outcomes=gates,
        signal_verdict=result.verdict,
        evaluation_state=result.evaluation_state.value,
        structure_status=structure_status,
        constructibility_reason=constructibility_reason,
        terminal_state=terminal_state,
        terminal_reason=terminal_reason,
    )


def _gate_outcome(value: TypedValue) -> bool | None:
    native = value.native()
    return native if isinstance(native, bool) else None


def _terminal(
    result: UniversalScreeningResult,
    assessment: ExecutableStructureAssessment | None,
) -> tuple[str, str]:
    if result.evaluation_state not in {
        EvaluationState.PASS,
        EvaluationState.NO_SIGNAL,
    }:
        reason = result.blockers[0] if result.blockers else result.evaluation_state.value
        return "evidence_unavailable", reason
    if (result.verdict or "").upper() not in {"PASS", "WATCH"}:
        reasons = result.metrics.get("decision.reason_codes")
        native = None if reasons is None else reasons.native()
        reason = (
            str(native[0]) if isinstance(native, list) and native else "strategy_gates_rejected"
        )
        return "strategy_rejected", reason
    if assessment is None:
        return "structure_unresolved", "execution_readiness_not_available"
    if assessment.status is ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED:
        return "actionable_opportunity", "constructible_as_intended"
    if assessment.status is ExecutableStructureStatus.DIFFERENT_STRUCTURE_AVAILABLE:
        return "structure_unavailable", assessment.reason_code or "different_structure_available"
    if assessment.status is ExecutableStructureStatus.NOT_CONSTRUCTIBLE:
        return "structure_unavailable", assessment.reason_code or "not_constructible"
    return "structure_unknown", assessment.reason_code or "constructibility_unknown"
