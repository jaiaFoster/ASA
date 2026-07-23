"""Strategy execution context (SPRINT-009/EPIC-1, extended by EPIC-3).

What a strategy adapter receives to evaluate one subject. ``fulfillment``
is EPIC-3's own extension (Shared Data Planning): the
market_data.CapabilityFulfillmentService shared by every strategy in the
same run that evaluates the same subject, so an identical CapabilityRequest
two strategies both make is only ever fulfilled once
(strategy_runtime.market_data_planning). None for a strategy contract
that declares no market_data/option_data/earnings requirement, or when a
caller runs strategies without shared data planning at all (EPIC-1's own
run_strategies() remains fully usable without it) -- a strategy that
needs it should assert it is not None itself, since only that strategy's
own contract can know it always will be for a correctly-run pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass

from market_data import CapabilityFulfillmentService
from strategy_runtime.clock import Clock
from strategy_runtime.contract import StrategyContract


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    contract: StrategyContract
    subject: str
    clock: Clock
    run_id: str
    fulfillment: CapabilityFulfillmentService | None = None
