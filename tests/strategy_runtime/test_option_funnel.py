from __future__ import annotations

from datetime import UTC, datetime

from domain import MarketCapability
from strategy_runtime.contract import (
    NO_LIFECYCLE,
    DataRequirement,
    OutputKind,
    RequirementCategory,
    StrategyCapability,
    StrategyContract,
    StructureKind,
)
from strategy_runtime.executable_structures import (
    ExecutableStructureAssessment,
    ExecutableStructureStatus,
)
from strategy_runtime.option_funnel import (
    CapabilityDemandDiagnostic,
    acquisition_diagnostics_from_result,
    attach_acquisition_diagnostics,
    build_option_funnel_trace,
)
from strategy_runtime.result import EvaluationState, RowType, UniversalScreeningResult
from strategy_runtime.values import TypedValue

NOW = datetime(2026, 9, 23, 16, tzinfo=UTC)


def _contract() -> StrategyContract:
    return StrategyContract(
        strategy_id="option_test",
        version="1.0.0",
        category="options_test",
        description="Option funnel test strategy.",
        requirements=(
            DataRequirement(
                RequirementCategory.OPTION_DATA,
                capabilities=(MarketCapability.OPTION_CHAIN_V1,),
            ),
        ),
        lifecycle=NO_LIFECYCLE,
        structure=StructureKind.CALENDAR,
        outputs=(OutputKind.METRICS,),
        capabilities=(StrategyCapability.OPTION_STRUCTURES,),
    )


def _result(
    *,
    state: EvaluationState = EvaluationState.PASS,
    verdict: str | None = "PASS",
    blockers: tuple[str, ...] = (),
) -> UniversalScreeningResult:
    return UniversalScreeningResult(
        strategy_id="option_test",
        strategy_version="1.0.0",
        symbol="AAPL",
        observation_id="observation-1",
        opportunity_id=None,
        row_type=RowType.RESULT,
        verdict=verdict,
        evaluation_state=state,
        lifecycle_stage=None,
        recommendation_state=None,
        data_quality=None,
        metrics={"gate.liquidity": TypedValue.of_boolean(True)},
        economics={},
        blockers=blockers,
        warnings=(),
        provenance=(),
        observed_at=NOW,
    )


def test_acquisition_diagnostics_round_trip_through_existing_result_metrics() -> None:
    diagnostic = CapabilityDemandDiagnostic(
        demand_id="demand-1",
        capability=MarketCapability.OPTION_CHAIN_V1.value,
        acquisition_result="fulfilled",
        evidence_usability="resolved",
        reused_across_consumers=True,
        attempt_count=1,
        missing_reason=None,
    )

    result = attach_acquisition_diagnostics(_result(), (diagnostic,))

    assert acquisition_diagnostics_from_result(result) == (diagnostic,)


def test_missing_data_has_typed_terminal_reason() -> None:
    diagnostic = CapabilityDemandDiagnostic(
        demand_id="demand-1",
        capability=MarketCapability.OPTION_CHAIN_V1.value,
        acquisition_result="failed",
        evidence_usability="unknown",
        reused_across_consumers=False,
        attempt_count=2,
        missing_reason="no_data",
    )
    result = attach_acquisition_diagnostics(
        _result(
            state=EvaluationState.MISSING_DATA,
            verdict=None,
            blockers=("typed unknown evidence gap: no_option_contracts",),
        ),
        (diagnostic,),
    )

    trace = build_option_funnel_trace(result, _contract(), None)

    assert trace.terminal_state == "evidence_unavailable"
    assert trace.terminal_reason == "typed unknown evidence gap: no_option_contracts"
    assert trace.acquisition == (diagnostic,)
    assert trace.gate_outcomes == (("liquidity", True),)


def test_unresolved_structure_is_explicit_not_silently_actionable() -> None:
    trace = build_option_funnel_trace(_result(), _contract(), None)

    assert trace.terminal_state == "structure_unresolved"
    assert trace.terminal_reason == "execution_readiness_not_available"


def test_not_constructible_assessment_terminates_with_its_reason() -> None:
    assessment = ExecutableStructureAssessment(
        originating_result_identity="observation-1",
        subject="AAPL",
        intended_structure_kind=StructureKind.CALENDAR,
        status=ExecutableStructureStatus.NOT_CONSTRUCTIBLE,
        exact_legs=(),
        selection_diagnostics=(),
        modeled_entry_economics=None,
        evidence_snapshot_identity="snapshot-1",
        assessed_at=NOW,
        reason_code="no_common_strike",
    )

    trace = build_option_funnel_trace(_result(), _contract(), assessment)

    assert trace.structure_status == "not_constructible"
    assert trace.terminal_state == "structure_unavailable"
    assert trace.terminal_reason == "no_common_strike"
