"""Universal strategy execution pipeline (SPRINT-009/EPIC-1).

run_strategies() is the one place every registered strategy executes. The
runtime owns orchestration and error isolation here; a strategy's adapter
owns only its own evaluation logic (this sprint's own runtime_owns_
infrastructure / strategies_own_thesis principles). This module contains
no forward_factor/earnings_calendar/skew_momentum conditional and never
will -- every decision it makes is derived from the StrategyRegistry and
StrategyContract it is given, matching EPIC-1's own acceptance criteria
directly (runtime executes arbitrary registered strategies; one strategy
failure never prevents others from executing; runtime has no strategy
conditionals).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from strategy_runtime.clock import Clock
from strategy_runtime.context import RuntimeContext
from strategy_runtime.registry import StrategyRegistry


class ExecutionStatus(str, Enum):
    COMPLETED = "completed"
    ADAPTER_EXCEPTION = "adapter_exception"


@dataclass(frozen=True, slots=True)
class StrategyExecutionResult[TResult]:
    strategy_id: str
    subject: str
    run_id: str
    status: ExecutionStatus
    result: TResult | None
    error_detail: str | None
    duration_seconds: float

    def __post_init__(self) -> None:
        if (self.status is ExecutionStatus.COMPLETED) != (self.result is not None):
            raise ValueError("StrategyExecutionResult status and result are inconsistent")
        if (self.status is ExecutionStatus.ADAPTER_EXCEPTION) != (self.error_detail is not None):
            raise ValueError("StrategyExecutionResult status and error_detail are inconsistent")
        if self.duration_seconds < 0:
            raise ValueError("StrategyExecutionResult.duration_seconds must be non-negative")


@dataclass(frozen=True, slots=True)
class RuntimeExecutionSummary:
    """Runtime diagnostics and metrics for one full run (EPIC-1's own
    "runtime diagnostics"/"runtime metrics" deliverables) -- computed
    entirely from a completed run's own StrategyExecutionResults, never
    tracked separately, so it cannot drift from what the run actually did.
    """

    run_id: str
    total: int
    completed: int
    failed: int
    total_duration_seconds: float

    @classmethod
    def from_results(
        cls, run_id: str, results: tuple[StrategyExecutionResult[object], ...]
    ) -> RuntimeExecutionSummary:
        completed = sum(1 for item in results if item.status is ExecutionStatus.COMPLETED)
        failed = sum(1 for item in results if item.status is ExecutionStatus.ADAPTER_EXCEPTION)
        return cls(
            run_id=run_id,
            total=len(results),
            completed=completed,
            failed=failed,
            total_duration_seconds=sum(item.duration_seconds for item in results),
        )


def _compute_run_id(
    strategy_ids: tuple[str, ...], subjects: tuple[str, ...], as_of: datetime
) -> str:
    payload = {
        "strategy_ids": list(strategy_ids),
        "subjects": list(subjects),
        "as_of": as_of.isoformat(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _run_one[TResult](
    registry: StrategyRegistry[TResult],
    strategy_id: str,
    subject: str,
    clock: Clock,
    run_id: str,
) -> StrategyExecutionResult[TResult]:
    adapter = registry.adapter_for(strategy_id)
    contract = registry.contract_for(strategy_id)
    context = RuntimeContext(contract, subject, clock, run_id)
    started_at = clock.now()
    try:
        result = adapter(context)
    except Exception as exc:
        finished_at = clock.now()
        return StrategyExecutionResult(
            strategy_id=strategy_id,
            subject=subject,
            run_id=run_id,
            status=ExecutionStatus.ADAPTER_EXCEPTION,
            result=None,
            error_detail=f"{type(exc).__name__}: unhandled adapter exception",
            duration_seconds=max(0.0, (finished_at - started_at).total_seconds()),
        )
    finished_at = clock.now()
    return StrategyExecutionResult(
        strategy_id=strategy_id,
        subject=subject,
        run_id=run_id,
        status=ExecutionStatus.COMPLETED,
        result=result,
        error_detail=None,
        duration_seconds=max(0.0, (finished_at - started_at).total_seconds()),
    )


def run_strategies[TResult](
    registry: StrategyRegistry[TResult],
    clock: Clock,
    *,
    subjects: tuple[str, ...],
    strategy_ids: tuple[str, ...] | None = None,
) -> tuple[StrategyExecutionResult[TResult], ...]:
    """Run every requested registered strategy against every requested
    subject, independently. One (strategy, subject) pair's adapter
    exception never prevents any other pair from executing -- enforced by
    _run_one's own isolation boundary, not merely documented, the same way
    screening/runner.py's own _run_one already isolates a screening
    strategy's exception without this module importing screening at all.

    Deterministically ordered: strategy-major, subject-minor, both sorted,
    for a given registry/subjects/strategy_ids/clock reading -- run_id is
    derived only from those inputs, never randomness, matching the
    determinism guarantee screening/runner.py's own run_screening()
    already provides for its own narrower scope.
    """
    requested_strategy_ids = tuple(
        sorted(strategy_ids if strategy_ids is not None else registry.strategy_ids())
    )
    for strategy_id in requested_strategy_ids:
        registry.contract_for(strategy_id)  # raises UnknownStrategyIdError before any execution
    if not subjects:
        raise ValueError("run_strategies requires at least one subject")
    sorted_subjects = tuple(sorted(subjects))

    as_of = clock.now()
    run_id = _compute_run_id(requested_strategy_ids, sorted_subjects, as_of)
    return tuple(
        _run_one(registry, strategy_id, subject, clock, run_id)
        for strategy_id in requested_strategy_ids
        for subject in sorted_subjects
    )
