"""Generic provider-free execution seam for one sealed cross-subject cohort."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar

from strategy_runtime.knowledge import ReadOnlyStrategyInput

TPayload = TypeVar("TPayload")
TDecision = TypeVar("TDecision")


@dataclass(frozen=True, slots=True)
class SealedCohortKnowledge(Generic[TPayload]):  # noqa: UP046
    decision_time: datetime
    subjects: tuple[tuple[str, ReadOnlyStrategyInput[TPayload]], ...]

    def __post_init__(self) -> None:
        if self.decision_time.tzinfo is None or self.decision_time.utcoffset() is None:
            raise ValueError("cohort decision time must be timezone-aware")
        symbols = tuple(symbol for symbol, _ in self.subjects)
        if symbols != tuple(sorted(set(symbols))):
            raise ValueError("cohort subjects must be unique and sorted")
        if any(knowledge.effective_time != self.decision_time for _, knowledge in self.subjects):
            raise ValueError("cohort subjects must have one effective time")


def compose_cohort_knowledge(  # noqa: UP047
    knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[TPayload]],
    *,
    decision_time: datetime,
) -> SealedCohortKnowledge[TPayload]:
    """Collect already-prepared knowledge; never acquire or reinterpret it."""
    return SealedCohortKnowledge(
        decision_time,
        tuple((symbol, knowledge_by_subject[symbol]) for symbol in sorted(knowledge_by_subject)),
    )


def evaluate_cohort(  # noqa: UP047
    cohort: SealedCohortKnowledge[TPayload],
    interpreter: Callable[[SealedCohortKnowledge[TPayload]], TDecision],
) -> TDecision:
    """Dispatch immutable cohort knowledge to a strategy-owned thesis."""
    return interpreter(cohort)
