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
run_strategies()'s own optional fulfillment_by_subject parameter. EPIC-4
(Universal Options Framework) lives in strategy_runtime.options: domain's
own already-validated OptionLeg/OptionStructure adopted directly as the
canonical option package representation, analytics.expiration_selection's
own already-generalized expiration-pairing re-exported for discoverability,
and liquidity/debit calculations ported from strategies/
stonk_components.py's own graph components to plain functions. EPIC-5
(Universal Opportunity Model) lives in strategy_runtime.lifecycle:
compute_opportunity_id() for stable cross-observation identity,
OpportunityObservation/OpportunityHistory for an opportunity's evolution,
RecommendedAction as the vocabulary UniversalScreeningResult.
recommendation_state holds, and validate_lifecycle_stage() as the one
guardrail keeping the engine strategy-agnostic (a reported stage must be
one the strategy's own contract actually declared). EPIC-8 (Persistence &
History) lives in strategy_runtime.persistence: two pure Protocols
(LatestResultRepository, ObservationHistoryRepository), no infrastructure
imports -- a concrete implementation is deferred to whichever ticket
first wires a live repository into a live adapter, matching
screening/state.py's own established convention that this package never
imports a database driver itself. EPIC-7 (Strategy Migration) lives in
strategy_runtime.adapters: one module per migrated strategy
(forward_factor, skew_momentum_vertical, earnings_calendar), each
declaring its own StrategyContract and a StrategyAdapter that reuses the
existing, unmodified execution graph (screening.live_adapters,
strategies/stonk_manifests.py) and translates its output into
UniversalScreeningResult via the shared _screening_bridge module. Not
re-exported here -- imported directly from strategy_runtime.adapters.*,
since registering them with a live registry is EPIC-9's own job.
SPRINT-013 S13-04 (Shared Historical Evidence Foundation) lives in
strategy_runtime.historical_evidence: HistoricalSkewRepository, a pure
Protocol matching strategy_runtime.persistence's own no-infrastructure-
imports convention exactly, plus record_prospective_skew_observation(),
the one entry point that may ever append to it -- reusable across any
future historical fact family, not owned by skew_momentum. Not
re-exported here, for the same reason strategy_runtime.persistence's own
Protocols are not: a concrete implementation belongs to asa/integrations.
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
    StrategyCapability,
    StrategyContract,
    StructureKind,
)
from strategy_runtime.errors import (
    DuplicateStrategyRegistrationError,
    StrategyContractError,
    StrategyContractViolationError,
    UnknownStrategyIdError,
)
from strategy_runtime.executable_structures import (
    ExecutableStructureAssessment,
    ExecutableStructureStatus,
    ModeledEntryEconomics,
    ResolvedOptionLeg,
    SelectionDiagnostic,
)
from strategy_runtime.execution import (
    ExecutionStatus,
    RuntimeExecutionSummary,
    StrategyExecutionResult,
    run_strategies,
)
from strategy_runtime.market_data_planning import (
    SubjectMarketDataAccess,
    build_provider_rolling_window_tracker,
    build_shared_market_data_access,
    declared_rolling_window_policies,
)
from strategy_runtime.modeled_pnl import (
    MODEL_VERSION,
    ModeledPnLAssumptions,
    ModeledPnLPoint,
    ModeledPnLSurface,
    ModeledPnLUnknown,
    model_front_expiration_pnl,
)
from strategy_runtime.option_structure_resolver import (
    OptionLegIntent,
    OptionStructureIntent,
    resolve_option_structure,
)
from strategy_runtime.registry import (
    StrategyAdapter,
    StrategyRegistry,
    describe_contract,
    describe_registry,
    register,
)
from strategy_runtime.result import (
    SUCCESS_EVALUATION_STATES,
    EvaluationState,
    RowType,
    UniversalScreeningResult,
    compute_observation_id,
)
from strategy_runtime.validation import validate_result
from strategy_runtime.values import TypedValue, ValueType

__all__ = [
    "NO_LIFECYCLE",
    "SUCCESS_EVALUATION_STATES",
    "DataRequirement",
    "DuplicateStrategyRegistrationError",
    "EvaluationState",
    "ExecutionStatus",
    "ExecutableStructureAssessment",
    "ExecutableStructureStatus",
    "LifecycleDeclaration",
    "LifecycleModel",
    "MODEL_VERSION",
    "ModeledEntryEconomics",
    "ModeledPnLAssumptions",
    "ModeledPnLPoint",
    "ModeledPnLSurface",
    "ModeledPnLUnknown",
    "OptionLegIntent",
    "OptionStructureIntent",
    "OutputKind",
    "RequirementCategory",
    "ResolvedOptionLeg",
    "RowType",
    "RuntimeContext",
    "RuntimeExecutionSummary",
    "StrategyAdapter",
    "StrategyCapability",
    "StrategyContract",
    "StrategyContractError",
    "StrategyContractViolationError",
    "StrategyExecutionResult",
    "StrategyRegistry",
    "StructureKind",
    "SelectionDiagnostic",
    "SubjectMarketDataAccess",
    "TypedValue",
    "UniversalScreeningResult",
    "UnknownStrategyIdError",
    "ValueType",
    "build_provider_rolling_window_tracker",
    "build_shared_market_data_access",
    "compute_observation_id",
    "declared_rolling_window_policies",
    "describe_contract",
    "describe_registry",
    "register",
    "model_front_expiration_pnl",
    "resolve_option_structure",
    "run_strategies",
    "validate_result",
]
