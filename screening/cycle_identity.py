"""Screening-cycle and pair-evaluation identity (SPRINT-013 S13-02).

screening owns minting this identity; it does not own persistence (that is
asa/integrations), the attempt contract (market_data), or query surfaces
(asa/market_data_ops). A cycle spans one scheduled-refresh invocation across
every (signal_id, symbol) pair; a pair evaluation is one (signal_id, symbol)
iteration within that cycle.
"""

from __future__ import annotations

from datetime import datetime

from domain.values import require_tz_aware


def new_screening_cycle_id(now: datetime) -> str:
    """Identity for one scheduled-refresh invocation, derived from its
    caller-supplied start time rather than uuid/random -- screening/'s own
    architecture boundary (SCREEN-002, test_screening_boundaries.py)
    forbids non-deterministic sources so cycles stay replayable.
    """
    require_tz_aware(now, "new_screening_cycle_id", "now")
    return f"cycle_{now.strftime('%Y%m%dT%H%M%S%f')}Z"


def pair_evaluation_id(screening_cycle_id: str, signal_id: str, symbol: str) -> str:
    """Deterministic identity for one (signal_id, symbol) evaluation within
    a cycle -- a pure composite key, already unique per cycle (each pair is
    evaluated at most once per cycle) and reproducible for tests/replay.
    """
    if not screening_cycle_id or not signal_id or not symbol:
        raise ValueError("pair_evaluation_id requires non-empty cycle, signal, and symbol")
    return f"{screening_cycle_id}:{signal_id}:{symbol}"
