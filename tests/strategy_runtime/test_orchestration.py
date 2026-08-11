"""SPRINT-014 S14-PR-05A, Architect checkpoint: fourteenth review PASS --
"authorized next increment": one shared orchestration seam wiring one
SubjectAcquisitionPlan/PlanBackedFulfillment per subject, subject-first
Earnings shadow preparation, and generic parity diagnostics, while legacy
stays authoritative.

Two layers tested here:

1. Synthetic dispatch mechanics (TestBuildSubjectAcquisitionAccess,
   TestPrepareSubjectShadowKnowledge, TestRefreshWithShadowDispatch) --
   proves strategy_runtime.orchestration's own generic control flow
   (match/mismatch/shadow_unknown/shadow_error/not_shadowed, persist-
   legacy-only) using synthetic, non-Earnings registries, mirroring
   tests/screening/test_subject_planning.py's own "everything synthetic"
   philosophy for the parts that do not need real financial data.

2. A real, end-to-end Earnings Calendar proof
   (TestEarningsCalendarSharedPlanEndToEnd) reusing
   tests/screening/test_live_adapters.py's own proven
   MultiExpirationFixtureProvider/_fulfillment() harness (already the
   fixture screening/live_adapters.py's own tests use to prove Earnings
   Calendar, Forward Factor, and Skew Momentum all succeed against a
   real, multi-expiration, multi-strike CapabilityFulfillmentService) --
   proving the actual, mandatory provider-call-count properties: zero
   additional legacy Earnings calls once subject-first preparation has
   populated the plan, order independence, a shared provider failure
   exhausted only once, and FF/Skew sharing the exact same plan.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

from analytics.features import DerivedFactRequest, DerivedFactSet
from domain import (
    CanonicalFact,
    CapabilityDemand,
    DemandExpansion,
    MarketCapability,
    MarketObservation,
    UnknownReason,
)
from market_data import CapabilityFulfillmentService, FixtureScenario, ProviderDependencies
from market_data.attempts import InMemoryAcquisitionAttemptRepository
from market_data.capability_coalescing import reduce_option_chain_results
from market_data.providers import ProviderErrorCode, ProviderMetadata
from market_data.registry import CapabilityRegistry, ProviderRegistry
from market_data.resolution import ResolutionPolicy
from market_data.subject_plan import PlanBackedFulfillment, SubjectAcquisitionPlan
from screening.live_acquisition import build_capability_registry, build_request_budget_manager
from screening.subject_planning import ResolvedEvidenceView, SubjectPlanConsumer
from strategies.earnings_calendar_planning import (
    earnings_calendar_resolved_field_requirements,
    earnings_demand,
)
from strategies.knowledge_contracts import KnowledgeMapping
from strategy_runtime.adapters import build_migrated_strategy_registry
from strategy_runtime.adapters.earnings_calendar_subject_first import (
    build_earnings_calendar_subject_preparation_binding,
)
from strategy_runtime.context import RuntimeContext
from strategy_runtime.contract import (
    NO_LIFECYCLE,
    DataRequirement,
    OutputKind,
    RequirementCategory,
    StrategyContract,
    StructureKind,
)
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.market_data_planning import resolution_policy_for_capabilities
from strategy_runtime.orchestration import (
    CutoverPolicy,
    SubjectAcquisitionAccess,
    TouchedResultFulfillment,
    _observations_relevant_to,
    build_subject_acquisition_access,
    prepare_subject_shadow_knowledge,
    refresh_with_shadow,
    touched_observations,
)
from strategy_runtime.persistence import LatestResultRepository
from strategy_runtime.registry import StrategyRegistry
from strategy_runtime.result import (
    EvaluationState,
    RowType,
    UniversalScreeningResult,
    compute_observation_id,
)
from strategy_runtime.subject_preparation import (
    SubjectPreparationBinding,
    SubjectPreparationRegistry,
)
from strategy_runtime.values import TypedValue
from tests.market_data.test_fulfillment import CAPABILITY, provider, request, service
from tests.screening.test_live_adapters import MultiExpirationFixtureProvider
from tests.strategy_runtime.test_service import InMemoryLatestResultRepository

NOW = datetime(2026, 8, 6, 15, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _FrozenClock:
    """A truly frozen clock -- the same reading on every call, mirroring
    asa/scheduled_screening.py's own _FrozenCycleClock: legacy adapters
    and subject-first preparation must see the exact same ``now`` for
    their own request-identity-affecting timestamps to actually agree
    (SPRINT-013 S13-03B's own established rationale, reused here for the
    shadow path).
    """

    value: datetime

    def now(self) -> datetime:
        return self.value


def _repository() -> LatestResultRepository:
    return InMemoryLatestResultRepository()


# ---------------------------------------------------------------------------
# Synthetic fixtures (mirrors tests/screening/test_subject_planning.py's own
# "everything synthetic" philosophy) for the generic dispatch-mechanics tests.
# ---------------------------------------------------------------------------


def _no_derived_facts(
    _facts: tuple[CanonicalFact, ...]
) -> tuple[DerivedFactRequest, ...] | UnknownReason:
    return ()


@dataclass(frozen=True, slots=True)
class _SyntheticPayload:
    marker: str


def _synthetic_payload(
    _facts: tuple[CanonicalFact, ...], _derived: DerivedFactSet
) -> _SyntheticPayload:
    return _SyntheticPayload("ok")


def _synthetic_demand() -> CapabilityDemand:
    return CapabilityDemand(CAPABILITY, ("last",), NOW, NOW, required=True)


def _synthetic_prepare_knowledge_mapping(
    _snapshot: object,
    _projected_evidence: ResolvedEvidenceView,
    _selections: tuple[tuple[str, object], ...],
    _subject: str,
) -> KnowledgeMapping[_SyntheticPayload] | UnknownReason:
    return KnowledgeMapping(
        canonical_fact_requests=(),
        compute_derived_fact_requests=_no_derived_facts,
        build_payload=_synthetic_payload,
    )


_SYNTHETIC_STRATEGY_ID = "synthetic-strategy"
_SYNTHETIC_RESOLUTION_POLICY = {CAPABILITY: ResolutionPolicy("v1", ("primary",), 3600, ("last",))}


def _synthetic_contract() -> StrategyContract:
    return StrategyContract(
        strategy_id=_SYNTHETIC_STRATEGY_ID,
        version="1.0.0",
        category="synthetic",
        description="synthetic strategy for orchestration dispatch tests",
        requirements=(DataRequirement(RequirementCategory.CUSTOM, identifier="synthetic"),),
        lifecycle=NO_LIFECYCLE,
        structure=StructureKind.NONE,
        outputs=(OutputKind.METRICS,),
        capabilities=(),
    )


def _synthetic_legacy_result(
    *,
    verdict: str = "PASS",
    symbol: str = "AAPL",
    metrics: dict[str, TypedValue] | None = None,
) -> UniversalScreeningResult:
    return UniversalScreeningResult(
        strategy_id=_SYNTHETIC_STRATEGY_ID,
        strategy_version="1.0.0",
        symbol=symbol,
        observation_id=compute_observation_id("run-1", _SYNTHETIC_STRATEGY_ID, symbol),
        opportunity_id=None,
        row_type=RowType.RESULT,
        verdict=verdict,
        evaluation_state=EvaluationState.PASS,
        lifecycle_stage=None,
        recommendation_state=None,
        data_quality=None,
        metrics=(
            metrics if metrics is not None else {"synthetic_metric": TypedValue.of_string(verdict)}
        ),
        economics={},
        blockers=(),
        warnings=(),
        provenance=(),
        observed_at=NOW,
    )


def _synthetic_legacy_registry(
    result_builder: Callable[[RuntimeContext], UniversalScreeningResult] | None = None,
) -> StrategyRegistry[UniversalScreeningResult]:
    contract = _synthetic_contract()

    def _adapter(context: RuntimeContext) -> UniversalScreeningResult:
        if result_builder is not None:
            return result_builder(context)
        return _synthetic_legacy_result(symbol=context.subject)

    return StrategyRegistry(((contract, _adapter),))


def _plan(fulfillment: CapabilityFulfillmentService) -> SubjectAcquisitionPlan:
    return SubjectAcquisitionPlan(
        "AAPL",
        fulfillment,
        attempt_repository=InMemoryAcquisitionAttemptRepository(),
        plan_id="cycle-1:AAPL",
        clock=_FrozenClock(NOW),
        maximum_attempts_per_request=2,
    )


def _fake_observation(
    *,
    capability: MarketCapability,
    effective_time: datetime = NOW,
    observation_id: str = "obs-1",
) -> MarketObservation:
    """A lightweight duck-typed stand-in (mirrors tests/strategy_runtime/
    test_refresh_integrity_regressions.py's own ``_observation`` helper)
    -- _observations_relevant_to only ever reads ``.capability`` off each
    element, so nothing else needs to be real.
    """
    return cast(
        MarketObservation,
        SimpleNamespace(
            capability=capability, effective_time=effective_time, observation_id=observation_id
        ),
    )


def _single_capability_registry(
    strategy_id: str, capability: MarketCapability
) -> StrategyRegistry[UniversalScreeningResult]:
    contract = StrategyContract(
        strategy_id=strategy_id,
        version="1.0.0",
        category="synthetic",
        description="capability-scoped synthetic strategy for the observations filter test",
        requirements=(
            DataRequirement(RequirementCategory.MARKET_DATA, capabilities=(capability,)),
        ),
        lifecycle=NO_LIFECYCLE,
        structure=StructureKind.NONE,
        outputs=(OutputKind.METRICS,),
    )
    def _unused_adapter(_context: RuntimeContext) -> UniversalScreeningResult:
        raise NotImplementedError("adapter unused by this test")

    return StrategyRegistry(((contract, _unused_adapter),))


class TestObservationsRelevantToFilter:
    """Architect checkpoint: sixteenth review, "if the existing broad
    observations callback causes cross-strategy shadow evidence to
    contaminate their temporal metadata, fix that at the generic
    orchestration/evidence boundary rather than accepting the
    difference." refresh_with_shadow() now scopes the caller-supplied
    ``observations`` callback to only the capabilities ``strategy_id``
    itself declares before forwarding it into refresh() -- both
    production roots' own shared raw fulfillment service means an
    unfiltered callback would otherwise let a different strategy's own
    irrelevant evidence (e.g. subject-first shadow preparation's own
    contribution for an entirely different, unrequested strategy) shift
    this strategy's own temporal metadata.
    """

    def test_irrelevant_capability_observations_are_excluded(self) -> None:
        registry = _single_capability_registry("scoped", MarketCapability.REAL_TIME_QUOTE_V1)
        relevant = _fake_observation(
            capability=MarketCapability.REAL_TIME_QUOTE_V1, observation_id="relevant"
        )
        irrelevant = _fake_observation(
            capability=MarketCapability.OPTION_CHAIN_V1, observation_id="irrelevant"
        )

        scoped = _observations_relevant_to("scoped", registry, lambda: (relevant, irrelevant))

        assert scoped() == (relevant,)

    def test_relevant_observations_pass_through_unchanged_regardless_of_order(self) -> None:
        registry = _single_capability_registry("scoped", MarketCapability.REAL_TIME_QUOTE_V1)
        first = _fake_observation(
            capability=MarketCapability.REAL_TIME_QUOTE_V1, observation_id="first"
        )
        second = _fake_observation(
            capability=MarketCapability.REAL_TIME_QUOTE_V1, observation_id="second"
        )

        scoped = _observations_relevant_to("scoped", registry, lambda: (first, second))

        assert scoped() == (first, second)

    def test_no_relevant_observations_yields_an_empty_tuple(self) -> None:
        registry = _single_capability_registry("scoped", MarketCapability.REAL_TIME_QUOTE_V1)
        irrelevant = _fake_observation(capability=MarketCapability.OPTION_CHAIN_V1)

        scoped = _observations_relevant_to("scoped", registry, lambda: (irrelevant,))

        assert scoped() == ()

    def test_filter_is_re_evaluated_on_every_call_not_cached(self) -> None:
        """observations() is a callback, not an already-computed tuple
        (strategy_runtime.service.refresh's own docstring reason: the
        underlying evidence does not exist until the adapter has actually
        run) -- the wrapped, scoped callback must preserve that, calling
        the caller's own ``observations`` fresh every time it is invoked,
        never caching a first result.
        """
        registry = _single_capability_registry("scoped", MarketCapability.REAL_TIME_QUOTE_V1)
        calls = 0

        def _observations() -> tuple[MarketObservation, ...]:
            nonlocal calls
            calls += 1
            return (_fake_observation(capability=MarketCapability.REAL_TIME_QUOTE_V1),)

        scoped = _observations_relevant_to("scoped", registry, _observations)
        scoped()
        scoped()

        assert calls == 2


class TestTouchedResultFulfillment:
    """Architect checkpoint: seventeenth review -- a tracker records only
    what it itself returns to its own caller, including a plan-cache hit,
    never anything a DIFFERENT consumer sharing the same underlying plan
    separately resolved. Subject-first shadow preparation resolves
    directly through SubjectAcquisitionPlan.resolve() (screening.
    subject_planning.run_subject_plan's own call path), never through any
    PlanBackedFulfillment/tracker at all -- so a tracker built for one
    pair's own legacy execution never sees shadow preparation's own
    contribution, by construction, regardless of capability overlap.
    """

    def test_records_nothing_a_different_consumer_resolved_directly_through_the_plan(
        self,
    ) -> None:
        fulfillment, _ = service(provider("primary"))
        plan = _plan(fulfillment)
        tracker = TouchedResultFulfillment(PlanBackedFulfillment(plan))

        plan.resolve(request())  # a different consumer's own direct resolve()

        assert tracker.touched == []

    def test_records_its_own_fresh_resolve(self) -> None:
        fulfillment, _ = service(provider("primary"))
        plan = _plan(fulfillment)
        tracker = TouchedResultFulfillment(PlanBackedFulfillment(plan))

        result = tracker.fulfill(request())

        assert tracker.touched == [result]

    def test_records_a_plan_cache_hit_too(self) -> None:
        fulfillment, budgets = service(provider("primary"))
        plan = _plan(fulfillment)
        tracker = TouchedResultFulfillment(PlanBackedFulfillment(plan))
        # Already resolved by a different consumer sharing this plan (an
        # earlier pair, or shadow preparation) before this tracker's own
        # first call.
        already_resolved = plan.resolve(request())

        via_tracker = tracker.fulfill(request())

        assert via_tracker is already_resolved
        assert tracker.touched == [already_resolved]
        assert len(budgets.accounting) == 1  # confirms this really was a cache hit

    def test_touched_observations_flattens_every_recorded_results_own_observations(
        self,
    ) -> None:
        fulfillment, _ = service(provider("primary"))
        plan = _plan(fulfillment)
        tracker = TouchedResultFulfillment(PlanBackedFulfillment(plan))
        result = tracker.fulfill(request())

        assert touched_observations(tracker) == result.observations

    def test_touched_observations_is_empty_when_nothing_was_ever_touched(self) -> None:
        fulfillment, _ = service(provider("primary"))
        plan = _plan(fulfillment)
        tracker = TouchedResultFulfillment(PlanBackedFulfillment(plan))

        assert touched_observations(tracker) == ()


class TestBuildSubjectAcquisitionAccess:
    def test_wraps_fulfillment_in_exactly_one_plan_and_plan_backed_fulfillment(self) -> None:
        fulfillment, _ = service(provider("primary"))
        access = build_subject_acquisition_access(
            "AAPL",
            fulfillment,
            attempt_repository=InMemoryAcquisitionAttemptRepository(),
            plan_id="cycle-1:AAPL",
            clock=_FrozenClock(NOW),
        )
        assert isinstance(access, SubjectAcquisitionAccess)
        assert isinstance(access.plan, SubjectAcquisitionPlan)
        assert isinstance(access.plan_backed_fulfillment, PlanBackedFulfillment)
        assert access.plan_backed_fulfillment.plan is access.plan
        assert access.plan.subject == "AAPL"
        assert access.plan.plan_id == "cycle-1:AAPL"


class TestPrepareSubjectShadowKnowledge:
    def test_empty_registry_returns_empty_mapping(self) -> None:
        fulfillment, _ = service(provider("primary"))
        plan = _plan(fulfillment)
        registry: SubjectPreparationRegistry[object] = SubjectPreparationRegistry(())

        result = prepare_subject_shadow_knowledge(
            plan,
            NOW,
            registry,
            subject="AAPL",
            provider_metadata=(),
            resolution_policy_by_capability={},
        )

        assert result == {}

    def test_runs_once_per_registered_strategy_id(self) -> None:
        consumer = SubjectPlanConsumer(
            _SYNTHETIC_STRATEGY_ID, (_synthetic_demand(),), lambda _evidence: DemandExpansion()
        )

        def _unreachable_adapter_builder(
            _knowledge: Mapping[str, ReadOnlyStrategyInput[object]],
        ) -> Callable[[RuntimeContext], UniversalScreeningResult]:
            raise AssertionError("never called by this test")

        binding: SubjectPreparationBinding[object] = SubjectPreparationBinding(
            consumer=consumer,
            prepare_knowledge_mapping=_synthetic_prepare_knowledge_mapping,
            build_shadow_adapter=_unreachable_adapter_builder,
        )
        registry: SubjectPreparationRegistry[object] = SubjectPreparationRegistry(
            ((_SYNTHETIC_STRATEGY_ID, binding),)
        )
        fulfillment, budgets = service(provider("primary"))
        plan = _plan(fulfillment)

        result = prepare_subject_shadow_knowledge(
            plan,
            NOW,
            registry,
            subject="AAPL",
            provider_metadata=(provider("primary").metadata,),
            resolution_policy_by_capability=_SYNTHETIC_RESOLUTION_POLICY,
        )

        entry = result[_SYNTHETIC_STRATEGY_ID]
        assert set(result) == {_SYNTHETIC_STRATEGY_ID}
        assert isinstance(entry, ReadOnlyStrategyInput)
        assert isinstance(entry.payload, _SyntheticPayload)
        assert entry.payload.marker == "ok"
        # One bootstrap demand, resolved once -- proves this ran through
        # the real plan/fulfillment, not a stub.
        assert len(budgets.accounting) == 1

    def test_consumers_share_one_snapshot_and_one_equivalent_request(self) -> None:
        def adapter_builder(
            _knowledge: Mapping[str, ReadOnlyStrategyInput[object]],
        ) -> Callable[[RuntimeContext], UniversalScreeningResult]:
            raise AssertionError("not evaluated during preparation")

        entries = tuple(
            (
                strategy_id,
                SubjectPreparationBinding(
                    SubjectPlanConsumer(
                        strategy_id,
                        (_synthetic_demand(),),
                        lambda _evidence: DemandExpansion(),
                    ),
                    _synthetic_prepare_knowledge_mapping,
                    adapter_builder,
                ),
            )
            for strategy_id in ("consumer-a", "consumer-b")
        )
        fulfillment, budgets = service(provider("primary"))
        result = prepare_subject_shadow_knowledge(
            _plan(fulfillment),
            NOW,
            SubjectPreparationRegistry(entries),
            subject="AAPL",
            provider_metadata=(provider("primary").metadata,),
            resolution_policy_by_capability=_SYNTHETIC_RESOLUTION_POLICY,
        )

        first = result["consumer-a"]
        second = result["consumer-b"]
        assert isinstance(first, ReadOnlyStrategyInput)
        assert isinstance(second, ReadOnlyStrategyInput)
        assert first.snapshot_id == second.snapshot_id
        assert first.snapshot_digest == second.snapshot_digest
        assert len(budgets.accounting) == 1


def _synthetic_knowledge_input(symbol: str) -> ReadOnlyStrategyInput[object]:
    return ReadOnlyStrategyInput(
        snapshot_id="snapshot-1",
        snapshot_digest="digest-1",
        effective_time=NOW,
        canonical_facts=(),
        derived_facts=DerivedFactSet(()),
        payload=_SyntheticPayload("ok"),
    )


def _shadow_adapter_matching_legacy(
    _knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[object]],
) -> Callable[[RuntimeContext], UniversalScreeningResult]:
    def _adapter(context: RuntimeContext) -> UniversalScreeningResult:
        return _synthetic_legacy_result(symbol=context.subject)

    return _adapter


def _shadow_adapter_mismatched_verdict(
    _knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[object]],
) -> Callable[[RuntimeContext], UniversalScreeningResult]:
    def _adapter(context: RuntimeContext) -> UniversalScreeningResult:
        return _synthetic_legacy_result(symbol=context.subject, verdict="WATCH")

    return _adapter


def _shadow_adapter_raises(
    _knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[object]],
) -> Callable[[RuntimeContext], UniversalScreeningResult]:
    def _adapter(_context: RuntimeContext) -> UniversalScreeningResult:
        raise RuntimeError("synthetic shadow adapter failure")

    return _adapter


def _shadow_adapter_with_metric_legacy_lacks(
    _knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[object]],
) -> Callable[[RuntimeContext], UniversalScreeningResult]:
    """Legacy's own single ``synthetic_metric`` key survives unchanged,
    but the shadow result carries one extra key legacy never emitted --
    the old intersection-only metrics comparison would have called this a
    match; exact equality (Architect checkpoint: fifteenth review,
    corrective item 1) must not.
    """

    def _adapter(context: RuntimeContext) -> UniversalScreeningResult:
        return _synthetic_legacy_result(
            symbol=context.subject,
            metrics={
                "synthetic_metric": TypedValue.of_string("PASS"),
                "shadow_only_metric": TypedValue.of_string("extra"),
            },
        )

    return _adapter


def _shadow_adapter_missing_metric_legacy_has(
    _knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[object]],
) -> Callable[[RuntimeContext], UniversalScreeningResult]:
    """The shadow result carries a non-empty metrics namespace (so
    validate_result's own "declared outputs emitted" check still passes),
    but never the specific key legacy emitted -- a silently dropped
    metric, which exact equality must catch as a mismatch rather than
    letting an intersection-only comparison treat an entirely
    non-overlapping metrics dict as agreement-by-omission.
    """

    def _adapter(context: RuntimeContext) -> UniversalScreeningResult:
        return _synthetic_legacy_result(
            symbol=context.subject,
            metrics={"unrelated_metric": TypedValue.of_string("x")},
        )

    return _adapter


def _shadow_adapter_wrong_symbol(
    _knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[object]],
) -> Callable[[RuntimeContext], UniversalScreeningResult]:
    """A malformed shadow adapter that reports a *different* subject than
    the one it was asked to evaluate -- exactly the "compares as match
    against the wrong pair" failure mode Architect checkpoint (fifteenth
    review, corrective item 4) named.
    """

    def _adapter(_context: RuntimeContext) -> UniversalScreeningResult:
        return _synthetic_legacy_result(symbol="MSFT")

    return _adapter


def _shadow_adapter_empty_metrics(
    _knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[object]],
) -> Callable[[RuntimeContext], UniversalScreeningResult]:
    """A malformed shadow adapter that never populates its declared
    OutputKind.METRICS namespace at all -- validate_result() must catch
    this exactly as strategy_runtime.execution's own generic runtime
    validation already would for a legacy adapter (Architect checkpoint:
    fifteenth review, corrective item 4: "reuse it rather than
    duplicating them").
    """

    def _adapter(context: RuntimeContext) -> UniversalScreeningResult:
        return _synthetic_legacy_result(symbol=context.subject, metrics={})

    return _adapter


def _synthetic_shadow_registry(
    build_shadow_adapter: Callable[
        [Mapping[str, ReadOnlyStrategyInput[object]]],
        Callable[[RuntimeContext], UniversalScreeningResult],
    ],
) -> SubjectPreparationRegistry[object]:
    consumer = SubjectPlanConsumer(_SYNTHETIC_STRATEGY_ID, (), lambda _evidence: DemandExpansion())
    binding: SubjectPreparationBinding[object] = SubjectPreparationBinding(
        consumer=consumer,
        prepare_knowledge_mapping=_synthetic_prepare_knowledge_mapping,
        build_shadow_adapter=build_shadow_adapter,
    )
    return SubjectPreparationRegistry(((_SYNTHETIC_STRATEGY_ID, binding),))


class TestRefreshWithShadowDispatch:
    """strategy_runtime.orchestration.refresh_with_shadow's own generic
    dispatch mechanics -- proven against synthetic, non-Earnings
    registries so this layer's own control flow (match/mismatch/
    shadow_unknown/shadow_error/not_shadowed, persist-legacy-only) is
    proven independently of any real financial data.
    """

    def test_no_shadow_registry_returns_none_diagnostic(self) -> None:
        result, diagnostic = refresh_with_shadow(
            _synthetic_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
        )
        assert diagnostic is None
        assert result.strategy_id == _SYNTHETIC_STRATEGY_ID
        assert result.verdict == "PASS"

    def test_unregistered_strategy_id_returns_none_diagnostic(self) -> None:
        """Not shadow-registered at all -- treated the same as no shadow
        registry supplied (test_no_shadow_registry_returns_none_diagnostic):
        no diagnostic is fabricated for a strategy no binding ever covers.
        """
        empty_shadow_registry: SubjectPreparationRegistry[object] = SubjectPreparationRegistry(())
        _result, diagnostic = refresh_with_shadow(
            _synthetic_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            shadow_registry=empty_shadow_registry,
            shadow_knowledge_by_subject={},
            now=NOW,
        )
        assert diagnostic is None

    def test_registered_but_not_yet_prepared_knowledge_is_not_shadowed(self) -> None:
        """strategy_id IS registered in shadow_registry, but this subject's
        own shadow knowledge was never prepared for it (e.g.
        prepare_subject_shadow_knowledge was never called, or its own
        result dict simply has no entry) -- recorded as its own explicit
        "not_shadowed" diagnostic, distinct from "no shadow binding at
        all" (which returns no diagnostic, see the test above).
        """
        shadow_registry = _synthetic_shadow_registry(_shadow_adapter_matching_legacy)
        _result, diagnostic = refresh_with_shadow(
            _synthetic_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            shadow_registry=shadow_registry,
            shadow_knowledge_by_subject={},
            now=NOW,
        )
        assert diagnostic is not None
        assert diagnostic.status == "not_shadowed"

    def test_matching_shadow_result_is_reported_as_a_match(self) -> None:
        shadow_registry = _synthetic_shadow_registry(_shadow_adapter_matching_legacy)
        knowledge = {_SYNTHETIC_STRATEGY_ID: _synthetic_knowledge_input("AAPL")}
        _result, diagnostic = refresh_with_shadow(
            _synthetic_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            shadow_registry=shadow_registry,
            shadow_knowledge_by_subject=knowledge,
            now=NOW,
        )
        assert diagnostic is not None
        assert diagnostic.status == "match"
        assert diagnostic.is_match
        assert diagnostic.mismatched_fields == ()

    def test_mismatched_verdict_is_reported_with_the_mismatched_field_named(self) -> None:
        shadow_registry = _synthetic_shadow_registry(_shadow_adapter_mismatched_verdict)
        knowledge = {_SYNTHETIC_STRATEGY_ID: _synthetic_knowledge_input("AAPL")}
        result, diagnostic = refresh_with_shadow(
            _synthetic_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            shadow_registry=shadow_registry,
            shadow_knowledge_by_subject=knowledge,
            now=NOW,
        )
        assert diagnostic is not None
        assert diagnostic.status == "mismatch"
        assert not diagnostic.is_match
        assert "verdict" in diagnostic.mismatched_fields
        assert diagnostic.legacy_verdict == "PASS" == result.verdict
        assert diagnostic.shadow_verdict == "WATCH"

    def test_shadow_metric_legacy_lacks_is_a_mismatch_not_a_silent_match(self) -> None:
        """Architect checkpoint: fifteenth review, corrective item 1 --
        the old intersection-only comparison would have called this a
        match (legacy's own one shared key agrees); exact equality must
        not, since the shadow result silently carries a metric legacy
        never emitted.
        """
        shadow_registry = _synthetic_shadow_registry(_shadow_adapter_with_metric_legacy_lacks)
        knowledge = {_SYNTHETIC_STRATEGY_ID: _synthetic_knowledge_input("AAPL")}
        _result, diagnostic = refresh_with_shadow(
            _synthetic_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            shadow_registry=shadow_registry,
            shadow_knowledge_by_subject=knowledge,
            now=NOW,
        )
        assert diagnostic is not None
        assert diagnostic.status == "mismatch"
        assert "metrics" in diagnostic.mismatched_fields

    def test_legacy_metric_shadow_lacks_is_a_mismatch_not_a_silent_match(self) -> None:
        """The reverse direction of the same corrective fix: a legacy
        metric key the shadow result never emits at all (the shadow's own
        metrics dict is entirely disjoint from legacy's) must also be
        caught, never treated as agreement-by-omission.
        """
        shadow_registry = _synthetic_shadow_registry(_shadow_adapter_missing_metric_legacy_has)
        knowledge = {_SYNTHETIC_STRATEGY_ID: _synthetic_knowledge_input("AAPL")}
        _result, diagnostic = refresh_with_shadow(
            _synthetic_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            shadow_registry=shadow_registry,
            shadow_knowledge_by_subject=knowledge,
            now=NOW,
        )
        assert diagnostic is not None
        assert diagnostic.status == "mismatch"
        assert "metrics" in diagnostic.mismatched_fields

    def test_shadow_unknown_reason_is_recorded_not_converted_to_an_exception(self) -> None:
        shadow_registry = _synthetic_shadow_registry(_shadow_adapter_matching_legacy)
        knowledge: dict[str, ReadOnlyStrategyInput[object] | UnknownReason] = {
            _SYNTHETIC_STRATEGY_ID: UnknownReason(
                "synthetic_gap", demand_ids=("demand-a", "demand-b")
            )
        }
        result, diagnostic = refresh_with_shadow(
            _synthetic_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            shadow_registry=shadow_registry,
            shadow_knowledge_by_subject=knowledge,
            now=NOW,
        )
        assert diagnostic is not None
        assert diagnostic.status == "shadow_unknown"
        assert diagnostic.shadow_unknown_code == "synthetic_gap"
        # Architect checkpoint: fifteenth review, corrective item 2 --
        # demand_ids must survive unchanged, not just the reason code.
        assert diagnostic.shadow_unknown_demand_ids == ("demand-a", "demand-b")
        # The legacy, authoritative result is entirely unaffected.
        assert result.verdict == "PASS"

    def test_wrong_symbol_shadow_result_is_a_mismatch_never_a_false_match(self) -> None:
        """Architect checkpoint: fifteenth review, corrective item 4 --
        a malformed shadow result reporting a different pair's own
        identity must never compare as a match; envelope identity
        (strategy_id/strategy_version/symbol/row_type) is part of the
        same comparison every other semantic field goes through.
        """
        shadow_registry = _synthetic_shadow_registry(_shadow_adapter_wrong_symbol)
        knowledge = {_SYNTHETIC_STRATEGY_ID: _synthetic_knowledge_input("AAPL")}
        _result, diagnostic = refresh_with_shadow(
            _synthetic_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            shadow_registry=shadow_registry,
            shadow_knowledge_by_subject=knowledge,
            now=NOW,
        )
        assert diagnostic is not None
        assert diagnostic.status == "mismatch"
        assert "symbol" in diagnostic.mismatched_fields

    def test_shadow_result_failing_declared_output_validation_is_a_shadow_error(self) -> None:
        """Architect checkpoint: fifteenth review, corrective item 4 --
        the shadow result is run through the same generic
        strategy_runtime.validation.validate_result() every legacy
        adapter's own execution already goes through; a shadow adapter
        that never populates its declared OutputKind.METRICS namespace is
        isolated as shadow_error, exactly like an unexpected exception,
        never silently compared or propagated.
        """
        shadow_registry = _synthetic_shadow_registry(_shadow_adapter_empty_metrics)
        knowledge = {_SYNTHETIC_STRATEGY_ID: _synthetic_knowledge_input("AAPL")}
        result, diagnostic = refresh_with_shadow(
            _synthetic_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            shadow_registry=shadow_registry,
            shadow_knowledge_by_subject=knowledge,
            now=NOW,
        )
        assert diagnostic is not None
        assert diagnostic.status == "shadow_error"
        assert diagnostic.shadow_error_detail is not None
        assert result.verdict == "PASS"

    def test_shadow_adapter_exception_is_isolated_never_propagated(self) -> None:
        shadow_registry = _synthetic_shadow_registry(_shadow_adapter_raises)
        knowledge = {_SYNTHETIC_STRATEGY_ID: _synthetic_knowledge_input("AAPL")}
        result, diagnostic = refresh_with_shadow(
            _synthetic_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            shadow_registry=shadow_registry,
            shadow_knowledge_by_subject=knowledge,
            now=NOW,
        )
        assert diagnostic is not None
        assert diagnostic.status == "shadow_error"
        assert diagnostic.shadow_error_detail is not None
        assert "synthetic shadow adapter failure" in diagnostic.shadow_error_detail
        # A raising shadow adapter never affects the legacy, authoritative
        # result this function still returns.
        assert result.verdict == "PASS"

    def test_only_the_legacy_result_is_ever_persisted(self) -> None:
        shadow_registry = _synthetic_shadow_registry(_shadow_adapter_mismatched_verdict)
        knowledge = {_SYNTHETIC_STRATEGY_ID: _synthetic_knowledge_input("AAPL")}
        repository = _repository()

        result, diagnostic = refresh_with_shadow(
            _synthetic_legacy_registry(),
            repository,
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            shadow_registry=shadow_registry,
            shadow_knowledge_by_subject=knowledge,
            now=NOW,
        )

        assert diagnostic is not None
        assert diagnostic.shadow_verdict == "WATCH"
        persisted = repository.get_one(_SYNTHETIC_STRATEGY_ID, "AAPL")
        assert persisted is not None
        assert persisted.to_result().verdict == result.verdict == "PASS"


def _raising_legacy_adapter(_context: RuntimeContext) -> UniversalScreeningResult:
    raise AssertionError("legacy adapter must never execute when cutover is authoritative")


def _raising_legacy_registry() -> StrategyRegistry[UniversalScreeningResult]:
    """A legacy registry that fails the test loudly if its own adapter is
    ever actually invoked -- the direct proof that a cut-over strategy's
    authoritative evaluation performs zero legacy execution (Architect
    checkpoint: nineteenth review, "when cutover is enabled, Earnings
    authoritative evaluation must come from the already-prepared ...
    adapter. It must perform zero acquisition of its own").
    """
    return StrategyRegistry(((_synthetic_contract(), _raising_legacy_adapter),))


class TestCutoverPolicy:
    """CutoverPolicy's own membership semantics in isolation (Architect
    checkpoint: nineteenth review, CUTOVER_PASS)."""

    def test_default_empty_policy_is_never_cut_over(self) -> None:
        assert CutoverPolicy().is_cut_over(_SYNTHETIC_STRATEGY_ID) is False

    def test_absent_strategy_id_defaults_to_not_cut_over(self) -> None:
        policy = CutoverPolicy({"some-other-strategy": True})
        assert policy.is_cut_over(_SYNTHETIC_STRATEGY_ID) is False

    def test_registered_true_is_cut_over(self) -> None:
        policy = CutoverPolicy({_SYNTHETIC_STRATEGY_ID: True})
        assert policy.is_cut_over(_SYNTHETIC_STRATEGY_ID) is True

    def test_registered_false_is_the_rollback_state_not_cut_over(self) -> None:
        policy = CutoverPolicy({_SYNTHETIC_STRATEGY_ID: False})
        assert policy.is_cut_over(_SYNTHETIC_STRATEGY_ID) is False


class TestCutoverDispatch:
    """SPRINT-014 S14-PR-05, Architect checkpoint: nineteenth review
    ("CUTOVER_PASS ... implement the already-approved PR-05 cutover
    mechanism") -- refresh_with_shadow()'s own new cutover-authoritative
    branch, proven against the same synthetic registries/adapters
    TestRefreshWithShadowDispatch already established, so this layer's
    control flow is proven independently of any real financial data.
    """

    def test_cut_over_strategy_is_authoritative_from_already_prepared_knowledge(
        self,
    ) -> None:
        # The shadow adapter reports WATCH; the (never-invoked) legacy
        # adapter would report PASS if it ran at all -- proving the
        # returned result really came from the already-prepared knowledge,
        # not from legacy.
        shadow_registry = _synthetic_shadow_registry(_shadow_adapter_mismatched_verdict)
        knowledge = {_SYNTHETIC_STRATEGY_ID: _synthetic_knowledge_input("AAPL")}
        cutover_policy = CutoverPolicy({_SYNTHETIC_STRATEGY_ID: True})

        result, diagnostic = refresh_with_shadow(
            _raising_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            shadow_registry=shadow_registry,
            shadow_knowledge_by_subject=knowledge,
            cutover_policy=cutover_policy,
            now=NOW,
        )

        assert result.verdict == "WATCH"
        # No shadow comparison runs once cutover is authoritative --
        # there is nothing left to compare against (Architect checkpoint:
        # nineteenth review, "do not run both authoritative paths after
        # cutover merely to preserve shadowing").
        assert diagnostic is None

    def test_cut_over_result_is_the_only_thing_persisted(self) -> None:
        shadow_registry = _synthetic_shadow_registry(_shadow_adapter_mismatched_verdict)
        knowledge = {_SYNTHETIC_STRATEGY_ID: _synthetic_knowledge_input("AAPL")}
        cutover_policy = CutoverPolicy({_SYNTHETIC_STRATEGY_ID: True})
        repository = _repository()

        result, _diagnostic = refresh_with_shadow(
            _raising_legacy_registry(),
            repository,
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            shadow_registry=shadow_registry,
            shadow_knowledge_by_subject=knowledge,
            cutover_policy=cutover_policy,
            now=NOW,
        )

        persisted = repository.get_one(_SYNTHETIC_STRATEGY_ID, "AAPL")
        assert persisted is not None
        assert persisted.to_result().verdict == result.verdict == "WATCH"

    def test_cutover_authoritative_path_never_calls_the_observations_callback(self) -> None:
        """The cutover-authoritative path performs zero acquisition of its
        own -- proven directly by supplying an observations callback that
        fails the test if it is ever invoked, rather than asserting on a
        downstream side effect.
        """
        shadow_registry = _synthetic_shadow_registry(_shadow_adapter_matching_legacy)
        knowledge = {_SYNTHETIC_STRATEGY_ID: _synthetic_knowledge_input("AAPL")}
        cutover_policy = CutoverPolicy({_SYNTHETIC_STRATEGY_ID: True})

        def _observations() -> tuple[MarketObservation, ...]:
            raise AssertionError(
                "cutover-authoritative evaluation must never call the caller's "
                "own observations callback"
            )

        result, _diagnostic = refresh_with_shadow(
            _raising_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=_observations,
            shadow_registry=shadow_registry,
            shadow_knowledge_by_subject=knowledge,
            cutover_policy=cutover_policy,
            now=NOW,
        )

        assert result.temporal is None

    def test_unknown_reason_under_cutover_yields_missing_data_never_legacy_execution(
        self,
    ) -> None:
        shadow_registry = _synthetic_shadow_registry(_shadow_adapter_matching_legacy)
        knowledge: dict[str, ReadOnlyStrategyInput[object] | UnknownReason] = {
            _SYNTHETIC_STRATEGY_ID: UnknownReason("synthetic_gap", demand_ids=("demand-a",))
        }
        cutover_policy = CutoverPolicy({_SYNTHETIC_STRATEGY_ID: True})

        result, diagnostic = refresh_with_shadow(
            _raising_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            shadow_registry=shadow_registry,
            shadow_knowledge_by_subject=knowledge,
            cutover_policy=cutover_policy,
            now=NOW,
        )

        assert diagnostic is None
        assert result.evaluation_state == EvaluationState.MISSING_DATA
        assert result.verdict is None
        assert result.opportunity_id is None
        assert result.lifecycle_stage is None
        assert any("synthetic_gap" in blocker for blocker in result.blockers)

    def test_rollback_false_entry_keeps_legacy_authoritative_and_shadow_comparison(
        self,
    ) -> None:
        """A registered-but-False CutoverPolicy entry (the operationally
        reversible rollback state) behaves identically to no cutover_policy
        at all -- legacy stays authoritative and shadow comparison still
        runs, with zero data migration required to reach this state.
        """
        shadow_registry = _synthetic_shadow_registry(_shadow_adapter_matching_legacy)
        knowledge = {_SYNTHETIC_STRATEGY_ID: _synthetic_knowledge_input("AAPL")}
        cutover_policy = CutoverPolicy({_SYNTHETIC_STRATEGY_ID: False})

        result, diagnostic = refresh_with_shadow(
            _synthetic_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            shadow_registry=shadow_registry,
            shadow_knowledge_by_subject=knowledge,
            cutover_policy=cutover_policy,
            now=NOW,
        )

        assert result.verdict == "PASS"
        assert diagnostic is not None
        assert diagnostic.status == "match"

    def test_cut_over_but_no_shadow_knowledge_prepared_falls_back_to_legacy(self) -> None:
        """Cutover is enabled and the strategy is shadow-registered, but
        this subject's own knowledge was never actually prepared for it --
        refresh_with_shadow() falls back to its existing legacy(+optional
        shadow) behavior rather than fabricating an authoritative result
        from nothing.
        """
        shadow_registry = _synthetic_shadow_registry(_shadow_adapter_matching_legacy)
        cutover_policy = CutoverPolicy({_SYNTHETIC_STRATEGY_ID: True})

        result, diagnostic = refresh_with_shadow(
            _synthetic_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            shadow_registry=shadow_registry,
            shadow_knowledge_by_subject={},
            cutover_policy=cutover_policy,
            now=NOW,
        )

        assert result.verdict == "PASS"
        assert diagnostic is not None
        assert diagnostic.status == "not_shadowed"

    def test_cut_over_but_not_shadow_registered_falls_back_to_legacy(self) -> None:
        """Cutover policy names a strategy_id that has no shadow_registry
        binding at all -- there is no already-prepared knowledge to be
        authoritative from, so legacy stays authoritative, exactly as if
        cutover_policy had never been supplied.
        """
        cutover_policy = CutoverPolicy({_SYNTHETIC_STRATEGY_ID: True})

        result, diagnostic = refresh_with_shadow(
            _synthetic_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            cutover_policy=cutover_policy,
            now=NOW,
        )

        assert result.verdict == "PASS"
        assert diagnostic is None

    def test_no_cutover_policy_is_identical_to_todays_pre_cutover_behavior(self) -> None:
        """The absent-cutover_policy default (both production roots always
        pass one, but the parameter itself defaults to None) behaves
        identically to an empty/rollback policy.
        """
        shadow_registry = _synthetic_shadow_registry(_shadow_adapter_matching_legacy)
        knowledge = {_SYNTHETIC_STRATEGY_ID: _synthetic_knowledge_input("AAPL")}

        result, diagnostic = refresh_with_shadow(
            _synthetic_legacy_registry(),
            _repository(),
            _FrozenClock(NOW),
            strategy_id=_SYNTHETIC_STRATEGY_ID,
            symbol="AAPL",
            observations=tuple,
            shadow_registry=shadow_registry,
            shadow_knowledge_by_subject=knowledge,
            now=NOW,
        )

        assert result.verdict == "PASS"
        assert diagnostic is not None
        assert diagnostic.status == "match"


# ---------------------------------------------------------------------------
# Real, end-to-end Earnings Calendar proof against a shared plan, reusing
# tests/screening/test_live_adapters.py's own proven multi-expiration
# fixture provider.
# ---------------------------------------------------------------------------

_BURST_LIMIT = 30


def _build_shared_fulfillment(
    provider_cls: type[MultiExpirationFixtureProvider] = MultiExpirationFixtureProvider,
    *,
    provider_clock: _FrozenClock,
    scenario: FixtureScenario | None = None,
) -> tuple[CapabilityFulfillmentService, ProviderRegistry, CapabilityRegistry]:
    """One CapabilityFulfillmentService against a real, multi-expiration,
    multi-strike, multi-capability fixture -- the exact same provider
    shape screening/live_adapters.py's own tests already prove all three
    migrated strategies succeed against. burst_limit is raised generously
    (matching tests/screening/test_live_adapters.py's own _fulfillment()
    override for a multi-acquisition run) since a shared subject plan can
    issue several distinct requests -- generous enough that a single
    frozen clock reading for every request in this test never collides on
    RequestBudgetPolicy's own burst key, so this stays the *same* frozen
    ``now`` the strategy-level clock uses (never a separately-advancing
    provider clock): every observation's own recorded_time must never
    exceed the sealed snapshot's own as_of (MarketSnapshot's own
    invariant), which only holds for certain when both clocks read
    identically.
    """
    from market_data import load_market_data_config

    config = load_market_data_config({})
    (fixture_config,) = tuple(item for item in config.providers if item.enabled)
    fixture_config = dataclasses.replace(
        fixture_config,
        request_budget=dataclasses.replace(
            fixture_config.request_budget, burst_limit=_BURST_LIMIT
        ),
    )
    budget_manager = build_request_budget_manager((fixture_config,), provider_clock)
    fixture_provider = provider_cls(
        fixture_config,
        ProviderDependencies(object(), provider_clock, budget_manager),
        scenario or FixtureScenario(),
    )
    provider_registry = ProviderRegistry((fixture_provider,))
    capability_registry = build_capability_registry(provider_registry)
    fulfillment = CapabilityFulfillmentService(
        provider_registry, capability_registry, budget_manager
    )
    return fulfillment, provider_registry, capability_registry


@dataclasses.dataclass(frozen=True, slots=True)
class _EarningsCalendarSharedPlanFixture:
    fulfillment: CapabilityFulfillmentService
    access: SubjectAcquisitionAccess
    shadow_registry: SubjectPreparationRegistry[object]
    resolution_policy_by_capability: dict[MarketCapability, ResolutionPolicy]
    provider_metadata: tuple[ProviderMetadata, ...]


def _build_earnings_calendar_fixture(
    *, symbol: str = "AAPL", scenario: FixtureScenario | None = None
) -> _EarningsCalendarSharedPlanFixture:
    fulfillment, provider_registry, capability_registry = _build_shared_fulfillment(
        provider_clock=_FrozenClock(NOW), scenario=scenario or FixtureScenario()
    )
    access = build_subject_acquisition_access(
        symbol,
        fulfillment,
        attempt_repository=InMemoryAcquisitionAttemptRepository(),
        plan_id=f"cycle-1:{symbol}",
        clock=_FrozenClock(NOW),
    )
    shadow_registry: SubjectPreparationRegistry[object] = SubjectPreparationRegistry(
        (("earnings_calendar", build_earnings_calendar_subject_preparation_binding(NOW)),)
    )
    resolution_policy = resolution_policy_for_capabilities(
        capability_registry, earnings_calendar_resolved_field_requirements()
    )
    return _EarningsCalendarSharedPlanFixture(
        fulfillment,
        access,
        shadow_registry,
        resolution_policy,
        provider_registry.metadata(),
    )


class TestEarningsCalendarSharedPlanEndToEnd:
    """Real, end-to-end proof of the mandatory provider-call-count
    properties (Architect checkpoint: fourteenth review, "provider-call
    proof is mandatory") against a real, multi-capability
    CapabilityFulfillmentService -- never a hand-scripted fake.
    """

    def test_subject_first_then_legacy_earnings_adds_zero_provider_calls(self) -> None:
        fixture = _build_earnings_calendar_fixture()

        knowledge = prepare_subject_shadow_knowledge(
            fixture.access.plan,
            NOW,
            fixture.shadow_registry,
            subject="AAPL",
            provider_metadata=fixture.provider_metadata,
            resolution_policy_by_capability=fixture.resolution_policy_by_capability,
            capability_reducer_by_capability={
                MarketCapability.OPTION_CHAIN_V1: reduce_option_chain_results
            },
        )
        assert isinstance(knowledge["earnings_calendar"], ReadOnlyStrategyInput)
        calls_after_subject_first_prep = len(fixture.fulfillment.call_log)
        assert calls_after_subject_first_prep > 0

        legacy_registry = build_migrated_strategy_registry(fixture.access.plan_backed_fulfillment)
        result, diagnostic = refresh_with_shadow(
            legacy_registry,
            _repository(),
            _FrozenClock(NOW),
            strategy_id="earnings_calendar",
            symbol="AAPL",
            observations=tuple,
            shadow_registry=fixture.shadow_registry,
            shadow_knowledge_by_subject=knowledge,
            now=NOW,
        )

        assert result.evaluation_state in {EvaluationState.PASS, EvaluationState.NO_SIGNAL}
        assert len(fixture.fulfillment.call_log) == calls_after_subject_first_prep, (
            "legacy Earnings running through the same PlanBackedFulfillment after "
            "subject-first preparation made at least one additional provider call -- "
            "a request-identity mismatch, not acceptable shadow overhead"
        )
        assert diagnostic is not None
        assert diagnostic.status == "match", diagnostic.mismatched_fields
        assert diagnostic.shadow_snapshot_id is not None
        assert diagnostic.shadow_snapshot_digest is not None

    def test_reversed_order_legacy_first_then_subject_first_same_total_calls(self) -> None:
        """Order independence: legacy Earnings running *first*, then
        subject-first preparation running second against the same plan,
        must reach the same total call count as the reverse order proven
        above -- neither ordering may re-issue an equivalent request.
        """
        fixture = _build_earnings_calendar_fixture()
        legacy_registry = build_migrated_strategy_registry(fixture.access.plan_backed_fulfillment)

        legacy_result, _ = refresh_with_shadow(
            legacy_registry,
            _repository(),
            _FrozenClock(NOW),
            strategy_id="earnings_calendar",
            symbol="AAPL",
            observations=tuple,
        )
        calls_after_legacy = len(fixture.fulfillment.call_log)
        assert calls_after_legacy > 0
        assert legacy_result.evaluation_state in {EvaluationState.PASS, EvaluationState.NO_SIGNAL}

        knowledge = prepare_subject_shadow_knowledge(
            fixture.access.plan,
            NOW,
            fixture.shadow_registry,
            subject="AAPL",
            provider_metadata=fixture.provider_metadata,
            resolution_policy_by_capability=fixture.resolution_policy_by_capability,
            capability_reducer_by_capability={
                MarketCapability.OPTION_CHAIN_V1: reduce_option_chain_results
            },
        )

        assert isinstance(knowledge["earnings_calendar"], ReadOnlyStrategyInput)
        assert len(fixture.fulfillment.call_log) == calls_after_legacy, (
            "subject-first preparation running after legacy Earnings made at least one "
            "additional provider call for an equivalent request"
        )

    def test_shared_provider_failure_is_exhausted_once_not_retried_independently(
        self,
    ) -> None:
        """A shared outage stays one outage: both the subject-first path
        and legacy Earnings consume the plan's own single bounded-retry
        outcome for an identical failed request -- shadow execution must
        never trigger a second, independent retry sequence merely because
        two evaluators exist.
        """
        scenario = FixtureScenario(
            failures=((MarketCapability.EARNINGS_CALENDAR_V1, ProviderErrorCode.NO_DATA),)
        )
        fixture = _build_earnings_calendar_fixture(scenario=scenario)

        knowledge = prepare_subject_shadow_knowledge(
            fixture.access.plan,
            NOW,
            fixture.shadow_registry,
            subject="AAPL",
            provider_metadata=fixture.provider_metadata,
            resolution_policy_by_capability=fixture.resolution_policy_by_capability,
            capability_reducer_by_capability={
                MarketCapability.OPTION_CHAIN_V1: reduce_option_chain_results
            },
        )
        # A missing confirmed earnings date is a genuine, expected data
        # gap -- typed UnknownReason, never an exception.
        earnings_unknown = knowledge["earnings_calendar"]
        assert isinstance(earnings_unknown, UnknownReason)
        assert earnings_unknown.code == "missing_earnings_date"
        assert earnings_unknown.demand_ids == (earnings_demand(NOW).demand_id,)
        calls_after_subject_first_prep = len(fixture.fulfillment.call_log)

        legacy_registry = build_migrated_strategy_registry(fixture.access.plan_backed_fulfillment)
        legacy_result, diagnostic = refresh_with_shadow(
            legacy_registry,
            _repository(),
            _FrozenClock(NOW),
            strategy_id="earnings_calendar",
            symbol="AAPL",
            observations=tuple,
            shadow_registry=fixture.shadow_registry,
            shadow_knowledge_by_subject=knowledge,
            now=NOW,
        )

        assert legacy_result.evaluation_state is EvaluationState.MISSING_DATA
        assert len(fixture.fulfillment.call_log) == calls_after_subject_first_prep, (
            "legacy Earnings retried an already-exhausted shared failure independently "
            "instead of reusing the plan's own single bounded outcome"
        )
        assert diagnostic is not None
        assert diagnostic.status == "shadow_unknown"
        assert diagnostic.shadow_unknown_code == "missing_earnings_date"
        assert diagnostic.shadow_unknown_demand_ids == (earnings_demand(NOW).demand_id,)

        # The plan's own bounded retry (maximum_attempts_per_request=2,
        # the default) is the *exact* source of EARNINGS_CALENDAR_V1
        # attempts -- never doubled across the two evaluators sharing this
        # plan, and never fewer than the configured bound either
        # (Architect checkpoint: fifteenth review, corrective test
        # hardening: an exact count, not merely an upper bound).
        earnings_calls = [
            fulfillment_result
            for fulfillment_result, _decision in fixture.fulfillment.call_log
            if fulfillment_result.request.capability is MarketCapability.EARNINGS_CALENDAR_V1
        ]
        assert len(earnings_calls) == 2

    def test_forward_factor_and_skew_momentum_share_the_same_plan(self) -> None:
        """FF and Skew remain unmigrated legacy adapters, executing
        unchanged through the exact same closure-bound
        PlanBackedFulfillment as legacy Earnings -- proven by running all
        three through one shared plan and confirming every evaluation
        completes without error, sharing whatever capability requests
        genuinely overlap (quote, historical bars).
        """
        fixture = _build_earnings_calendar_fixture()
        legacy_registry = build_migrated_strategy_registry(fixture.access.plan_backed_fulfillment)
        repository = _repository()
        clock = _FrozenClock(NOW)

        results = {
            strategy_id: refresh_with_shadow(
                legacy_registry,
                repository,
                clock,
                strategy_id=strategy_id,
                symbol="AAPL",
                observations=tuple,
            )[0]
            for strategy_id in ("forward_factor", "skew_momentum", "earnings_calendar")
        }

        for strategy_id, result in results.items():
            assert result.evaluation_state in {
                EvaluationState.PASS,
                EvaluationState.NO_SIGNAL,
            }, (strategy_id, result.evaluation_state, result.metrics)

        # One real, shared quote request serves all three strategies --
        # never three independent ones for the same subject/capability.
        quote_calls = [
            fulfillment_result
            for fulfillment_result, decision in fixture.fulfillment.call_log
            if fulfillment_result.request.capability is MarketCapability.REAL_TIME_QUOTE_V1
        ]
        assert len(quote_calls) == 1

    def test_only_one_subject_acquisition_plan_is_ever_constructed_for_this_subject(
        self,
    ) -> None:
        """build_subject_acquisition_access is called exactly once for
        this subject in this test -- the same SubjectAcquisitionAccess
        (and therefore the same underlying plan) is reused across all
        three strategy evaluations below, by construction, never rebuilt
        per (strategy, subject) pair.
        """
        fixture = _build_earnings_calendar_fixture()
        legacy_registry = build_migrated_strategy_registry(fixture.access.plan_backed_fulfillment)
        repository = _repository()
        clock = _FrozenClock(NOW)

        for strategy_id in ("forward_factor", "skew_momentum", "earnings_calendar"):
            refresh_with_shadow(
                legacy_registry,
                repository,
                clock,
                strategy_id=strategy_id,
                symbol="AAPL",
                observations=tuple,
            )

        assert legacy_registry.adapter_for("forward_factor") is not None
        assert fixture.access.plan_backed_fulfillment.plan is fixture.access.plan
        assert fixture.access.plan.plan_id == "cycle-1:AAPL"
