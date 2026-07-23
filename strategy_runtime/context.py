"""Strategy execution context (SPRINT-009/EPIC-1).

What a strategy adapter receives to evaluate one subject. Deliberately
minimal today: EPIC-3 (Shared Data Planning) will extend this with
acquired-data access once it exists, by adding a field here, not by
changing an adapter's own signature -- an adapter always receives "the
context" as a whole, never its fields positionally, so it gains new
capability without needing to be rewritten when the context grows.
"""

from __future__ import annotations

from dataclasses import dataclass

from strategy_runtime.clock import Clock
from strategy_runtime.contract import StrategyContract


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    contract: StrategyContract
    subject: str
    clock: Clock
    run_id: str
