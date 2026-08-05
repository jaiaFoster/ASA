from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from domain import MarketCapability
from market_data.budget import (
    BudgetExhaustedError,
    BudgetScope,
    QuotaObservation,
    RequestBudgetManager,
    RequestBudgetPolicy,
    RequestOutcome,
)
from market_data.providers import ProviderErrorCode
from market_data.rolling_window import ProviderRollingWindowTracker, RollingWindowPolicy

START = datetime(2026, 7, 21, tzinfo=UTC)


@dataclass
class FakeClock:
    value: datetime = START

    def now(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


def manager(clock: FakeClock, *, maximum: int = 4, burst: int = 2) -> RequestBudgetManager:
    return RequestBudgetManager(
        (
            RequestBudgetPolicy("fixture", BudgetScope.RUNTIME, maximum, burst, 1, "v1"),
            RequestBudgetPolicy("fixture", BudgetScope.VALIDATION, 2, 1, 1, "v1"),
        ),
        clock,
    )


def test_authorization_and_completion_are_auditable() -> None:
    clock = FakeClock()
    budget = manager(clock)
    authorization = budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    clock.advance(1)
    entry = budget.complete(authorization.authorization_id, RequestOutcome.SUCCEEDED)
    assert entry.outcome is RequestOutcome.SUCCEEDED
    assert budget.accounting == (entry,)


def test_budget_exhaustion_fails_before_transport() -> None:
    clock = FakeClock()
    budget = manager(clock, maximum=1, burst=1)
    budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    clock.advance(1)
    with pytest.raises(BudgetExhaustedError, match="budget exhausted"):
        budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)


def test_runtime_and_validation_budgets_are_isolated() -> None:
    clock = FakeClock()
    budget = manager(clock, maximum=1, burst=1)
    budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    validation = budget.authorize(
        "fixture",
        MarketCapability.REAL_TIME_QUOTE_V1,
        1,
        BudgetScope.VALIDATION,
    )
    assert validation.allowed_request_units == 1


def test_burst_limit_uses_injected_clock() -> None:
    clock = FakeClock()
    budget = manager(clock, burst=1)
    budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    with pytest.raises(BudgetExhaustedError, match="burst"):
        budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    clock.advance(1)
    assert budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)


def test_retry_consumes_budget_and_is_bounded() -> None:
    clock = FakeClock()
    budget = manager(clock)
    original = budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    clock.advance(1)
    retry = budget.authorize(
        "fixture",
        MarketCapability.REAL_TIME_QUOTE_V1,
        1,
        retry_of=original.authorization_id,
    )
    assert budget.accounting[-1].attempt_number == 2
    clock.advance(1)
    with pytest.raises(BudgetExhaustedError, match="retry budget"):
        budget.authorize(
            "fixture",
            MarketCapability.REAL_TIME_QUOTE_V1,
            1,
            retry_of=retry.authorization_id,
        )


def test_each_request_has_an_independent_retry_budget() -> None:
    clock = FakeClock()
    budget = manager(clock, maximum=8)
    first = budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    clock.advance(1)
    budget.authorize(
        "fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1, retry_of=first.authorization_id
    )
    clock.advance(1)
    second = budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    clock.advance(1)
    retry = budget.authorize(
        "fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1, retry_of=second.authorization_id
    )
    assert retry.allowed_attempts == 2


def test_retry_after_creates_explicit_cooldown() -> None:
    clock = FakeClock()
    budget = manager(clock)
    authorization = budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    budget.complete(
        authorization.authorization_id,
        RequestOutcome.RATE_LIMITED,
        retry_after_seconds=5,
    )
    clock.advance(4)
    with pytest.raises(BudgetExhaustedError, match="cooldown"):
        budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    clock.advance(1)
    assert budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)


def test_quota_headers_create_immutable_observation() -> None:
    clock = FakeClock()
    budget = manager(clock)
    authorization = budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    quota = QuotaObservation("fixture", START, 9, 10, START + timedelta(minutes=1), ("x-limit",))
    entry = budget.complete(
        authorization.authorization_id, RequestOutcome.SUCCEEDED, quota=quota
    )
    assert entry.quota == quota


def test_unknown_provider_limit_never_means_unlimited() -> None:
    with pytest.raises(BudgetExhaustedError, match="No finite"):
        manager(FakeClock()).authorize("unknown", MarketCapability.REAL_TIME_QUOTE_V1, 1)


def test_same_inputs_and_fake_clock_produce_same_authorization() -> None:
    first = manager(FakeClock()).authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    second = manager(FakeClock()).authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    assert first == second


# -- SPRINT-013 S13-03A: burst sliding window and shared cross-pair
# rolling-window integration --------------------------------------------


def test_microsecond_separated_requests_obey_the_same_active_window() -> None:
    """The confirmed root cause (issue #261): the old burst dict keyed
    usage by the exact authorization timestamp, so under a real clock
    (unique to the microsecond on every call) two requests essentially
    never collided and burst_limit was unenforceable in production. A
    FakeClock that doesn't advance at all is the adversarial case that
    exposes this."""
    clock = FakeClock()
    budget = manager(clock, burst=1)
    budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    with pytest.raises(BudgetExhaustedError, match="burst"):
        budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)


