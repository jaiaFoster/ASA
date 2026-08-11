"""Shared translation from screening.results.ScreeningResult to
strategy_runtime.result.UniversalScreeningResult (SPRINT-009/EPIC-7).

Not a strategy adapter itself -- the one piece every migrated strategy's
own thin adapter module shares, so the translation rule is written once
and applied identically to all three, rather than copied three times
with three chances to drift. This is exactly this sprint's own
generalize_before_specialize principle applied to the migration work
itself: even the migration's own plumbing gets generalized before being
copy-pasted per strategy.

``explanation_metrics()`` (SPRINT-014 S14-PR-05A) is public rather than
module-private because it is now shared by more than
translate_screening_result()'s own ScreeningResult-shaped call site: the
new subject-first Earnings adapter (strategy_runtime/adapters/
earnings_calendar_subject_first.py) projects a ComponentValues graph
result directly into UniversalScreeningResult, with no ScreeningResult in
between, and reuses this exact metrics-extraction rule rather than a
second, independently maintained copy.
"""

from __future__ import annotations

from decimal import Decimal

from screening.results import ScreeningExplanation, ScreeningOutcomeStatus, ScreeningResult
from strategy_runtime.result import EvaluationState, RowType, UniversalScreeningResult
from strategy_runtime.values import TypedValue

_EVALUATION_STATE_BY_OUTCOME: dict[ScreeningOutcomeStatus, EvaluationState] = {
    ScreeningOutcomeStatus.PASS: EvaluationState.PASS,
    ScreeningOutcomeStatus.NO_SIGNAL: EvaluationState.NO_SIGNAL,
    ScreeningOutcomeStatus.MISSING_DATA: EvaluationState.MISSING_DATA,
    ScreeningOutcomeStatus.MALFORMED_OUTPUT: EvaluationState.MALFORMED_OUTPUT,
    ScreeningOutcomeStatus.STRATEGY_EXCEPTION: EvaluationState.ADAPTER_EXCEPTION,
}

_SUCCESS_OUTCOMES = frozenset({ScreeningOutcomeStatus.PASS, ScreeningOutcomeStatus.NO_SIGNAL})


def _provenance(result: ScreeningResult) -> tuple[str, ...]:
    entries = []
    for item in (*result.evidence, *result.input_provenance):
        suffix = f"@{item.version}" if item.version is not None else ""
        entries.append(f"{item.kind.value}:{item.referenced_id}{suffix}")
    return tuple(entries)


def _typed_explanation_value(value: object) -> TypedValue:
    if value is None:
        return TypedValue.of_string("UNKNOWN")
    if isinstance(value, bool):
        return TypedValue.of_boolean(value)
    if isinstance(value, int):
        return TypedValue.of_integer(value)
    if isinstance(value, Decimal):
        return TypedValue.of_decimal(value)
    return TypedValue.of_string(str(value))


def explanation_metrics(explanation: ScreeningExplanation | None) -> dict[str, TypedValue]:
    if explanation is None:
        return {}
    metrics = {
        f"fact.{name}": _typed_explanation_value(value)
        for name, value in explanation.canonical_facts
    }
    metrics.update(
        {
            f"derived_fact.{name}": _typed_explanation_value(value)
            for name, value in explanation.named_derived_facts
        }
    )
    metrics.update(
        {
            f"formula_version.{name}": TypedValue.of_string(version)
            for name, version in explanation.formula_versions
        }
    )
    metrics.update(
        {
            f"gate.{name}": _typed_explanation_value(value)
            for name, value in explanation.gate_results
        }
    )
    if explanation.direction is not None:
        metrics["decision.direction"] = TypedValue.of_string(explanation.direction)
    if explanation.structure is not None:
        metrics["decision.structure"] = TypedValue.of_string(explanation.structure)
    metrics["decision.reason_codes"] = TypedValue.of_structured(
        list(explanation.reason_codes)
    )
    metrics["decision.assumptions"] = TypedValue.of_structured(
        list(explanation.assumptions)
    )
    return metrics


def translate_screening_result(
    result: ScreeningResult,
    *,
    symbol: str,
    observation_id: str,
    opportunity_id: str | None,
    lifecycle_stage: str | None,
) -> UniversalScreeningResult:
    """Translate one ScreeningResult (the existing, unmodified execution
    graph's own output -- strategies/stonk_manifests.py compiled and run
    exactly as it already was) into this sprint's universal envelope.
    ``symbol`` is the caller's own known subject, never
    ``result.subject_identity`` -- runner.py's own documented convention
    sets that field to "unknown" for a StrategyAdapterError-raised
    failure, exactly the case this translation must still represent
    correctly.
    """
    is_success = result.outcome_status in _SUCCESS_OUTCOMES
    metrics = explanation_metrics(result.explanation)
    metrics.update(
        {"strategy_native_score": TypedValue.of_decimal(result.strategy_native_score)}
        if result.strategy_native_score is not None
        else {}
    )
    return UniversalScreeningResult(
        strategy_id=result.strategy_id,
        strategy_version=result.strategy_version,
        symbol=symbol,
        observation_id=observation_id,
        opportunity_id=opportunity_id if is_success else None,
        row_type=RowType.RESULT,
        verdict=result.signal_classification if is_success else None,
        evaluation_state=_EVALUATION_STATE_BY_OUTCOME[result.outcome_status],
        lifecycle_stage=lifecycle_stage if is_success else None,
        recommendation_state=None,
        data_quality=None,
        metrics=metrics,
        economics={},
        blockers=(result.failure_detail,) if result.failure_detail else (),
        warnings=result.explanation.warnings if result.explanation is not None else (),
        provenance=_provenance(result),
        observed_at=result.as_of,
    )
