from __future__ import annotations

from asa.market_data_ops.auth import OperationsRunLimiter


def test_default_hourly_cap_is_fifty() -> None:
    assert OperationsRunLimiter().max_runs_per_hour == 50


def test_hourly_cap_is_enforced_when_set() -> None:
    limiter = OperationsRunLimiter(max_runs_per_hour=2)
    assert limiter.try_acquire() is True
    limiter.release()
    assert limiter.try_acquire() is True
    limiter.release()
    assert limiter.try_acquire() is False


def test_none_disables_the_hourly_cap() -> None:
    limiter = OperationsRunLimiter(max_runs_per_hour=None)
    for _ in range(60):
        assert limiter.try_acquire() is True
        limiter.release()


def test_none_still_enforces_single_concurrency() -> None:
    limiter = OperationsRunLimiter(max_runs_per_hour=None)
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False
    limiter.release()
    assert limiter.try_acquire() is True
