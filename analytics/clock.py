"""Injected clock port for the derived analytics framework (ANALYTICS-001).

A local, minimal Protocol -- deliberately not imported from screening,
market_data, or any other bounded context, so the analytics framework
stays independently reusable and decoupled.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...
