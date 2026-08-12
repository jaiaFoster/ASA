"""Provider-free replay of already-materialized strategy knowledge."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Generic

from strategy_runtime.context import RuntimeContext
from strategy_runtime.knowledge import ReadOnlyStrategyInput, TPayload
from strategy_runtime.registry import StrategyAdapter
from strategy_runtime.result import UniversalScreeningResult
from strategy_runtime.subject_preparation import BuildShadowAdapter


@dataclass(frozen=True, slots=True)
class StrategyKnowledgeReplayRecord(Generic[TPayload]):  # noqa: UP046
    strategy_id: str
    subject: str
    knowledge: ReadOnlyStrategyInput[TPayload]


def replay_strategy_knowledge(
    record: StrategyKnowledgeReplayRecord[TPayload],
    build_adapter: BuildShadowAdapter[TPayload],
    context: RuntimeContext,
) -> UniversalScreeningResult:
    """Evaluate immutable knowledge only; no acquisition input exists."""
    if context.contract.strategy_id != record.strategy_id:
        raise ValueError("replay strategy contract does not match record")
    if context.subject != record.subject:
        raise ValueError("replay subject does not match record")
    knowledge: Mapping[str, ReadOnlyStrategyInput[TPayload]] = {
        record.subject: record.knowledge
    }
    adapter: StrategyAdapter[UniversalScreeningResult] = build_adapter(knowledge)
    return adapter(context)
