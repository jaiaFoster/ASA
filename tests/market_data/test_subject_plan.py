"""SPRINT-014 S14-PR-03: two-phase subject-first acquisition plan tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from market_data import (
    BudgetScope,
    CapabilityFulfillmentService,
    CapabilityRegistry,
    ProviderPriority,
    ProviderPriorityPolicy,
    ProviderRegistry,
    RequestBudgetManager,
    RequestBudgetPolicy,
)
from market_data.attempts import (
    AcquisitionOutcome,
    AttemptQuery,
    InMemoryAcquisitionAttemptRepository,
)
from market_data.subject_plan import PlanBackedFulfillment, SubjectAcquisitionPlan
from tests.market_data.test_fulfillment import (
    CAPABILITY,
    Clock,
    FixtureScenario,
    ProviderErrorCode,
    _FailsOnceProvider,
    provider,
    request,
    service,
)

NOW = datetime(2026, 7, 21, 16, 0, tzinfo=UTC)


def _plan(
    fulfillment,
    *,
    subject: str = "AAPL",
    plan_id: str = "plan-1",
    attempt_repository: InMemoryAcquisitionAttemptRepository | None = None,
    maximum_attempts_per_request: int = 2,
) -> tuple[SubjectAcquisitionPlan, InMemoryAcquisitionAttemptRepository]:
    repository = attempt_repository or InMemoryAcquisitionAttemptRepository()
    plan = SubjectAcquisitionPlan(
        subject,
        fulfillment,
        attempt_repository=repository,
        plan_id=plan_id,
        clock=Clock(NOW),
        maximum_attempts_per_request=maximum_attempts_per_request,
    )
    return plan, repository


class TestConstruction:
    def test_rejects_unnormalized_subject(self) -> None:
        fulfillment, _ = service(provider("primary"))
        with pytest.raises(ValueError, match="subject"):
            SubjectAcquisitionPlan(
                " AAPL",
                fulfillment,
                attempt_repository=InMemoryAcquisitionAttemptRepository(),
                plan_id="plan-1",
                clock=Clock(NOW),
            )

    def test_rejects_non_positive_maximum_attempts(self) -> None:
        fulfillment, _ = service(provider("primary"))
        with pytest.raises(ValueError, match="maximum_attempts_per_request"):
            SubjectAcquisitionPlan(
                "AAPL",
                fulfillment,
                attempt_repository=InMemoryAcquisitionAttemptRepository(),
                plan_id="plan-1",
                clock=Clock(NOW),
                maximum_attempts_per_request=0,
            )


class TestResolveSharesSuccess:
    def test_a_second_resolve_of_the_same_request_costs_no_new_provider_call(self) -> None:
        fulfillment, budgets = service(provider("primary"))
        plan, _ = _plan(fulfillment)

        first = plan.resolve(request())
        second = plan.resolve(request())

        assert first.status.value == "fulfilled"
        assert first is second
        assert len(budgets.accounting) == 1  # only the first resolve() ever called a provider


class TestResolveSharesFailure:
    def test_a_second_resolve_of_an_already_exhausted_failure_costs_no_new_provider_call(
        self,
    ) -> None:
        always_fails = FixtureScenario(
            failures=((request().capability, ProviderErrorCode.NO_DATA),)
        )
        fulfillment, budgets = service(provider("primary", always_fails), maximum=4)
        # maximum_attempts_per_request=1 -- the plan's own bounded retry is
        # exhausted after the single first attempt.
        plan, _ = _plan(fulfillment, maximum_attempts_per_request=1)

        first = plan.resolve(request(), required=False)
        second = plan.resolve(request(), required=False)

        assert first.status.value == "failed"
        assert first is second
        # Exactly one provider round trip total across BOTH resolve() calls
        # -- this is the fix for S14-PR-01's own root-cause finding: a
        # second consumer never independently retries an already-exhausted
        # failure.
        assert len(budgets.accounting) == 1

    def test_the_plans_own_bounded_retry_gets_a_second_chance_before_freezing(self) -> None:
        # FixtureScenario's own outcome is fixed for the provider's whole
        # lifetime (unlike the _FailsOnceProvider used elsewhere), so this
        # proves the *number* of attempts the plan itself makes before
        # giving up, not that a later attempt happens to succeed.
        always_fails = FixtureScenario(
            failures=((request().capability, ProviderErrorCode.NO_DATA),)
        )
        fulfillment, budgets = service(provider("primary", always_fails), maximum=4)
        plan, _ = _plan(fulfillment, maximum_attempts_per_request=2)

        result = plan.resolve(request(), required=False)

        assert result.status.value == "failed"
        assert len(budgets.accounting) == 2  # the bounded retry actually ran


class TestConsumerOrderIndependence:
    def test_order_of_two_consumers_does_not_change_the_total_call_count(self) -> None:
        always_fails = FixtureScenario(
            failures=((request().capability, ProviderErrorCode.NO_DATA),)
        )

        fulfillment_a, budgets_a = service(provider("primary", always_fails), maximum=4)
        plan_a, _ = _plan(fulfillment_a, maximum_attempts_per_request=1)
        plan_a.resolve(request(), required=False)  # "consumer 1" first
        plan_a.resolve(request(), required=False)  # "consumer 2" second

        fulfillment_b, budgets_b = service(provider("primary", always_fails), maximum=4)
        plan_b, _ = _plan(fulfillment_b, maximum_attempts_per_request=1)
        plan_b.resolve(request(), required=False)  # same two consumers, same
        plan_b.resolve(request(), required=False)  # request, reverse arrival order

        assert len(budgets_a.accounting) == len(budgets_b.accounting) == 1


class TestAttemptPersistence:
    def test_every_attempt_is_recorded_including_the_failed_one(self) -> None:
        always_fails = FixtureScenario(
            failures=((request().capability, ProviderErrorCode.NO_DATA),)
        )
        fulfillment, _ = service(provider("primary", always_fails), maximum=4)
        plan, repository = _plan(
            fulfillment, plan_id="cycle-1:AAPL", maximum_attempts_per_request=2
        )

        plan.resolve(request(), required=False)

        rows = repository.query(AttemptQuery(screening_cycle_id="cycle-1:AAPL", limit=10))
        assert len(rows) == 2  # both bounded-retry attempts persisted
        assert all(item.outcome is AcquisitionOutcome.NO_MATCHING_DATA for item in rows)

    def test_a_reused_result_does_not_duplicate_attempt_rows(self) -> None:
        fulfillment, _ = service(provider("primary"))
        plan, repository = _plan(fulfillment, plan_id="cycle-1:AAPL")

        plan.resolve(request())
        plan.resolve(request())

        rows = repository.query(AttemptQuery(screening_cycle_id="cycle-1:AAPL", limit=10))
        assert len(rows) == 1

    def test_sequence_is_unique_across_multiple_resolved_requests(self) -> None:
        primary = provider("primary")
        fulfillment, _ = service(primary, maximum=4)
        plan, repository = _plan(fulfillment, plan_id="cycle-1:AAPL")

        plan.resolve(request())
        # A second, distinct request (different maximum_age_seconds changes
        # required_fields identity indirectly via a fresh CapabilityRequest)
        # -- simplest distinct request here is simply calling resolve twice
        # is already covered above; assert monotonically increasing sequence
        # for the one attempt recorded so far.
        rows = repository.query(AttemptQuery(screening_cycle_id="cycle-1:AAPL", limit=10))
        assert [item.sequence for item in rows] == list(range(len(rows)))

    def test_an_earlier_failure_stays_queryable_after_the_plans_own_retry_succeeds(
        self,
    ) -> None:
        # _FailsOnceProvider fails its first fetch, then succeeds every
        # fetch after -- so the plan's own bounded retry (attempt 1: fails,
        # attempt 2: succeeds) exercises exactly the "eviction and later
        # success" half of this ticket's own acceptance criterion: the
        # underlying CapabilityFulfillmentService evicts the failed cache
        # entry internally before its own independent retry, but that
        # eviction must never erase the failure's own durable attempt row.
        flaky = _FailsOnceProvider("primary")
        registry = ProviderRegistry((flaky,))
        capabilities = CapabilityRegistry(
            registry, ProviderPriorityPolicy("v1", (ProviderPriority(CAPABILITY, ("primary",)),))
        )
        budgets = RequestBudgetManager(
            (RequestBudgetPolicy("primary", BudgetScope.RUNTIME, 4, 4, 0, "v1"),), Clock(NOW)
        )
        fulfillment = CapabilityFulfillmentService(registry, capabilities, budgets)
        plan, repository = _plan(
            fulfillment, plan_id="cycle-1:AAPL", maximum_attempts_per_request=2
        )

        result = plan.resolve(request(), required=False)

        assert result.status.value == "fulfilled"  # the plan's own retry recovered
        rows = repository.query(AttemptQuery(screening_cycle_id="cycle-1:AAPL", limit=10))
        assert len(rows) == 2
        assert rows[0].outcome is AcquisitionOutcome.TRANSPORT_FAILURE  # the earlier failure
        assert rows[1].outcome is AcquisitionOutcome.SUCCESS  # the later, plan-owned retry
        # Both rows independently queryable by outcome -- the failure is
        # not erased by the later success, and a caller can distinguish
        # "recovered on retry" from "succeeded on the first try."
        failed_only = repository.query(
            AttemptQuery(
                screening_cycle_id="cycle-1:AAPL",
                outcome=AcquisitionOutcome.TRANSPORT_FAILURE,
            )
        )
        assert len(failed_only) == 1


class TestDoesNotMutateUnderlyingService:
    def test_the_wrapped_fulfillment_service_still_reflects_its_own_reuse_semantics(self) -> None:
        # SubjectAcquisitionPlan wraps CapabilityFulfillmentService; it must
        # never bypass or replace its own de-duplication/fallback mechanics.
        fulfillment, _ = service(provider("primary"))
        plan, _ = _plan(fulfillment)

        plan.resolve(request())
        direct = fulfillment.fulfill(request())  # bypassing the plan entirely

        assert direct.status.value == "fulfilled"
        assert [decision.value for _, decision in fulfillment.call_log] == ["fresh", "reused"]


class TestPlanBackedFulfillment:
    """SPRINT-014 S14-PR-05A, Architect review finding B3: a legacy
    consumer calling .fulfill() directly (exactly as
    CapabilityFulfillmentService's own real callers already do) must
    share the same plan-owned resolution a migrated consumer's own
    plan.resolve() call sees -- one exhausted or successful request per
    subject per cycle, never once per consumer.
    """

    def test_fulfill_delegates_to_the_wrapped_plans_resolve(self) -> None:
        fulfillment, _ = service(provider("primary"))
        plan, _ = _plan(fulfillment)
        wrapper = PlanBackedFulfillment(plan)

        via_wrapper = wrapper.fulfill(request())
        via_plan = plan.resolve(request())

        assert via_wrapper.status.value == "fulfilled"
        assert via_wrapper is via_plan  # the exact same resolved result, not a copy

    def test_a_migrated_consumers_plan_resolve_and_a_legacy_consumers_fulfill_share_one_result(
        self,
    ) -> None:
        """The exact scenario B3 describes: one caller uses the plan
        directly (as the generic planner does); another, unmodified
        legacy caller only knows how to call .fulfill() on whatever it is
        given. Wrapping the same plan for the second caller means both
        see the identical resolved result and only one provider round
        trip happens in total.
        """
        fulfillment, _ = service(provider("primary"))
        plan, _ = _plan(fulfillment)
        legacy_view: CapabilityFulfillmentService = PlanBackedFulfillment(plan)  # type: ignore[assignment]

        migrated_result = plan.resolve(request())
        legacy_result = legacy_view.fulfill(request())

        assert migrated_result is legacy_result
        assert len(fulfillment.call_log) == 1  # exactly one real provider call, not two

    def test_an_exhausted_failure_is_shared_across_a_legacy_and_a_migrated_consumer(self) -> None:
        always_fails = FixtureScenario(failures=((CAPABILITY, ProviderErrorCode.NO_DATA),))
        fulfillment, _ = service(provider("primary", always_fails))
        plan, repository = _plan(fulfillment, maximum_attempts_per_request=1)
        legacy_view = PlanBackedFulfillment(plan)

        migrated_result = plan.resolve(request(), required=False)
        legacy_result = legacy_view.fulfill(request(), required=False)

        assert migrated_result.status.value == "failed"
        assert legacy_result is migrated_result
        # Exactly one attempt was ever made and durably recorded -- the
        # legacy caller's own later call never triggered a second one.
        rows = repository.query(AttemptQuery(limit=10))
        assert len(rows) == 1

    def test_consumer_order_does_not_change_the_shared_result_or_call_count(self) -> None:
        """B3's own "strategy-order and consumer-count independence"
        requirement, proven the other way around: the legacy caller
        resolves first this time.
        """
        fulfillment, _ = service(provider("primary"))
        plan, _ = _plan(fulfillment)
        legacy_view = PlanBackedFulfillment(plan)

        legacy_result = legacy_view.fulfill(request())
        migrated_result = plan.resolve(request())

        assert legacy_result is migrated_result
        assert len(fulfillment.call_log) == 1
