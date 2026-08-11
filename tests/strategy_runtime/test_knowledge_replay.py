"""S14R M3 provider-free replay contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from analytics.features import DerivedFactSet
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
from strategy_runtime.registry import StrategyAdapter
from strategy_runtime.replay import StrategyKnowledgeReplayRecord, replay_strategy_knowledge
from strategy_runtime.result import EvaluationState, RowType, UniversalScreeningResult

NOW = datetime(2026, 8, 11, 20, tzinfo=UTC)


@dataclass(frozen=True)
class _Clock:
    def now(self) -> datetime:
        return NOW


def _contract() -> StrategyContract:
    return StrategyContract(
        "replay-test",
        "1.0.0",
        "test",
        "provider-free replay test strategy",
        (DataRequirement(RequirementCategory.CUSTOM, identifier="knowledge"),),
        NO_LIFECYCLE,
        StructureKind.NONE,
        (OutputKind.METRICS,),
    )


def test_replay_uses_read_only_knowledge_and_is_deterministic() -> None:
    contract = _contract()
    knowledge = ReadOnlyStrategyInput(
        "snapshot-1", "digest-1", NOW, (), DerivedFactSet(()), "payload"
    )
    builds = 0

    def build_adapter(
        by_subject: Mapping[str, ReadOnlyStrategyInput[str]],
    ) -> StrategyAdapter[UniversalScreeningResult]:
        nonlocal builds
        builds += 1

        def adapter(context: RuntimeContext) -> UniversalScreeningResult:
            item = by_subject[context.subject]
            return UniversalScreeningResult(
                contract.strategy_id,
                contract.version,
                context.subject,
                "observation-1",
                None,
                RowType.RESULT,
                "PASS",
                EvaluationState.PASS,
                None,
                None,
                None,
                {},
                {},
                (),
                (),
                (f"snapshot_digest:{item.snapshot_digest}",),
                item.effective_time,
            )

        return adapter

    context = RuntimeContext(contract, "AAPL", _Clock(), "replay-run")
    record = StrategyKnowledgeReplayRecord(contract.strategy_id, "AAPL", knowledge)
    first = replay_strategy_knowledge(record, build_adapter, context)
    second = replay_strategy_knowledge(record, build_adapter, context)

    assert first == second
    assert first.provenance == ("snapshot_digest:digest-1",)
    assert builds == 2
