# Adding a strategy to the Universal Strategy Runtime

SPRINT-009R/EPIC-R4. Per this sprint's own `definition_of_done`, adding a strategy requires
exactly four steps, and none of them touch runtime orchestration, persistence, APIs, planners,
or lifecycle infrastructure:

1. Define a `StrategyContract`.
2. Declare its runtime capabilities.
3. Implement evaluation logic.
4. Register the strategy.

This is true today without any further platform work -- `strategy_runtime/adapters/` already
demonstrates it for three production strategies (`forward_factor`, `skew_momentum_vertical`,
`earnings_calendar`), each in its own module, none of which required a change to
`strategy_runtime/execution.py`, `strategy_runtime/service.py`, or any Postgres integration.
This guide is the walkthrough for a new one.

## 1. Define a `StrategyContract`

```python
from domain import MarketCapability
from strategy_runtime import (
    NO_LIFECYCLE,
    DataRequirement,
    OutputKind,
    RequirementCategory,
    StrategyCapability,
    StrategyContract,
    StructureKind,
)

MY_STRATEGY_CONTRACT = StrategyContract(
    strategy_id="my_strategy",
    version="1.0.0",
    category="options_volatility",  # a short, free-text grouping label
    description="One sentence describing this strategy's own investment thesis.",
    requirements=(
        DataRequirement(
            RequirementCategory.MARKET_DATA, capabilities=(MarketCapability.REAL_TIME_QUOTE_V1,)
        ),
    ),
    lifecycle=NO_LIFECYCLE,  # or a LifecycleDeclaration -- see step 2
    structure=StructureKind.NONE,  # or VERTICAL/CALENDAR/CUSTOM for an option structure
    outputs=(OutputKind.METRICS,),  # every namespace this strategy actually populates
)
```

`StrategyContract.__post_init__` validates this immediately and raises `StrategyContractError`
with a specific, actionable message for anything inconsistent -- there is no separate contract
linter to run first.

## 2. Declare its runtime capabilities

Only declare a `StrategyCapability` your contract's other fields actually back -- see
`strategy_runtime/contract.py`'s own `_check_capability_consistency()` for the exact pairing
each one requires (e.g. `StrategyCapability.ECONOMICS` requires `OutputKind.ECONOMICS` in
`outputs`; `StrategyCapability.OPTION_STRUCTURES` requires a non-`NONE` `structure`).
Omitting `capabilities` entirely is always valid -- it is additive and opt-in, not a second
mandatory encoding of the same information.

If your strategy tracks a persistent opportunity across repeated observations (SPRINT-009R/
EPIC-R3), declare a `LifecycleDeclaration` instead of `NO_LIFECYCLE`, add
`OutputKind.LIFECYCLE` to `outputs`, and add `StrategyCapability.LIFECYCLE` to `capabilities`.

## 3. Implement evaluation logic

An adapter is one function: `RuntimeContext -> UniversalScreeningResult` (or any other TResult,
for a registry not built around the universal envelope). It owns only your strategy's own
financial judgment -- orchestration, retries, and error isolation are the runtime's job
(`strategy_runtime.execution.run_strategies()`), never the adapter's own.

```python
from strategy_runtime import RuntimeContext, UniversalScreeningResult
from strategy_runtime.result import EvaluationState, RowType, compute_observation_id


def my_strategy_adapter(context: RuntimeContext) -> UniversalScreeningResult:
    if context.fulfillment is None:
        raise RuntimeError("my_strategy requires shared market data access")
    # ... your own evaluation logic against context.fulfillment ...
    return UniversalScreeningResult(
        strategy_id=context.contract.strategy_id,
        strategy_version=context.contract.version,
        symbol=context.subject,
        observation_id=compute_observation_id(
            context.run_id, context.contract.strategy_id, context.subject
        ),
        opportunity_id=None,
        row_type=RowType.RESULT,
        verdict="pass",
        evaluation_state=EvaluationState.PASS,
        lifecycle_stage=None,
        recommendation_state=None,
        data_quality=None,
        metrics={},  # populate with strategy_runtime.values.TypedValue entries
        economics={},
        blockers=(),
        warnings=(),
        provenance=(),
        observed_at=context.clock.now(),
    )
```

An unhandled exception here is caught by `run_strategies()` and reported as
`ExecutionStatus.ADAPTER_EXCEPTION` -- one strategy's exception never prevents any other
strategy from executing. A result that contradicts its own contract (e.g. declares
`OutputKind.METRICS` but returns an empty `metrics` dict) is caught the same way, via
`strategy_runtime.validation.validate_result()` (SPRINT-009R/EPIC-R1).

If you are migrating an existing strategy that already runs through `screening/`, reuse
`strategy_runtime.adapters._screening_bridge.translate_screening_result()` rather than writing
a second translation -- see `strategy_runtime/adapters/forward_factor.py` for the pattern every
migrated strategy already follows.

## 4. Register the strategy

```python
from strategy_runtime import register

MY_REGISTRY = register(
    (MY_STRATEGY_CONTRACT, my_strategy_adapter),
    # ...alongside any other contract/adapter pairs...
)
```

`register()` (SPRINT-009R/EPIC-R4) is a thin ergonomic wrapper over `StrategyRegistry`'s own
constructor, which remains the one place a duplicate `strategy_id` is caught
(`DuplicateStrategyRegistrationError`).

## Diagnostics

After registering, `strategy_runtime.describe_registry(MY_REGISTRY)` prints one human-readable
line per registered strategy (id, version, category, requirements, lifecycle, structure,
outputs, capabilities) -- use it to sanity-check a new strategy's own contract at a glance,
alongside every other strategy already running. `strategy_runtime.describe_contract(contract)`
does the same for one contract in isolation.

## What you will never need to touch

- `strategy_runtime/execution.py` -- `run_strategies()` already executes any registered
  strategy generically; it contains no strategy-named conditional and never will.
- `strategy_runtime/service.py` -- `refresh()`/`get_state()`/`record_opportunity_observation()`
  already work against any `StrategyRegistry[UniversalScreeningResult]`.
- Persistence (`strategy_runtime/persistence.py` and its Postgres implementations) -- shaped
  around `UniversalScreeningResult`/`OpportunityObservation`, not any one strategy_id.
- The Agent Data API routes (`asa/api/`) -- reading from a registry is a separate, deliberately
  deferred wiring step (SPRINT-009R/EPIC-R5's own scope), not something a new strategy causes
  by existing.
