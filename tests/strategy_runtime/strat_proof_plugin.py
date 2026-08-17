"""Test-only strategy plug-in used by STRAT-PROOF-001 acceptance."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType

from analytics.derived_facts import CROSS_SECTIONAL_MOMENTUM, REALIZED_VOLATILITY
from strategy_runtime.context import RuntimeContext
from strategy_runtime.contract import (
    NO_LIFECYCLE,
    DataRequirement,
    OutputKind,
    RequirementCategory,
    StrategyContract,
    StructureKind,
)
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.registry import StrategyAdapter, StrategyRegistry, register
from strategy_runtime.result import (
    EvaluationState,
    RowType,
    UniversalScreeningResult,
    compute_observation_id,
)
from strategy_runtime.values import TypedValue

STRATEGY_ID = "strat_proof_synthetic"
CONTRACT = StrategyContract(
    STRATEGY_ID,
    "1.0.0-test",
    "architecture-proof",
    "test-only consumer of existing immutable local and cross-sectional facts",
    (
        DataRequirement(
            RequirementCategory.CUSTOM,
            identifier="existing_subject_local_and_cross_sectional_facts",
        ),
    ),
    NO_LIFECYCLE,
    StructureKind.NONE,
    (OutputKind.METRICS,),
)


def _fact_value(knowledge: ReadOnlyStrategyInput[object], feature_id: str) -> Decimal:
    fact = next(
        item
        for item in knowledge.derived_facts.facts
        if item.derived_fact_id.startswith(f"{feature_id}:")
    )
    if not isinstance(fact.value, Decimal):
        raise TypeError(f"{feature_id} must be decimal")
    return fact.value


def build_adapter(
    knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[object]],
) -> StrategyAdapter[UniversalScreeningResult]:
    """Bind immutable pre-materialized knowledge to strategy-owned thesis logic."""

    frozen = MappingProxyType(dict(knowledge_by_subject))

    def evaluate(context: RuntimeContext) -> UniversalScreeningResult:
        knowledge = frozen[context.subject]
        local_value = _fact_value(knowledge, REALIZED_VOLATILITY)
        cross_value = _fact_value(knowledge, CROSS_SECTIONAL_MOMENTUM)
        verdict = (
            "PASS"
            if local_value < Decimal("0.50") and cross_value >= Decimal("0.50")
            else "WATCH"
        )
        return UniversalScreeningResult(
            strategy_id=STRATEGY_ID,
            strategy_version=CONTRACT.version,
            symbol=context.subject,
            observation_id=compute_observation_id(context.run_id, STRATEGY_ID, context.subject),
            opportunity_id=None,
            row_type=RowType.RESULT,
            verdict=verdict,
            evaluation_state=EvaluationState.PASS,
            lifecycle_stage=None,
            recommendation_state=None,
            data_quality="complete",
            metrics={
                "local.realized_volatility": TypedValue.of_decimal(local_value),
                "cross.cross_sectional_percentile": TypedValue.of_decimal(cross_value),
            },
            economics={},
            blockers=(),
            warnings=(),
            provenance=tuple(
                sorted(item.derived_fact_id for item in knowledge.derived_facts.facts)
            ),
            observed_at=knowledge.effective_time,
        )

    return evaluate


def register_test_strategy(
    knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[object]],
) -> StrategyRegistry[UniversalScreeningResult]:
    """Use the normal immutable registry; no test-only executor exists."""

    return register((CONTRACT, build_adapter(knowledge_by_subject)))


class FrozenClock:
    def __init__(self, value: datetime) -> None:
        self._value = value

    def now(self) -> datetime:
        return self._value
