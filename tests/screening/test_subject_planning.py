"""SPRINT-014 S14-PR-05A: generic phased subject planning.

Every test consumer here is synthetic -- none references Earnings
Calendar, Forward Factor, or Skew Momentum. That is deliberate: this
module proves screening/subject_planning.py's own generic mechanism in
isolation, before any real strategy is wired to it (kept as a separate,
later increment per the Architect's own directive).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from domain import (
    CapabilityDemand,
    DemandExpansion,
    EvidenceUsability,
    MarketCapability,
    UnknownReason,
)
from domain.values import DomainInvariantError
from market_data.attempts import InMemoryAcquisitionAttemptRepository
from market_data.fulfillment import CapabilityFulfillmentResult, FulfillmentStatus
from market_data.resolution import ResolutionPolicy
from market_data.subject_plan import SubjectAcquisitionPlan
from screening.subject_planning import (
    SubjectPlanConsumer,
    run_subject_plan,
)
from tests.market_data.test_fulfillment import (
    CAPABILITY,
    Clock,
    FixtureScenario,
    ProviderErrorCode,
    provider,
    service,
)

NOW = datetime(2026, 8, 6, 15, 0, tzinfo=UTC)
_RESOLUTION_POLICY = {CAPABILITY: ResolutionPolicy("v1", ("primary",), 3600, ("last",))}


def _quote_demand(*, required: bool = True) -> CapabilityDemand:
    return CapabilityDemand(CAPABILITY, ("last",), NOW, NOW, required=required)


def _plan(
    fulfillment, *, plan_id: str = "cycle-1:AAPL", maximum_attempts_per_request: int = 2
) -> SubjectAcquisitionPlan:
    return SubjectAcquisitionPlan(
        "AAPL",
        fulfillment,
        attempt_repository=InMemoryAcquisitionAttemptRepository(),
        plan_id=plan_id,
        clock=Clock(NOW),
        maximum_attempts_per_request=maximum_attempts_per_request,
    )


def _no_expansion(_evidence: object) -> DemandExpansion:
    return DemandExpansion()


class TestTwoSyntheticConsumers:
    def test_bootstrap_evidence_is_shared_across_every_consumer_not_siloed(self) -> None:
        """Consumer B declares no bootstrap demand of its own -- if it can
        still see Consumer A's own bootstrap result in phase two, evidence
        is genuinely shared, not per-consumer.
        """
        seen_by_b: dict[str, object] = {}

        def b_expand(evidence: object) -> DemandExpansion:
            seen_by_b.update(evidence)  # type: ignore[arg-type]
            return DemandExpansion()

        fulfillment, _ = service(provider("primary"))
        plan = _plan(fulfillment)
        demand = _quote_demand()
        consumer_a = SubjectPlanConsumer("consumer-a", (demand,), _no_expansion)
        consumer_b = SubjectPlanConsumer("consumer-b", (), b_expand)

        result = run_subject_plan(
            plan,
            NOW,
            (consumer_a, consumer_b),
            provider_metadata=(provider("primary").metadata,),
            resolution_policy_by_capability=_RESOLUTION_POLICY,
        )

        assert demand.demand_id in result.diagnostic_fulfillments
        assert demand.demand_id in seen_by_b
        # seen_by_b holds the *restricted* ResolvedCapabilityEvidence
        # projection (never the raw CapabilityFulfillmentResult
        # SubjectPlanResult.diagnostic_fulfillments itself carries) --
        # proven shared by content: the projection reflects the same
        # resolved, usable evidence the raw result actually carries.
        projected = seen_by_b[demand.demand_id]
        raw = result.diagnostic_fulfillments[demand.demand_id]
        assert projected.usability is EvidenceUsability.RESOLVED
        assert projected.value == raw.observations[0].value
        assert projected.observation_ids == (raw.observations[0].observation_id,)

    def test_a_phase_two_demand_identical_to_a_phase_one_demand_resolves_only_once(self) -> None:
        demand = _quote_demand()

        def b_expand(_evidence: object) -> DemandExpansion:
            return DemandExpansion(demands=(demand,))

        fulfillment, _ = service(provider("primary"))
        plan = _plan(fulfillment)
        consumer_a = SubjectPlanConsumer("consumer-a", (demand,), _no_expansion)
        consumer_b = SubjectPlanConsumer("consumer-b", (), b_expand)

        result = run_subject_plan(
            plan,
            NOW,
            (consumer_a, consumer_b),
            provider_metadata=(provider("primary").metadata,),
            resolution_policy_by_capability=_RESOLUTION_POLICY,
        )

        assert len(fulfillment.call_log) == 1
        assert result.demand_ids_by_consumer["consumer-a"] == (demand.demand_id,)
        assert result.demand_ids_by_consumer["consumer-b"] == (demand.demand_id,)

    def test_selections_and_unknown_reasons_pass_through_untouched(self) -> None:
        reason = UnknownReason("no_data", demand_ids=(_quote_demand().demand_id,))

        def expand(_evidence: object) -> DemandExpansion:
            return DemandExpansion(selections=(("chosen", "x"),), unknown_reasons=(reason,))

        fulfillment, _ = service(provider("primary"))
        plan = _plan(fulfillment)
        consumer = SubjectPlanConsumer("consumer-a", (_quote_demand(),), expand)

        result = run_subject_plan(
            plan,
            NOW,
            (consumer,),
            provider_metadata=(provider("primary").metadata,),
            resolution_policy_by_capability=_RESOLUTION_POLICY,
        )

        expansion = result.expansions_by_consumer["consumer-a"]
        assert expansion.selections == (("chosen", "x"),)
        assert expansion.unknown_reasons == (reason,)


class TestOrderAndCountIndependence:
    def test_consumer_registration_order_does_not_change_diagnostic_fulfillments_or_call_count(
        self,
    ) -> None:
        demand = _quote_demand()

        def build(order: tuple[str, str]) -> tuple:
            fulfillment, _ = service(provider("primary"))
            plan = _plan(fulfillment)
            consumer_a = SubjectPlanConsumer("consumer-a", (demand,), _no_expansion)
            consumer_b = SubjectPlanConsumer(
                "consumer-b", (), lambda _e: DemandExpansion(demands=(demand,))
            )
            by_id = {"consumer-a": consumer_a, "consumer-b": consumer_b}
            consumers = tuple(by_id[name] for name in order)
            result = run_subject_plan(
                plan,
                NOW,
                consumers,
                provider_metadata=(provider("primary").metadata,),
                resolution_policy_by_capability=_RESOLUTION_POLICY,
            )
            return result, fulfillment

        forward_result, forward_fulfillment = build(("consumer-a", "consumer-b"))
        reverse_result, reverse_fulfillment = build(("consumer-b", "consumer-a"))

        assert set(forward_result.diagnostic_fulfillments) == set(
            reverse_result.diagnostic_fulfillments
        )
        assert len(forward_fulfillment.call_log) == len(reverse_fulfillment.call_log) == 1

    def test_an_extra_uninvolved_consumer_does_not_change_another_consumers_own_evidence(
        self,
    ) -> None:
        demand = _quote_demand()
        fulfillment, _ = service(provider("primary"))
        plan = _plan(fulfillment)
        consumer_a = SubjectPlanConsumer("consumer-a", (demand,), _no_expansion)
        consumer_bystander = SubjectPlanConsumer("bystander", (), _no_expansion)

        with_bystander = run_subject_plan(
            plan,
            NOW,
            (consumer_a, consumer_bystander),
            provider_metadata=(provider("primary").metadata,),
            resolution_policy_by_capability=_RESOLUTION_POLICY,
        )

        fulfillment_alone, _ = service(provider("primary"))
        plan_alone = _plan(fulfillment_alone)
        alone = run_subject_plan(
            plan_alone,
            NOW,
            (consumer_a,),
            provider_metadata=(provider("primary").metadata,),
            resolution_policy_by_capability=_RESOLUTION_POLICY,
        )

        assert (
            with_bystander.diagnostic_fulfillments[demand.demand_id].status
            == alone.diagnostic_fulfillments[demand.demand_id].status
        )
        assert with_bystander.demand_ids_by_consumer["consumer-a"] == (demand.demand_id,)


class TestSharedExhaustedFailure:
    def test_two_consumers_sharing_a_failing_demand_see_the_identical_result_and_pay_once(
        self,
    ) -> None:
        always_fails = FixtureScenario(failures=((CAPABILITY, ProviderErrorCode.NO_DATA),))
        fulfillment, _ = service(provider("primary", always_fails))
        plan = _plan(fulfillment, maximum_attempts_per_request=1)
        demand = _quote_demand(required=False)
        consumer_a = SubjectPlanConsumer("consumer-a", (demand,), _no_expansion)
        consumer_b = SubjectPlanConsumer("consumer-b", (demand,), _no_expansion)

        result = run_subject_plan(
            plan,
            NOW,
            (consumer_a, consumer_b),
            provider_metadata=(provider("primary").metadata,),
            resolution_policy_by_capability=_RESOLUTION_POLICY,
        )

        resolved = result.diagnostic_fulfillments[demand.demand_id]
        assert resolved.status is FulfillmentStatus.FAILED
        assert len(fulfillment.call_log) == 1


class TestConstructionAndErrorHandling:
    def test_requires_at_least_one_consumer(self) -> None:
        fulfillment, _ = service(provider("primary"))
        plan = _plan(fulfillment)
        with pytest.raises(ValueError, match="at least one consumer"):
            run_subject_plan(
                plan,
                NOW,
                (),
                provider_metadata=(provider("primary").metadata,),
                resolution_policy_by_capability=_RESOLUTION_POLICY,
            )

    def test_rejects_duplicate_consumer_ids(self) -> None:
        fulfillment, _ = service(provider("primary"))
        plan = _plan(fulfillment)
        consumer = SubjectPlanConsumer("dup", (_quote_demand(),), _no_expansion)
        with pytest.raises(ValueError, match="unique consumer_id"):
            run_subject_plan(
                plan,
                NOW,
                (consumer, consumer),
                provider_metadata=(provider("primary").metadata,),
                resolution_policy_by_capability=_RESOLUTION_POLICY,
            )

    def test_consumer_id_must_be_normalized(self) -> None:
        with pytest.raises(ValueError, match="consumer_id"):
            SubjectPlanConsumer(" padded", (), _no_expansion)

    def test_multiple_results_for_one_capability_without_a_reducer_raises(self) -> None:
        first = _quote_demand()
        # Two distinct demand_ids sharing one capability: vary the window
        # to force genuinely different demand_ids.
        second = CapabilityDemand(CAPABILITY, ("last",), NOW, NOW + timedelta(seconds=1))
        assert first.demand_id != second.demand_id

        fulfillment, _ = service(provider("primary"))
        plan = _plan(fulfillment)
        consumer = SubjectPlanConsumer("consumer-a", (first, second), _no_expansion)

        with pytest.raises(ValueError, match="capability_reducer_by_capability"):
            run_subject_plan(
                plan,
                NOW,
                (consumer,),
                provider_metadata=(provider("primary").metadata,),
                resolution_policy_by_capability=_RESOLUTION_POLICY,
            )

    def test_multiple_results_for_one_capability_with_a_registered_reducer_succeeds(self) -> None:
        first = _quote_demand()
        second = CapabilityDemand(CAPABILITY, ("last",), NOW, NOW + timedelta(seconds=1))
        received: list[tuple[CapabilityFulfillmentResult, ...]] = []

        def reducer(
            results: tuple[CapabilityFulfillmentResult, ...],
        ) -> CapabilityFulfillmentResult:
            received.append(results)
            return results[0]

        fulfillment, _ = service(provider("primary"))
        plan = _plan(fulfillment)
        consumer = SubjectPlanConsumer("consumer-a", (first, second), _no_expansion)

        run_subject_plan(
            plan,
            NOW,
            (consumer,),
            provider_metadata=(provider("primary").metadata,),
            resolution_policy_by_capability=_RESOLUTION_POLICY,
            capability_reducer_by_capability={CAPABILITY: reducer},
        )

        assert len(received) == 1
        assert len(received[0]) == 2

    def test_a_genuine_plan_level_exception_propagates_uncaught(self) -> None:
        """B4: expected missing evidence is typed data (a FAILED result);
        a real invariant/configuration failure must remain a real
        exception, never silently downgraded. A capability nothing in the
        registry declares raises DomainInvariantError from deep inside
        CapabilityFulfillmentService.fulfill() -- this module performs no
        exception handling of its own, so it must reach the caller intact.
        """
        fulfillment, _ = service(provider("primary"))
        plan = _plan(fulfillment)
        undeclared_capability_demand = CapabilityDemand(
            MarketCapability.HISTORICAL_BARS_V1, ("close",), NOW, NOW
        )
        consumer = SubjectPlanConsumer("consumer-a", (undeclared_capability_demand,), _no_expansion)

        with pytest.raises(DomainInvariantError):
            run_subject_plan(
                plan,
                NOW,
                (consumer,),
                provider_metadata=(provider("primary").metadata,),
                resolution_policy_by_capability=_RESOLUTION_POLICY,
            )
