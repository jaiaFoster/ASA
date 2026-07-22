from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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

START = datetime(2026, 7, 21, tzinfo=timezone.utc)


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
