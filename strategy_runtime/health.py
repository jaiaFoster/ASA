from collections import Counter
from dataclasses import dataclass

from strategy_runtime.result import (
    SUCCESS_EVALUATION_STATES,
    EvaluationState,
    UniversalScreeningResult,
)


@dataclass(frozen=True, slots=True)
class StrategyHealthFunnel:
    strategy_id: str
    active_subjects: int
    evaluated: int
    evidence_sufficient: int
    structure_eligible_or_constructible: int
    gates_passed: int
    watch: int
    passed: int
    typed_unknown_counts: tuple[tuple[str, int], ...]
    typed_rejection_counts: tuple[tuple[str, int], ...]


def build_strategy_health(
    strategy_id: str,
    records: tuple[UniversalScreeningResult, ...],
) -> StrategyHealthFunnel:
    evaluated_records = tuple(
        item for item in records if item.evaluation_state in SUCCESS_EVALUATION_STATES
    )
    unknowns: Counter[str] = Counter()
    rejections: Counter[str] = Counter()
    for item in records:
        reasons = _reasons(item)
        destination = (
            unknowns if item.evaluation_state not in SUCCESS_EVALUATION_STATES else rejections
        )
        for reason in reasons:
            destination[reason] += 1
    watch = sum(_verdict(item) == "WATCH" for item in evaluated_records)
    passed = sum(_verdict(item) == "PASS" for item in evaluated_records)
    structure_eligible = sum("decision.structure" in item.metrics for item in evaluated_records)
    return StrategyHealthFunnel(
        strategy_id=strategy_id,
        active_subjects=len(records),
        evaluated=len(evaluated_records),
        evidence_sufficient=len(evaluated_records),
        structure_eligible_or_constructible=structure_eligible,
        gates_passed=watch + passed,
        watch=watch,
        passed=passed,
        typed_unknown_counts=tuple(sorted(unknowns.items())),
        typed_rejection_counts=tuple(sorted(rejections.items())),
    )


def _verdict(item: UniversalScreeningResult) -> str:
    return (item.verdict or "").upper()


def _reasons(item: UniversalScreeningResult) -> tuple[str, ...]:
    reason_metric = item.metrics.get("decision.reason_codes")
    native = None if reason_metric is None else reason_metric.native()
    metric_reasons = tuple(str(value) for value in native) if isinstance(native, list) else ()
    temporal_reasons = (
        (item.temporal.usability_reason,)
        if item.temporal is not None and item.evaluation_state is EvaluationState.MISSING_DATA
        else ()
    )
    explicit = tuple(item.blockers) + tuple(item.warnings) + metric_reasons + temporal_reasons
    if explicit:
        return explicit
    if _verdict(item) == "PASS":
        return ()
    return (
        (f"verdict:{_verdict(item).lower()}",)
        if item.verdict
        else (f"evaluation_state:{item.evaluation_state.value}",)
    )
