"""Strategy execution context (SPRINT-009/EPIC-1).

What a strategy adapter receives to evaluate one subject: its own
contract, which subject, a clock, and the run identity -- runtime/
evaluation concerns only.

``fulfillment`` (EPIC-3's own Shared Data Planning extension) is removed
as of SPRINT-014 S14-PR-05A (Architect checkpoint: twelfth review, item
1 -- "remove acquisition from RuntimeContext ... do not replace it with a
generic data, services, resources, or similar escape hatch"). Acquisition
is now the strategy-owned adapter's own concern, bound by closure at
registry-construction time (strategy_runtime/adapters/*.py), never carried
on this context: a strategy adapter that needs shared market data receives
it because its own factory function closed over a CapabilityFulfiller
(raw or PlanBackedFulfillment) when it was built, not because it reads a
field here.
"""

from __future__ import annotations

from dataclasses import dataclass

from strategy_runtime.clock import Clock
from strategy_runtime.contract import StrategyContract
from strategy_runtime.historical_evidence import HistoricalSkewRepository


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    contract: StrategyContract
    subject: str
    clock: Clock
    run_id: str
    # SPRINT-013 S13-04D: None for a strategy contract that never consumes
    # historical evidence, or when a caller runs strategies without it at
    # all.
    historical_skew_repository: HistoricalSkewRepository | None = None