def test_burst_window_duration_is_configurable_and_expires_deterministically() -> None:
    clock = FakeClock()
    budget = RequestBudgetManager(
        (RequestBudgetPolicy("fixture", BudgetScope.RUNTIME, 10, 1, 1, "v1",
                              burst_window_seconds=5),),
        clock,
    )
    budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    clock.advance(4)
    with pytest.raises(BudgetExhaustedError, match="burst"):
        budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    clock.advance(2)  # now 6s after the first authorization
    assert budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)


def test_shared_rolling_window_refusal_never_burns_local_pair_budget() -> None:
    """A cross-pair provider-level refusal must be refused before any
    local (pair-scoped) budget is consumed -- otherwise a shared-window
    refusal would silently eat into this pair's own accounting for a
    request that was never actually sent."""
    clock = FakeClock()
    window = ProviderRollingWindowTracker(
        (RollingWindowPolicy("fixture", 60, 1, "documented"),), clock
    )
    window.try_reserve("fixture")  # consume the one shared slot
    budget = RequestBudgetManager(
        (RequestBudgetPolicy("fixture", BudgetScope.RUNTIME, 10, 5, 1, "v1"),),
        clock,
        rolling_window=window,
    )
    with pytest.raises(BudgetExhaustedError, match="rolling-window"):
        budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    assert budget.accounting == ()  # nothing was locally recorded


def test_shared_rolling_window_is_consulted_across_independently_constructed_managers() -> None:
    """The whole point: two DIFFERENT RequestBudgetManager instances (one
    per pair, as production actually builds them) sharing one
    ProviderRollingWindowTracker enforce one real cross-pair limit."""
    clock = FakeClock()
    window = ProviderRollingWindowTracker(
        (RollingWindowPolicy("fixture", 60, 1, "documented"),), clock
    )
    first_pair_budget = RequestBudgetManager(
        (RequestBudgetPolicy("fixture", BudgetScope.RUNTIME, 10, 5, 1, "v1"),),
        clock,
        rolling_window=window,
    )
    second_pair_budget = RequestBudgetManager(
        (RequestBudgetPolicy("fixture", BudgetScope.RUNTIME, 10, 5, 1, "v1"),),
        clock,
        rolling_window=window,
    )
    assert first_pair_budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    with pytest.raises(BudgetExhaustedError, match="rolling-window"):
        second_pair_budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    # Each manager's own local accounting stays independent (pair isolation).
    assert len(first_pair_budget.accounting) == 1
    assert len(second_pair_budget.accounting) == 0


def test_upstream_and_local_refusal_remain_distinct() -> None:
    """A shared-window (upstream-shaped) refusal and a local total-budget
    refusal must raise distinguishable errors, not the same generic one."""
    clock = FakeClock()
    window = ProviderRollingWindowTracker(
        (RollingWindowPolicy("fixture", 60, 1, "documented"),), clock
    )
    window.try_reserve("fixture")
    budget = RequestBudgetManager(
        (RequestBudgetPolicy("fixture", BudgetScope.RUNTIME, 1, 1, 1, "v1"),),
        clock,
        rolling_window=window,
    )
    with pytest.raises(BudgetExhaustedError, match="rolling-window"):
        budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)

    other_budget = RequestBudgetManager(
        (RequestBudgetPolicy("fixture", BudgetScope.RUNTIME, 1, 1, 1, "v1"),), clock
    )
    other_budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    with pytest.raises(BudgetExhaustedError, match="budget exhausted"):
        other_budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)


def test_local_rolling_window_exhaustion_has_a_distinct_error_code_from_upstream_rate_limit() -> (
    None
):
    """SPRINT-013 P0: a LOCAL shared-window refusal (raised here, before
    any provider request is ever made) must carry its own distinct
    ProviderErrorCode, never ProviderErrorCode.RATE_LIMITED -- that code
    is reserved for a genuine upstream 429/rate-limit response
    (market_data/fulfillment.py's own classification of a real fetch
    result), a structurally different event this manager never raises.
    """
    clock = FakeClock()
    window = ProviderRollingWindowTracker(
        (RollingWindowPolicy("fixture", 60, 1, "documented"),), clock
    )
    window.try_reserve("fixture")
    budget = RequestBudgetManager(
        (RequestBudgetPolicy("fixture", BudgetScope.RUNTIME, 10, 5, 1, "v1"),),
        clock,
        rolling_window=window,
    )
    with pytest.raises(BudgetExhaustedError) as excinfo:
        budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    assert excinfo.value.code is ProviderErrorCode.PROVIDER_ROLLING_WINDOW_EXHAUSTED
    assert excinfo.value.code is not ProviderErrorCode.RATE_LIMITED


def test_complete_forwards_safe_reset_hint_to_shared_window() -> None:
    clock = FakeClock()
    window = ProviderRollingWindowTracker(
        (RollingWindowPolicy("fixture", 60, 5, "documented"),), clock
    )
    budget = RequestBudgetManager(
        (RequestBudgetPolicy("fixture", BudgetScope.RUNTIME, 10, 5, 1, "v1"),),
        clock,
        rolling_window=window,
    )
    authorization = budget.authorize("fixture", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    quota = QuotaObservation(
        "fixture", clock.now(), 0, 5, clock.now() + timedelta(minutes=5), ("x-ratelimit",)
    )
    budget.complete(authorization.authorization_id, RequestOutcome.RATE_LIMITED, quota=quota)
    # The reset hint (5 minutes out) is now the binding constraint, tighter
    # than the window's own 60s duration would otherwise allow.
    clock.advance(65)
    assert window.try_reserve("fixture") is False
