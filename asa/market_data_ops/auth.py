"""Bearer-token auth and application-level bounding for the operations endpoint."""

from __future__ import annotations

import _thread
import hmac
import time
from dataclasses import dataclass, field


def token_matches(presented: str, configured: str) -> bool:
    """Timing-safe comparison; never logs either value."""
    return hmac.compare_digest(presented.encode("utf-8"), configured.encode("utf-8"))


@dataclass
class OperationsRunLimiter:
    """Bounds runs to max_runs_per_hour with concurrency capped at one in-process run.

    max_runs_per_hour=None disables the hourly count check (still one concurrent
    run at a time); intended for the development environment only.
    """

    max_runs_per_hour: int | None = 50
    _lock: _thread.LockType = field(default_factory=_thread.allocate_lock, repr=False)
    _run_timestamps: list[float] = field(default_factory=list, repr=False)
    _running: bool = field(default=False, repr=False)

    def try_acquire(self) -> bool:
        now = time.monotonic()
        self._lock.acquire()
        try:
            if self._running:
                return False
            if self.max_runs_per_hour is not None:
                self._run_timestamps = [t for t in self._run_timestamps if now - t < 3600]
                if len(self._run_timestamps) >= self.max_runs_per_hour:
                    return False
                self._run_timestamps.append(now)
            self._running = True
            return True
        finally:
            self._lock.release()

    def release(self) -> None:
        self._lock.acquire()
        try:
            self._running = False
        finally:
            self._lock.release()
