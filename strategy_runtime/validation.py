"""Contract-derived runtime validation (SPRINT-009R/EPIC-R1).

"Declared outputs emitted" -- one of EPIC-R1's five runtime_validation
entries -- can only be checked against one actual execution, not against
a StrategyContract in isolation; the other four (requirements fulfilled,
lifecycle/structure/capability consistency) are either enforced
structurally in StrategyContract.__post_init__ (the three that only ever
depend on the contract's own fields) or already enforced by each
adapter's own established self-check convention -- ``if
context.fulfillment is None: raise ...`` appears in every
capability-backed adapter today (strategy_runtime.adapters.*), matching
strategy_runtime.context's own documented design: only a strategy's own
contract knows whether shared data access is truly required for a
correctly-run pipeline, so "requirements fulfilled" is deliberately left
to the adapter, not duplicated here as a second, contradictory runtime
gate (run_strategies() must remain fully usable without shared data
planning at all -- see strategy_runtime.context.RuntimeContext's own
docstring).

This module is strategy_runtime.execution's own post-execution check: it
reads nothing but a contract and that one execution's own output,
matching this sprint's own contract_is_truth principle -- no strategy_id
conditional appears anywhere in this file.
"""

from __future__ import annotations

from strategy_runtime.contract import OutputKind, StrategyContract
from strategy_runtime.errors import StrategyContractViolationError
from strategy_runtime.result import SUCCESS_EVALUATION_STATES, UniversalScreeningResult


def validate_result(contract: StrategyContract, result: object) -> None:
    """"Declared outputs emitted" -- checked after the adapter returns.
    Only applies to results shaped as a UniversalScreeningResult (EPIC-6's
    envelope); a strategy_runtime caller using a different TResult opts
    out of this check entirely, since there is then no fixed shape to
    check declared outputs against.
    """
    if not isinstance(result, UniversalScreeningResult):
        return
    if result.evaluation_state not in SUCCESS_EVALUATION_STATES:
        # A non-success evaluation (missing_data, malformed_output, adapter_exception) never
        # populated its declared outputs in the first place -- that is not a contract
        # violation, it is the strategy correctly reporting it could not evaluate.
        return
    if OutputKind.METRICS in contract.outputs and not result.metrics:
        raise StrategyContractViolationError(
            f"strategy {contract.strategy_id!r} declares OutputKind.METRICS but the result's "
            "metrics namespace is empty"
        )
    # OutputKind.ECONOMICS is deliberately not enforced here yet: every strategy migrated in
    # SPRINT-009/EPIC-7 declares it but strategy_runtime.adapters._screening_bridge always
    # emits economics={} today (the executive_summary's own "strategy-native information is
    # not yet fully represented" gap) -- populating it with typed values is EPIC-R2's job.
    # Enforcing this check before EPIC-R2 lands would fail every currently-shipped strategy.
    if OutputKind.LIFECYCLE in contract.outputs and (
        result.opportunity_id is None or result.lifecycle_stage is None
    ):
        raise StrategyContractViolationError(
            f"strategy {contract.strategy_id!r} declares OutputKind.LIFECYCLE but the result "
            "carries no opportunity_id/lifecycle_stage"
        )
    if (
        OutputKind.RECOMMENDATION_SUPPORT in contract.outputs
        and result.recommendation_state is None
    ):
        raise StrategyContractViolationError(
            f"strategy {contract.strategy_id!r} declares OutputKind.RECOMMENDATION_SUPPORT but "
            "the result carries no recommendation_state"
        )
