from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from domain.values import DomainInvariantError
from market_data.config import ProviderEndpointEnvironment
from market_data.finnhub import finnhub_rolling_window_policy
from market_data.rolling_window import ProviderRollingWindowTracker, RollingWindowPolicy
from market_data.tradier import tradier_rolling_window_policy

START = datetime(2026, 7, 21, tzinfo=UTC)


@dataclass
class FakeClock:
    value: datetime = START

    def now(self) -> datetime:
        return self.value

    def advance(self, **kwargs) -> None:
        self.value += timedelta(**kwargs)


def policy(provider_id: str = "tradier", window_seconds: int = 60, window_limit: int = 2):
    return RollingWindowPolicy(provider_id, window_seconds, window_limit, "documented")


def test_policy_rejects_non_positive_fields() -> None:
    with pytest.raises(DomainInvariantError):
        RollingWindowPolicy("tradier", 0, 5, "documented")
    with pytest.raises(DomainInvariantError):
        RollingWindowPolicy("tradier", 60, 0, "documented")


def test_reserves_up_to_the_limit_within_the_window() -> None:
    clock = FakeClock()
    tracker = ProviderRollingWindowTracker((policy(),), clock)
    assert tracker.try_reserve("tradier") is True
    assert tracker.try_reserve("tradier") is True
    assert tracker.try_reserve("tradier") is False  # limit is 2


def test_genuinely_aggregates_microsecond_separated_requests() -> None:
    """The bug this fixes: RequestBudgetManager's old burst dict keyed by
    the exact authorization timestamp, so two requests one microsecond
    apart never collided under a real clock. A rolling window must catch
    this even without advancing the clock at all."""
    clock = FakeClock()
    tracker = ProviderRollingWindowTracker((policy(window_limit=1),), clock)
    assert tracker.try_reserve("tradier") is True
    # No time has passed at all -- still within the same window.
    assert tracker.try_reserve("tradier") is False


def test_window_expiry_restores_allowance_deterministically() -> None:
    clock = FakeClock()
    tracker = ProviderRollingWindowTracker((policy(window_seconds=60, window_limit=1),), clock)
    assert tracker.try_reserve("tradier") is True
    clock.advance(seconds=59)
    assert tracker.try_reserve("tradier") is False
    clock.advance(seconds=2)  # now 61s after the first reservation
    assert tracker.try_reserve("tradier") is True


def test_providers_have_independent_accounting() -> None:
    clock = FakeClock()
    tracker = ProviderRollingWindowTracker(
        (policy("tradier", window_limit=1), policy("finnhub", window_limit=1)), clock
    )
    assert tracker.try_reserve("tradier") is True
    assert tracker.try_reserve("tradier") is False
    assert tracker.try_reserve("finnhub") is True  # independent from tradier


def test_unconfigured_provider_is_never_limited() -> None:
    """This tracker adds protection; it never invents a limit for a
    provider with no declared/configured policy."""
    clock = FakeClock()
    tracker = ProviderRollingWindowTracker((policy("tradier"),), clock)
    for _ in range(50):
        assert tracker.try_reserve("alpha_vantage") is True


def test_reset_hint_can_only_shorten_never_lengthen_allowance() -> None:
    clock = FakeClock()
    tracker = ProviderRollingWindowTracker((policy(window_seconds=60, window_limit=5),), clock)
    tracker.apply_reset_hint("tradier", clock.now() + timedelta(seconds=120))
    assert tracker.try_reserve("tradier") is False  # blocked well before the window would expire

    clock.advance(seconds=200)  # past the reset hint
    assert tracker.try_reserve("tradier") is True


def test_reset_hint_does_not_shorten_below_a_later_earlier_hint() -> None:
    """A later, LOOSER hint must never override an earlier, TIGHTER one --
    only ever tighten further, never relax."""
    clock = FakeClock()
    tracker = ProviderRollingWindowTracker((policy(window_seconds=60, window_limit=5),), clock)
    tracker.apply_reset_hint("tradier", clock.now() + timedelta(seconds=120))
    tracker.apply_reset_hint("tradier", clock.now() + timedelta(seconds=10))  # looser, ignored
    clock.advance(seconds=15)
    assert tracker.try_reserve("tradier") is False  # still blocked under the tighter hint


def test_reset_hint_for_unconfigured_provider_is_ignored() -> None:
    clock = FakeClock()
    tracker = ProviderRollingWindowTracker((policy("tradier"),), clock)
    tracker.apply_reset_hint("alpha_vantage", clock.now() + timedelta(seconds=999))
    assert tracker.try_reserve("alpha_vantage") is True


# -- SPRINT-013 P0: declared-window expiry against each provider's own
# real, documented policy (not a synthetic one) -- proves the fix
# against the actual values production uses, not just an arbitrary
# window_seconds/window_limit pair.


def test_a_finnhub_reservation_expires_after_its_declared_second() -> None:
    policy = finnhub_rolling_window_policy()
    clock = FakeClock()
    tracker = ProviderRollingWindowTracker((policy,), clock)
    for _ in range(policy.window_limit):
        assert tracker.try_reserve("finnhub") is True
    assert tracker.try_reserve("finnhub") is False  # exactly at the declared per-second limit

    clock.advance(seconds=policy.window_seconds)  # 1s: Finnhub's own declared window
    assert tracker.try_reserve("finnhub") is True


def test_a_tradier_reservation_expires_after_its_declared_minute() -> None:
    policy = tradier_rolling_window_policy(ProviderEndpointEnvironment.PRODUCTION)
    clock = FakeClock()
    tracker = ProviderRollingWindowTracker((policy,), clock)
    for _ in range(policy.window_limit):
        assert tracker.try_reserve("tradier") is True
    assert tracker.try_reserve("tradier") is False  # exactly at the declared per-minute limit

    clock.advance(seconds=policy.window_seconds)  # 60s: Tradier's own declared window
    assert tracker.try_reserve("tradier") is True


def test_summary_reports_sanitized_in_window_counts_only() -> None:
    clock = FakeClock()
    tracker = ProviderRollingWindowTracker((policy(window_seconds=60, window_limit=5),), clock)
    tracker.try_reserve("tradier")
    tracker.try_reserve("tradier")
    assert tracker.summary() == {"tradier": 2}
    clock.advance(seconds=61)
    assert tracker.summary() == {"tradier": 0}
