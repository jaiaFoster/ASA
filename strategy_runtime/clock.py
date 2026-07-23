"""Injected clock port for strategy_runtime (SPRINT-009/EPIC-1).

A local, minimal Protocol -- deliberately not imported from screening,
market_data, or any other bounded context, so this package stays decoupled
from every consumer, matching the pattern screening/clock.py already
established for its own bounded context.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...
