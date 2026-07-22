"""Injected clock port for the screening framework (SCREEN-002).

A local, minimal Protocol -- deliberately not imported from market_data or
any other bounded context, so the screening framework stays decoupled from
provider-facing infrastructure.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...
