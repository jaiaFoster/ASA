"""Generic append-only storage and provider-free replay for decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Protocol, TypeVar

TDecision = TypeVar("TDecision")


class DecisionRecord(Protocol):
    @property
    def decision_id(self) -> str: ...


class DecisionLedger(Protocol[TDecision]):
    def append(self, decision: TDecision) -> None: ...
    def get(self, decision_id: str) -> TDecision | None: ...
    def all(self) -> tuple[TDecision, ...]: ...


@dataclass(slots=True)
class InMemoryDecisionLedger(Generic[TDecision]):  # noqa: UP046
    _records: dict[str, TDecision] = field(default_factory=dict)

    def append(self, decision: TDecision) -> None:
        decision_id = getattr(decision, "decision_id", None)
        if not isinstance(decision_id, str) or not decision_id:
            raise ValueError("decision must expose a normalized decision_id")
        existing = self._records.get(decision_id)
        if existing is not None and existing != decision:
            raise ValueError("immutable decision identity collision")
        self._records.setdefault(decision_id, decision)

    def get(self, decision_id: str) -> TDecision | None:
        return self._records.get(decision_id)

    def all(self) -> tuple[TDecision, ...]:
        return tuple(self._records[key] for key in sorted(self._records))


def replay_decision(  # noqa: UP047
    ledger: DecisionLedger[TDecision], decision_id: str
) -> TDecision:
    """Read the persisted immutable decision; no acquisition port exists."""
    decision = ledger.get(decision_id)
    if decision is None:
        raise KeyError(decision_id)
    return decision
