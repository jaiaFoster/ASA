"""Shared screening execution and state service (API-001, SPRINT-008).

The single execution graph both screening/cli.py and backend's HTTP API
call -- neither reimplements or duplicates strategy-selection or execution
logic. get_state() only ever reads through an injected repository (never
triggers a provider request, matching this sprint's own architecture
principle); refresh() calls the existing, unmodified
run_screening()/build_live_adapters() machinery for exactly one requested
strategy against one symbol, then persists the result through the same
injected repository -- bounded, narrow, no whole-universe execution.

The repository is always caller-supplied (dependency injection, the same
pattern market_data/ already uses to separate pure interfaces from impure
implementations) -- this module never constructs one itself, so it never
needs a database driver as a dependency.
"""

from __future__ import annotations

from market_data import CapabilityFulfillmentService
from screening.clock import Clock
from screening.live_adapters import build_live_adapters
from screening.registry import ScreeningRegistry
from screening.runner import run_screening
from screening.state import ScreeningStateRecord, ScreeningStateRepository


def get_state(
    repository: ScreeningStateRepository,
    *,
    signal_id: str | None = None,
    symbol: str | None = None,
) -> tuple[ScreeningStateRecord, ...]:
    """Read current screening state -- never computes, never acquires live
    data, purely a repository read.
    """
    if signal_id is not None and symbol is not None:
        record = repository.get_one(signal_id, symbol)
        return (record,) if record is not None else ()
    if signal_id is not None:
        return repository.get_for_signal(signal_id)
    return repository.get_all()


def refresh(
    repository: ScreeningStateRepository,
    registry: ScreeningRegistry,
    fulfillment: CapabilityFulfillmentService,
    clock: Clock,
    *,
    signal_id: str,
    symbol: str,
) -> ScreeningStateRecord:
    """Recompute exactly one strategy against exactly one symbol via the
    existing live adapters, then persist and return the new state -- never
    a whole-universe or whole-strategy-set refresh. signal_id maps directly
    onto run_screening()'s own strategy_ids parameter -- same identifier,
    screening/'s own established name for it, unchanged.
    """
    adapters = build_live_adapters(symbol, fulfillment)
    (result,) = run_screening(registry, adapters, clock, strategy_ids=(signal_id,))
    record = ScreeningStateRecord.from_result(result, symbol=symbol)
    repository.upsert(record)
    return record
