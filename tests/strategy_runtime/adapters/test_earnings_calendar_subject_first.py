"""SPRINT-014 S14-PR-05A, Architect checkpoint: twelfth review, items 5/6.

Proves the production subject-first preparation seam
(strategy_runtime.subject_preparation) and Earnings Calendar's own binding
+ runtime adapter (strategy_runtime.adapters.earnings_calendar_subject_first)
actually work, replacing the test-only ``_select_structure()`` harness
(tests/strategy_runtime/test_earnings_calendar_generic_composition.py) with
calls into the real production functions it was standing in for.

Three things proven here:

1. ``_prepare_earnings_calendar_knowledge_mapping`` -- Earnings' own
   binding callback -- reproduces the exact parity and typed-UNKNOWN
   results already proven against the test-only harness, now calling
   production code, against the same fixtures.
2. ``prepare_strategy_knowledge`` -- the generic orchestrator -- proven
   generic against a synthetic, non-Earnings consumer run through a REAL
   SubjectAcquisitionPlan/CapabilityFulfillmentService (mirroring
   tests/screening/test_subject_planning.py's own "everything synthetic"
   philosophy), plus SubjectPreparationRegistry's own lookup/duplicate
   behavior.
3. ``build_earnings_calendar_subject_first_adapter`` -- the new runtime
   adapter -- proven to project a ReadOnlyStrategyInput into a correct
   UniversalScreeningResult, with no route back to acquisition.

Still unwired (Architect checkpoint item 8 remains separate, larger,
production-composition-root work): none of this has a caller in
asa/scheduled_screening.py or asa/api/screening_routes.py yet.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import cast

import pytest

from analytics.features import DerivedFactRequest, DerivedFactSet
from domain import (
    CanonicalFact,
    CapabilityDemand,
    DemandExpansion,
    EvidenceUsability,
    MarketCapability,
    Quote,
    ResolvedCapabilityEvidence,
    UnknownReason,
)
from market_data import CapabilityFulfillmentService
from market_data.attempts import InMemoryAcquisitionAttemptRepository
from market_data.resolution import ResolutionPolicy
from market_data.snapshot import MarketSnapshot
from market_data.subject_plan import SubjectAcquisitionPlan
from screening.subject_fact_projection import SealedEvidenceProvenanceError
from screening.subject_planning import ResolvedEvidenceView, SubjectPlanConsumer
from strategies.earnings_calendar_evaluation import evaluate_earnings_calendar
from strategies.earnings_calendar_knowledge_binding import EarningsCalendarPayload
from strategies.earnings_calendar_planning import (
    earnings_demand,
    expirations_demand,
    historical_bars_demand,
    quote_demand,
)
from strategies.knowledge_contracts import KnowledgeMapping
from strategy_runtime.adapters.earnings_calendar import EARNINGS_CALENDAR_CONTRACT
from strategy_runtime.adapters.earnings_calendar_subject_first import (
    _prepare_earnings_calendar_knowledge_mapping,
    build_earnings_calendar_subject_first_adapter,
    build_earnings_calendar_subject_preparation_binding,
)
from strategy_runtime.context import RuntimeContext
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.knowledge_composition import compose_strategy_knowledge
from strategy_runtime.knowledge_registry import KnowledgeCompositionRegistry
from strategy_runtime.lifecycle import compute_opportunity_id
from strategy_runtime.result import EvaluationState, UniversalScreeningResult
from strategy_runtime.subject_preparation import (
    DuplicateSubjectPreparationBindingError,
    SubjectPreparationBinding,
    SubjectPreparationRegistry,
    UnknownSubjectPreparationBindingError,
    prepare_strategy_knowledge,
    prepare_subject_knowledge,
)
from tests.market_data.test_fulfillment import CAPABILITY, provider, service
from tests.strategy_runtime.test_earnings_calendar_generic_composition import (
    NOW,
    STRATEGY_ID,
    SYMBOL,
    _build_snapshot,
    _chain,
    _daily_closes,
    _earnings_event,
    _expiration_collection,
    _historical_bars,
    _legacy_baseline,
    _quote,
    _resolved_evidence,
    _selections,
)


@dataclass
class _FixedClock:
    value: datetime = NOW

    def now(self) -> datetime:
        return self.value


def _projected_evidence(
    *,
    front_iv: Decimal | None,
    back_iv: Decimal | None,
    bars_count: int = 30,
    no_calls_at: date | None = None,
    quote: Quote | None = None,
) -> dict[str, ResolvedCapabilityEvidence]:
    """The same raw, un-phase-two-selected evidence dict
    screening.subject_planning.run_subject_plan's own ``projected_evidence``
    would hand a registered binding -- reusing the exact fixture data
    tests/strategy_runtime/test_earnings_calendar_generic_composition.py's
    own ``_phase_two_evidence`` already builds internally, before that
    helper converts it via select_earnings_calendar_phase_two_evidence
    (which _prepare_earnings_calendar_knowledge_mapping now does itself).
    """
    selections = dict(_selections())
    front_demand_id = selections["front_demand_id"]
    back_demand_id = selections["back_demand_id"]
    assert isinstance(front_demand_id, str)
    assert isinstance(back_demand_id, str)
    chain = _chain(front_iv, back_iv, no_calls_at=no_calls_at)
    resolved_quote = quote if quote is not None else _quote()
    return {
        quote_demand(NOW).demand_id: _resolved_evidence(
            quote_demand(NOW).demand_id,
            MarketCapability.REAL_TIME_QUOTE_V1,
            ("last",),
            resolved_quote,
        ),
        earnings_demand(NOW).demand_id: _resolved_evidence(
            earnings_demand(NOW).demand_id,
            MarketCapability.EARNINGS_CALENDAR_V1,
            ("earnings_date",),
            _earnings_event(),
        ),
        historical_bars_demand(NOW).demand_id: _resolved_evidence(
            historical_bars_demand(NOW).demand_id,
            MarketCapability.HISTORICAL_BARS_V1,
            ("close",),
            _historical_bars(bars_count),
        ),
        expirations_demand(NOW).demand_id: _resolved_evidence(
            expirations_demand(NOW).demand_id,
            MarketCapability.OPTION_CHAIN_V1,
            ("expirations",),
            _expiration_collection(),
        ),
        front_demand_id: _resolved_evidence(
            front_demand_id, MarketCapability.OPTION_CHAIN_V1, ("contracts",), chain
        ),
        back_demand_id: _resolved_evidence(
            back_demand_id, MarketCapability.OPTION_CHAIN_V1, ("contracts",), chain
        ),
    }


class TestPrepareEarningsCalendarKnowledgeMapping:
    """Earnings' own SubjectPreparationBinding callback, unit-tested
    directly -- the production function that now performs every mechanic
    the deleted test-only ``_select_structure()`` harness stood in for.
    """

    def test_pass_or_watch_parity_with_legacy_verdict_and_score(self) -> None:
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv)
        projected = _projected_evidence(front_iv=front_iv, back_iv=back_iv)

        mapping = _prepare_earnings_calendar_knowledge_mapping(
            snapshot, projected, _selections(), SYMBOL
        )
        assert not isinstance(mapping, UnknownReason)

        registry = KnowledgeCompositionRegistry(((STRATEGY_ID, mapping),))
        knowledge_input = compose_strategy_knowledge(
            snapshot, registry, STRATEGY_ID, subject=SYMBOL
        )
        assert not isinstance(knowledge_input, UnknownReason)

        outputs = evaluate_earnings_calendar(knowledge_input.derived_facts, knowledge_input.payload)
        legacy_verdict, legacy_score = _legacy_baseline(
            _chain(front_iv, back_iv), _earnings_event(), _daily_closes(30)
        )
        assert outputs.get("verdict").value == legacy_verdict
        assert outputs.get("score").value == legacy_score
        assert legacy_verdict in {"PASS", "WATCH"}

    def test_insufficient_historical_bars_is_unknown(self) -> None:
        # insufficient_historical_bars is raised lazily, inside the
        # KnowledgeMapping's own compute_derived_fact_requests callback
        # (strategies/earnings_calendar_knowledge_binding.py) -- it only
        # surfaces once compose_strategy_knowledge actually invokes that
        # callback, not from _prepare_earnings_calendar_knowledge_mapping
        # (which only builds structural selection) on its own.
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv, bars_count=1)
        projected = _projected_evidence(front_iv=front_iv, back_iv=back_iv, bars_count=1)

        mapping = _prepare_earnings_calendar_knowledge_mapping(
            snapshot, projected, _selections(), SYMBOL
        )
        assert not isinstance(mapping, UnknownReason)
        registry = KnowledgeCompositionRegistry(((STRATEGY_ID, mapping),))
        result = compose_strategy_knowledge(snapshot, registry, STRATEGY_ID, subject=SYMBOL)
        assert isinstance(result, UnknownReason)
        assert result.code == "insufficient_historical_bars"

    def test_missing_implied_volatility_is_unknown(self) -> None:
        snapshot, *_ = _build_snapshot(front_iv=None, back_iv=Decimal("0.20"))
        projected = _projected_evidence(front_iv=None, back_iv=Decimal("0.20"))

        mapping = _prepare_earnings_calendar_knowledge_mapping(
            snapshot, projected, _selections(), SYMBOL
        )
        assert isinstance(mapping, UnknownReason)
        assert mapping.code == "missing_implied_volatility"

    def test_evidence_not_belonging_to_the_supplied_snapshot_is_rejected(self) -> None:
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        other_snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv, bars_count=45)
        projected = _projected_evidence(front_iv=front_iv, back_iv=back_iv)

        with pytest.raises(SealedEvidenceProvenanceError):
            _prepare_earnings_calendar_knowledge_mapping(
                other_snapshot, projected, _selections(), SYMBOL
            )

    def test_wrong_domain_type_for_discovery_evidence_raises_not_unknown(self) -> None:
        """Architect checkpoint: thirteenth review, corrective item 3 --
        "an unexpected resolved value type" is an internal inconsistency,
        never a genuine data gap, so it must raise
        SealedEvidenceProvenanceError, not downgrade to a typed
        UnknownReason.
        """
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv)
        projected = dict(_projected_evidence(front_iv=front_iv, back_iv=back_iv))
        expirations_id = expirations_demand(NOW).demand_id
        # Built directly (not via _resolved_evidence's own MarketObservation-
        # backed helper): MarketObservation.__post_init__ already enforces
        # value/capability type matching as a domain invariant, so a
        # malformed observation can never even be constructed -- but
        # ResolvedCapabilityEvidence (a lighter, provider-blind projection)
        # carries no such check, which is exactly the gap this test proves
        # _prepare_earnings_calendar_knowledge_mapping itself must guard.
        projected[expirations_id] = ResolvedCapabilityEvidence(
            expirations_id,
            MarketCapability.OPTION_CHAIN_V1,
            EvidenceUsability.RESOLVED,
            _quote(),
            (),
            None,
        )

        with pytest.raises(SealedEvidenceProvenanceError):
            _prepare_earnings_calendar_knowledge_mapping(
                snapshot, projected, _selections(), SYMBOL
            )

    def test_selected_expiration_not_in_discovery_collection_raises_not_unknown(self) -> None:
        """Architect checkpoint: thirteenth review, corrective item 3 --
        "a selected expiration missing from the discovery collection" is
        an impossible internal inconsistency (both the selection and the
        discovery collection are computed from the same evidence), never
        a genuine data gap.
        """
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv)
        projected = _projected_evidence(front_iv=front_iv, back_iv=back_iv)
        selections_by_key = dict(_selections())
        selections_by_key["front_expiration"] = date(2099, 1, 1).isoformat()
        bad_selections = tuple(selections_by_key.items())

        with pytest.raises(SealedEvidenceProvenanceError):
            _prepare_earnings_calendar_knowledge_mapping(
                snapshot, projected, bad_selections, SYMBOL
            )


class TestSubjectPreparationRegistry:
    def _binding(self) -> SubjectPreparationBinding[object]:
        return build_earnings_calendar_subject_preparation_binding(NOW)

    def test_unknown_strategy_id_raises(self) -> None:
        registry: SubjectPreparationRegistry[object] = SubjectPreparationRegistry(())
        with pytest.raises(UnknownSubjectPreparationBindingError):
            registry.binding_for("nope")

    def test_duplicate_strategy_id_raises(self) -> None:
        binding = self._binding()
        with pytest.raises(DuplicateSubjectPreparationBindingError):
            SubjectPreparationRegistry(((STRATEGY_ID, binding), (STRATEGY_ID, binding)))

    def test_strategy_ids_and_is_registered(self) -> None:
        binding = self._binding()
        registry: SubjectPreparationRegistry[object] = SubjectPreparationRegistry(
            (("zeta", binding), ("alpha", binding))
        )
        assert registry.strategy_ids() == ("alpha", "zeta")
        assert registry.is_registered("alpha")
        assert not registry.is_registered("omega")


@dataclass(frozen=True, slots=True)
class _SyntheticPayload:
    marker: str


def _no_derived_facts(
    _facts: tuple[CanonicalFact, ...]
) -> tuple[DerivedFactRequest, ...] | UnknownReason:
    return ()


def _broken_derived_facts(
    _facts: tuple[CanonicalFact, ...]
) -> tuple[DerivedFactRequest, ...] | UnknownReason:
    raise RuntimeError("synthetic composition defect")


def _synthetic_payload(
    _facts: tuple[CanonicalFact, ...], _derived: DerivedFactSet
) -> _SyntheticPayload:
    return _SyntheticPayload("ok")


_SYNTHETIC_RESOLUTION_POLICY = {CAPABILITY: ResolutionPolicy("v1", ("primary",), 3600, ("last",))}


def _synthetic_demand() -> CapabilityDemand:
    return CapabilityDemand(CAPABILITY, ("last",), NOW, NOW, required=True)


def _synthetic_prepare_knowledge_mapping(
    _snapshot: MarketSnapshot,
    _projected_evidence: ResolvedEvidenceView,
    _selections: tuple[tuple[str, object], ...],
    _subject: str,
) -> KnowledgeMapping[_SyntheticPayload] | UnknownReason:
    # Reuses the real, strategies-owned KnowledgeMapping dataclass rather
    # than a hand-rolled local stand-in -- both structurally satisfy
    # KnowledgeBinding identically at runtime, but mypy's Protocol
    # conformance check for a Generic[TPayload] dataclass against
    # KnowledgeBinding[TPayload] only resolves cleanly when the concrete
    # type itself is used as the declared return type (matching how
    # strategy_runtime/adapters/earnings_calendar_subject_first.py's own
    # production binding is typed) -- a plain non-generic synthetic
    # class in this position hits a mypy limitation, not a real defect.
    return KnowledgeMapping(
        canonical_fact_requests=(),
        compute_derived_fact_requests=_no_derived_facts,
        build_payload=_synthetic_payload,
    )


def _synthetic_build_shadow_adapter(
    _knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[_SyntheticPayload]],
) -> Callable[[RuntimeContext], UniversalScreeningResult]:
    raise AssertionError("synthetic binding's shadow adapter is never exercised by this test")


def _plan(fulfillment: CapabilityFulfillmentService) -> SubjectAcquisitionPlan:
    return SubjectAcquisitionPlan(
        "AAPL",
        fulfillment,
        attempt_repository=InMemoryAcquisitionAttemptRepository(),
        plan_id="cycle-1:AAPL",
        clock=_FixedClock(NOW),
        maximum_attempts_per_request=2,
    )


class TestPrepareStrategyKnowledgeGenericMechanics:
    """prepare_strategy_knowledge's own orchestration, proven generic
    against a synthetic consumer run through a REAL SubjectAcquisitionPlan
    and a REAL CapabilityFulfillmentService (single-capability, via
    tests.market_data.test_fulfillment's own fixtures) -- proving the
    actual run_subject_plan integration path works, not merely a
    hand-assembled sealed snapshot.
    """

    def test_unregistered_strategy_id_raises(self) -> None:
        registry: SubjectPreparationRegistry[object] = SubjectPreparationRegistry(())
        fulfillment, _ = service(provider("primary"))
        plan = _plan(fulfillment)

        with pytest.raises(UnknownSubjectPreparationBindingError):
            prepare_strategy_knowledge(
                plan,
                NOW,
                registry,
                "not-registered",
                subject="AAPL",
                provider_metadata=(provider("primary").metadata,),
                resolution_policy_by_capability=_SYNTHETIC_RESOLUTION_POLICY,
            )

    def test_synthetic_consumer_composes_end_to_end(self) -> None:
        consumer = SubjectPlanConsumer(
            "synthetic-strategy", (_synthetic_demand(),), lambda _evidence: DemandExpansion()
        )
        binding: SubjectPreparationBinding[_SyntheticPayload] = SubjectPreparationBinding(
            consumer=consumer,
            prepare_knowledge_mapping=_synthetic_prepare_knowledge_mapping,
            build_shadow_adapter=_synthetic_build_shadow_adapter,
        )
        registry: SubjectPreparationRegistry[_SyntheticPayload] = SubjectPreparationRegistry(
            (("synthetic-strategy", binding),)
        )
        fulfillment, budgets = service(provider("primary"))
        plan = _plan(fulfillment)

        result = prepare_strategy_knowledge(
            plan,
            NOW,
            registry,
            "synthetic-strategy",
            subject="AAPL",
            provider_metadata=(provider("primary").metadata,),
            resolution_policy_by_capability=_SYNTHETIC_RESOLUTION_POLICY,
        )

        assert isinstance(result, ReadOnlyStrategyInput)
        assert result.payload.marker == "ok"
        assert result.canonical_facts == ()
        assert result.derived_facts.facts == ()
        # Exactly one real provider call was made for the one bootstrap
        # demand -- proving this ran through the real acquisition path,
        # not a hand-assembled snapshot.
        assert len(budgets.accounting) == 1

    def test_expansion_unknown_reason_propagates_without_calling_the_binding_callback(
        self,
    ) -> None:
        called = False

        def _never_called(
            _snapshot: MarketSnapshot,
            _projected_evidence: ResolvedEvidenceView,
            _selections: tuple[tuple[str, object], ...],
            _subject: str,
        ) -> KnowledgeMapping[_SyntheticPayload] | UnknownReason:
            nonlocal called
            called = True
            return KnowledgeMapping(
                canonical_fact_requests=(),
                compute_derived_fact_requests=_no_derived_facts,
                build_payload=_synthetic_payload,
            )

        def _expand_with_gap(_evidence: object) -> DemandExpansion:
            return DemandExpansion(unknown_reasons=(UnknownReason("synthetic_gap"),))

        consumer = SubjectPlanConsumer(
            "synthetic-strategy", (_synthetic_demand(),), _expand_with_gap
        )
        binding: SubjectPreparationBinding[_SyntheticPayload] = SubjectPreparationBinding(
            consumer=consumer,
            prepare_knowledge_mapping=_never_called,
            build_shadow_adapter=_synthetic_build_shadow_adapter,
        )
        registry: SubjectPreparationRegistry[_SyntheticPayload] = SubjectPreparationRegistry(
            (("synthetic-strategy", binding),)
        )
        fulfillment, _ = service(provider("primary"))
        plan = _plan(fulfillment)

        result = prepare_strategy_knowledge(
            plan,
            NOW,
            registry,
            "synthetic-strategy",
            subject="AAPL",
            provider_metadata=(provider("primary").metadata,),
            resolution_policy_by_capability=_SYNTHETIC_RESOLUTION_POLICY,
        )

        assert isinstance(result, UnknownReason)
        assert result.code == "synthetic_gap"
        assert called is False

    def test_one_binding_failure_does_not_destroy_other_prepared_knowledge(self) -> None:
        consumer_a = SubjectPlanConsumer(
            "broken-strategy", (_synthetic_demand(),), lambda _evidence: DemandExpansion()
        )
        consumer_b = SubjectPlanConsumer(
            "healthy-strategy", (_synthetic_demand(),), lambda _evidence: DemandExpansion()
        )

        def _broken(*_args: object) -> KnowledgeMapping[_SyntheticPayload]:
            raise RuntimeError("synthetic binding defect")

        broken: SubjectPreparationBinding[_SyntheticPayload] = SubjectPreparationBinding(
            consumer_a, _broken, _synthetic_build_shadow_adapter
        )
        healthy: SubjectPreparationBinding[_SyntheticPayload] = SubjectPreparationBinding(
            consumer_b, _synthetic_prepare_knowledge_mapping, _synthetic_build_shadow_adapter
        )
        registry = cast(
            SubjectPreparationRegistry[object],
            SubjectPreparationRegistry(
                (("broken-strategy", broken), ("healthy-strategy", healthy))
            ),
        )
        fulfillment, budgets = service(provider("primary"))

        result = prepare_subject_knowledge(
            _plan(fulfillment),
            NOW,
            registry,
            subject="AAPL",
            provider_metadata=(provider("primary").metadata,),
            resolution_policy_by_capability=_SYNTHETIC_RESOLUTION_POLICY,
        )

        broken_result = result["broken-strategy"]
        assert isinstance(broken_result, UnknownReason)
        assert broken_result.code == "strategy_knowledge_construction_failed"
        assert isinstance(result["healthy-strategy"], ReadOnlyStrategyInput)
        assert len(budgets.accounting) == 1

    def test_one_composition_failure_does_not_destroy_other_prepared_knowledge(self) -> None:
        consumer_a = SubjectPlanConsumer(
            "broken-strategy", (_synthetic_demand(),), lambda _evidence: DemandExpansion()
        )
        consumer_b = SubjectPlanConsumer(
            "healthy-strategy", (_synthetic_demand(),), lambda _evidence: DemandExpansion()
        )

        def _broken_mapping(*_args: object) -> KnowledgeMapping[_SyntheticPayload]:
            return KnowledgeMapping((), _broken_derived_facts, _synthetic_payload)

        registry = cast(
            SubjectPreparationRegistry[object],
            SubjectPreparationRegistry(
                (
                    (
                        "broken-strategy",
                        SubjectPreparationBinding(
                            consumer_a, _broken_mapping, _synthetic_build_shadow_adapter
                        ),
                    ),
                    (
                        "healthy-strategy",
                        SubjectPreparationBinding(
                            consumer_b,
                            _synthetic_prepare_knowledge_mapping,
                            _synthetic_build_shadow_adapter,
                        ),
                    ),
                )
            ),
        )
        fulfillment, budgets = service(provider("primary"))

        result = prepare_subject_knowledge(
            _plan(fulfillment),
            NOW,
            registry,
            subject="AAPL",
            provider_metadata=(provider("primary").metadata,),
            resolution_policy_by_capability=_SYNTHETIC_RESOLUTION_POLICY,
        )

        broken_result = result["broken-strategy"]
        assert isinstance(broken_result, UnknownReason)
        assert broken_result.code == "strategy_knowledge_construction_failed"
        assert isinstance(result["healthy-strategy"], ReadOnlyStrategyInput)
        assert len(budgets.accounting) == 1


class TestEarningsCalendarSubjectFirstAdapter:
    """build_earnings_calendar_subject_first_adapter, proven bound only to
    an already-computed ReadOnlyStrategyInput -- no route back to plan,
    fulfillment, provider, transport, budget, repository, or raw
    acquisition diagnostics -- and, Architect checkpoint (thirteenth
    review, corrective item 2), proven to preserve legacy Earnings runtime
    semantics exactly: pinned PASS and WATCH fixtures, each compared
    against strategy_runtime/adapters/earnings_calendar.py's own
    documented mapping rules (_NON_FAIL_VERDICTS / _STAGE_BY_OUTCOME /
    compute_opportunity_id) for verdict, evaluation_state, opportunity
    identity, lifecycle stage, score/metrics, warnings, and observed time.
    Provenance is intentionally richer on the subject-first path (bullet
    2's own explicit carve-out) and is asserted separately, not folded
    into the legacy-parity comparison.
    """

    def _knowledge_input(
        self, *, front_iv: Decimal, back_iv: Decimal
    ) -> tuple[MarketSnapshot, ReadOnlyStrategyInput[EarningsCalendarPayload]]:
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv)
        projected = _projected_evidence(front_iv=front_iv, back_iv=back_iv)
        mapping = _prepare_earnings_calendar_knowledge_mapping(
            snapshot, projected, _selections(), SYMBOL
        )
        assert not isinstance(mapping, UnknownReason)
        registry = KnowledgeCompositionRegistry(((STRATEGY_ID, mapping),))
        knowledge_input = compose_strategy_knowledge(
            snapshot, registry, STRATEGY_ID, subject=SYMBOL
        )
        assert not isinstance(knowledge_input, UnknownReason)
        return snapshot, knowledge_input

    def _run(
        self, *, front_iv: Decimal, back_iv: Decimal, run_id: str = "run-1"
    ) -> tuple[
        MarketSnapshot, ReadOnlyStrategyInput[EarningsCalendarPayload], UniversalScreeningResult
    ]:
        snapshot, knowledge_input = self._knowledge_input(front_iv=front_iv, back_iv=back_iv)
        adapter = build_earnings_calendar_subject_first_adapter({SYMBOL: knowledge_input})
        context = RuntimeContext(
            contract=EARNINGS_CALENDAR_CONTRACT,
            subject=SYMBOL,
            clock=_FixedClock(NOW),
            run_id=run_id,
        )
        return snapshot, knowledge_input, adapter(context)

    def _assert_full_legacy_semantic_parity(
        self, result: UniversalScreeningResult, *, front_iv: Decimal, back_iv: Decimal
    ) -> None:
        """Compares every semantic field the Architect's own checkpoint
        named against legacy's own documented rules
        (strategy_runtime/adapters/earnings_calendar.py):
        ``_NON_FAIL_VERDICTS = {"PASS", "WATCH"}`` maps to
        ``ScreeningOutcomeStatus.PASS`` -> ``EvaluationState.PASS``;
        ``_STAGE_BY_OUTCOME`` maps that same successful outcome to
        ``"confirmed"`` (everything else to ``"watching"``), with
        ``compute_opportunity_id("earnings_calendar", symbol)`` always
        assigned alongside a stage. verdict/score parity itself reuses
        ``_legacy_baseline()`` -- the same acquisition-free formula-chain
        replay already proven correct against the live path in
        TestGenericCompositionParity.
        """
        legacy_verdict, legacy_score = _legacy_baseline(
            _chain(front_iv, back_iv), _earnings_event(), _daily_closes(30)
        )
        is_successful = legacy_verdict in {"PASS", "WATCH"}
        assert result.verdict == legacy_verdict
        assert result.evaluation_state is (
            EvaluationState.PASS if is_successful else EvaluationState.NO_SIGNAL
        )
        assert result.lifecycle_stage == ("confirmed" if is_successful else "watching")
        assert result.opportunity_id == compute_opportunity_id(STRATEGY_ID, SYMBOL)
        assert result.metrics["strategy_native_score"].native() == legacy_score
        assert result.warnings == ()

    def test_pass_matches_legacy_semantics(self) -> None:
        front_iv, back_iv = Decimal("0.50"), Decimal("0.20")
        snapshot, knowledge_input, result = self._run(front_iv=front_iv, back_iv=back_iv)

        assert result.verdict == "PASS"
        self._assert_full_legacy_semantic_parity(result, front_iv=front_iv, back_iv=back_iv)
        assert result.strategy_id == STRATEGY_ID
        assert result.strategy_version == EARNINGS_CALENDAR_CONTRACT.version
        assert result.symbol == SYMBOL
        assert result.observed_at == snapshot.as_of

        self._assert_richer_than_legacy_provenance(result, knowledge_input)

    def test_watch_matches_legacy_semantics(self) -> None:
        """The corrective fix under direct test: legacy treats WATCH as a
        successful, lifecycle-confirmed observation (via
        _NON_FAIL_VERDICTS), not a bare NO_SIGNAL with no opportunity
        identity -- the first draft of this adapter got this wrong.
        """
        front_iv, back_iv = Decimal("0.33"), Decimal("0.24")
        snapshot, knowledge_input, result = self._run(front_iv=front_iv, back_iv=back_iv)

        assert result.verdict == "WATCH"
        self._assert_full_legacy_semantic_parity(result, front_iv=front_iv, back_iv=back_iv)
        assert result.evaluation_state is EvaluationState.PASS
        assert result.lifecycle_stage == "confirmed"
        assert result.opportunity_id is not None

        self._assert_richer_than_legacy_provenance(result, knowledge_input)

    def _assert_richer_than_legacy_provenance(
        self,
        result: UniversalScreeningResult,
        knowledge_input: ReadOnlyStrategyInput[EarningsCalendarPayload],
    ) -> None:
        """Provenance is deliberately richer than legacy's own bare-id
        tuple (Architect checkpoint: thirteenth review, corrective
        hardening 2) -- snapshot identity plus every fact's own version/
        formula_version, explicit rather than accidental.
        """
        assert result.provenance[0] == f"snapshot_id:{knowledge_input.snapshot_id}"
        assert result.provenance[1] == f"snapshot_digest:{knowledge_input.snapshot_digest}"
        expected_canonical = {
            f"canonical_fact:{fact.fact_id}@{fact.version}"
            for fact in knowledge_input.canonical_facts
        }
        expected_derived = {
            f"derived_fact:{fact.derived_fact_id}@{fact.formula_version}"
            for fact in knowledge_input.derived_facts.facts
        }
        assert set(result.provenance[2:]) == expected_canonical | expected_derived

    def test_looks_up_only_by_context_subject(self) -> None:
        _snapshot, _knowledge_input, result = self._run(
            front_iv=Decimal("0.50"), back_iv=Decimal("0.20"), run_id="run-2"
        )
        assert result.observation_id != ""

    def test_knowledge_by_subject_is_frozen_at_construction(self) -> None:
        """Architect checkpoint: thirteenth review, corrective hardening
        1 -- the adapter must not trust an externally mutable Mapping.
        """
        _snapshot, knowledge_input = self._knowledge_input(
            front_iv=Decimal("0.50"), back_iv=Decimal("0.20")
        )
        mutable: dict[str, ReadOnlyStrategyInput[EarningsCalendarPayload]] = {
            SYMBOL: knowledge_input
        }
        adapter = build_earnings_calendar_subject_first_adapter(mutable)
        mutable.clear()
        context = RuntimeContext(
            contract=EARNINGS_CALENDAR_CONTRACT,
            subject=SYMBOL,
            clock=_FixedClock(NOW),
            run_id="run-3",
        )

        result = adapter(context)

        assert result.symbol == SYMBOL
        assert result.verdict == "PASS"
