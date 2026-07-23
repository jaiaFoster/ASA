"""Universal Strategy Runtime (SPRINT-009).

Root-level, deployable-application-independent infrastructure -- a plain
sibling of screening/, market_data/, and domain/, following the same
one-directional dependency rule asa/'s own consolidation established
(ARCH-MONOREPO-001): this package and everything under it may be imported
by asa/, but must never import asa/ itself
(tests/architecture/test_asa_dependency_direction.py enforces this
automatically for every root-level package, this one included).

EPIC-2 (Declarative Strategy Contract) lives in strategy_runtime.contract:
the one shape every strategy declares itself through. EPIC-1 (Universal
Strategy Runtime) builds on it: strategy_runtime.registry (registration and
discovery), strategy_runtime.context (what an adapter receives), and
strategy_runtime.execution (the one execution pipeline every registered
strategy runs through, with error isolation, diagnostics, and metrics) --
together, the one place a strategy executes without a strategy-specific
conditional anywhere in this package. EPIC-6 (Universal Screening Result)
lives in strategy_runtime.result: the one canonical result envelope every
strategy's adapter returns. EPIC-3 (Shared Data Planning) lives in
strategy_runtime.market_data_planning: one market_data.
CapabilityFulfillmentService per subject, shared by every strategy that
evaluates it within a run, threaded through RuntimeContext.fulfillment by
run_strategies()'s own optional fulfillment_by_subject parameter.
"""

from __future__ import annotations

from strategy_runtime.context import RuntimeContext
from strategy_runtime.contract import (
    NO_LIFECYCLE,
    DataRequirement,
    LifecycleDeclaration,
    LifecycleModel,
    OutputKind,
    RequirementCategory,
    StrategyContract,
    StructureKind,
)
from strategy_runtime.errors import (
    DuplicateStrategyRegistrationError,
    StrategyContractError,
    UnknownStrategyIdError,
)
from strategy_runtime.execution import (
    ExecutionStatus,
    RuntimeExecutionSummary,
    StrategyExecutionResult,
    run_strategies,
)
from strategy_runtime.market_data_planning import (
    SubjectMarketDataAccess,
    build_shared_market_data_access,
)
from strategy_runtime.registry import StrategyAdapter, StrategyRegistry
from strategy_runtime.result import (
    SUCCESS_EVALUATION_STATES,
    EvaluationState,
    RowType,
    UniversalScreeningResult,
    compute_observation_id,
)

__all__ = [
    "NO_LIFECYCLE",
    "SUCCESS_EVALUATION_STATES",
    "DataRequirement",
    "DuplicateStrategyRegistrationError",
    "EvaluationState",
    "ExecutionStatus",
    "LifecycleDeclaration",
    "LifecycleModel",
    "OutputKind",
    "RequirementCategory",
    "RowType",
    "RuntimeContext",
    "RuntimeExecutionSummary",
    "StrategyAdapter",
    "StrategyContract",
    "StrategyContractError",
    "StrategyExecutionResult",
    "StrategyRegistry",
    "StructureKind",
    "SubjectMarketDataAccess",
    "UniversalScreeningResult",
    "UnknownStrategyIdError",
    "build_shared_market_data_access",
    "compute_observation_id",
    "run_strategies",
]
