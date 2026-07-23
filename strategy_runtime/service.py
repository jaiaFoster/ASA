"""Universal screening service (SPRINT-009/EPIC-9).

Generalizes screening.service's own get_state()/refresh() shape to the
universal runtime: get_state() only ever reads through an injected
LatestResultRepository (never triggers acquisition, matching this
sprint's own architecture_principles); refresh() calls run_strategies()
for exactly one requested strategy against one subject, then persists the
result through the same injected repository -- bounded, narrow, no
whole-universe execution, matching screening.service's own exact
guarantee for the same reason.

Both functions translate between UniversalScreeningResult (this module's
own public parameter/return type, same as every adapter's) and
UniversalSignalRow (LatestResultRepository's own storage-boundary shape,
see strategy_runtime/persistence.py's own docstring for why) right here
at the repository call site -- callers of get_state()/refresh() never see
UniversalSignalRow at all.
"""

from __future__ import annotations

from collections.abc import Mapping

from market_data import CapabilityFulfillmentService
from strategy_runtime.clock import Clock
from strategy_runtime.execution import ExecutionStatus, run_strategies
from strategy_runtime.persistence import LatestResultRepository, UniversalSignalRow
from strategy_runtime.registry import StrategyRegistry
from strategy_runtime.result import UniversalScreeningResult


def get_state(
    repository: LatestResultRepository,
    *,
    strategy_id: str | None = None,
    symbol: str | None = None,
) -> tuple[UniversalScreeningResult, ...]:
    if strategy_id is not None and symbol is not None:
        row = repository.get_one(strategy_id, symbol)
        return (row.to_result(),) if row is not None else ()
    if strategy_id is not None:
        return tuple(row.to_result() for row in repository.get_for_signal(strategy_id))
    return tuple(row.to_result() for row in repository.get_all())


def refresh(
    registry: StrategyRegistry[UniversalScreeningResult],
    repository: LatestResultRepository,
    clock: Clock,
    *,
    strategy_id: str,
    symbol: str,
    fulfillment_by_subject: Mapping[str, CapabilityFulfillmentService],
) -> UniversalScreeningResult:
    """Recompute exactly one strategy against exactly one subject via the
    existing migrated adapters, then persist and return the new state --
    never a whole-universe or whole-strategy-set refresh.
    """
    (execution_result,) = run_strategies(
        registry,
        clock,
        subjects=(symbol,),
        strategy_ids=(strategy_id,),
        fulfillment_by_subject=fulfillment_by_subject,
    )
    if (
        execution_result.status is ExecutionStatus.ADAPTER_EXCEPTION
        or execution_result.result is None
    ):
        raise RuntimeError(
            f"refresh({strategy_id!r}, {symbol!r}) failed unexpectedly: "
            f"{execution_result.error_detail}"
        )
    repository.upsert(UniversalSignalRow.from_result(execution_result.result))
    return execution_result.result
