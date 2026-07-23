"""SPRINT-009/EPIC-5: universal opportunity model.

Uses a fake, generically-named lifecycle-tracking strategy ("watched_event")
throughout -- proving the engine is genuinely strategy-agnostic, the same
way EPIC-1's own tests never named a real strategy either. Reconciling
this engine against the mature Stonk Calendar implementation's own real
states is EPIC-7's job, not this ticket's.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from strategy_runtime import (
    DataRequirement,
    LifecycleDeclaration,
    LifecycleModel,
    OutputKind,
    RequirementCategory,
    StrategyContract,
    StrategyContractError,
    StructureKind,
)
from strategy_runtime.lifecycle import (
    OpportunityHistory,
    OpportunityObservation,
    RecommendedAction,
    compute_opportunity_id,
    observe_transition,
    validate_lifecycle_stage,
)
from strategy_runtime.result import EvaluationState, RowType, UniversalScreeningResult

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _lifecycle_contract() -> StrategyContract:
    return StrategyContract(
        strategy_id="watched_event",
        version="1.0.0",
        category="test",
        description="A fake lifecycle-tracking strategy for EPIC-5 tests.",
        requirements=(DataRequirement(RequirementCategory.CUSTOM, identifier="none"),),
        lifecycle=LifecycleDeclaration(
            LifecycleModel.OPPORTUNITY,
            supported_states=("watching", "confirmed", "closed"),
            observation_type="watched_event",
        ),
        structure=StructureKind.NONE,
        outputs=(OutputKind.METRICS, OutputKind.LIFECYCLE),
    )


def _no_lifecycle_contract() -> StrategyContract:
    from strategy_runtime import NO_LIFECYCLE

    return StrategyContract(
        strategy_id="stateless",
        version="1.0.0",
        category="test",
        description="A fake stateless strategy for EPIC-5 tests.",
        requirements=(DataRequirement(RequirementCategory.CUSTOM, identifier="none"),),
        lifecycle=NO_LIFECYCLE,
        structure=StructureKind.NONE,
        outputs=(OutputKind.METRICS,),
    )


def _observation(
    opportunity_id: str, stage: str, action: RecommendedAction, observed_at: datetime
) -> OpportunityObservation:
    return OpportunityObservation(
        opportunity_id=opportunity_id,
        strategy_id="watched_event",
        symbol="AAPL",
        lifecycle_stage=stage,
        verdict="pass",
        recommended_action=action,
        observed_at=observed_at,
    )


class TestComputeOpportunityId:
    def test_deterministic_for_identical_inputs(self) -> None:
        assert compute_opportunity_id(
            "watched_event", "AAPL", "2026-02-01"
        ) == compute_opportunity_id("watched_event", "AAPL", "2026-02-01")

    def test_differs_when_identity_components_differ(self) -> None:
        base = compute_opportunity_id("watched_event", "AAPL", "2026-02-01")
        assert compute_opportunity_id("watched_event", "AAPL", "2026-03-01") != base
        assert compute_opportunity_id("watched_event", "MSFT", "2026-02-01") != base

    def test_differs_from_a_differently_scoped_observation_id(self) -> None:
        # An opportunity_id must never accidentally collide with a
        # per-observation identity -- different hash inputs entirely.
        from strategy_runtime.result import compute_observation_id

        opportunity_id = compute_opportunity_id("watched_event", "AAPL", "2026-02-01")
        observation_id = compute_observation_id("run-1", "watched_event", "AAPL")
        assert opportunity_id != observation_id


class TestValidateLifecycleStage:
    def test_undeclared_stage_is_rejected(self) -> None:
        with pytest.raises(StrategyContractError, match="not a lifecycle_stage"):
            validate_lifecycle_stage(_lifecycle_contract(), "expired")

    def test_declared_stage_is_accepted(self) -> None:
        validate_lifecycle_stage(_lifecycle_contract(), "watching")  # does not raise

    def test_none_lifecycle_contract_rejects_any_stage(self) -> None:
        with pytest.raises(StrategyContractError, match="declares no lifecycle model"):
            validate_lifecycle_stage(_no_lifecycle_contract(), "watching")


class TestOpportunityHistory:
    def test_requires_at_least_one_observation(self) -> None:
        with pytest.raises(ValueError, match="at least one observation"):
            OpportunityHistory("opp-1", ())

    def test_mismatched_opportunity_id_is_rejected(self) -> None:
        observation = _observation("opp-1", "watching", RecommendedAction.MONITOR, NOW)
        with pytest.raises(ValueError, match="same opportunity_id"):
            OpportunityHistory("opp-2", (observation,))

    def test_observations_are_ordered_oldest_first_regardless_of_input_order(self) -> None:
        early = _observation("opp-1", "watching", RecommendedAction.MONITOR, NOW)
        late = _observation(
            "opp-1", "confirmed", RecommendedAction.ENTER, NOW + timedelta(days=1)
        )
        history = OpportunityHistory("opp-1", (late, early))
        assert history.observations == (early, late)
        assert history.current is late

    def test_append_returns_a_new_history_with_the_new_observation_last(self) -> None:
        first = _observation("opp-1", "watching", RecommendedAction.MONITOR, NOW)
        history = OpportunityHistory("opp-1", (first,))

        second = _observation(
            "opp-1", "confirmed", RecommendedAction.ENTER, NOW + timedelta(days=1)
        )
        updated = history.append(second)

        assert updated.observations == (first, second)
        assert updated.current is second
        assert history.observations == (first,)  # original untouched -- immutable

    def test_append_rejects_a_mismatched_opportunity_id(self) -> None:
        first = _observation("opp-1", "watching", RecommendedAction.MONITOR, NOW)
        history = OpportunityHistory("opp-1", (first,))
        other = _observation("opp-2", "watching", RecommendedAction.MONITOR, NOW)
        with pytest.raises(ValueError, match="own opportunity_id"):
            history.append(other)


class TestEndToEndFakeLifecycleStrategy:
    def test_a_generic_strategy_can_build_a_full_evolution_history(self) -> None:
        contract = _lifecycle_contract()
        opportunity_id = compute_opportunity_id(
            contract.strategy_id, "AAPL", "watched-event-2026-02-01"
        )

        for stage in contract.lifecycle.supported_states:
            validate_lifecycle_stage(contract, stage)  # every declared stage is valid

        watching = _observation(opportunity_id, "watching", RecommendedAction.MONITOR, NOW)
        history = OpportunityHistory(opportunity_id, (watching,))

        confirmed = _observation(
            opportunity_id, "confirmed", RecommendedAction.ENTER, NOW + timedelta(days=3)
        )
        history = history.append(confirmed)

        closed = _observation(
            opportunity_id, "closed", RecommendedAction.EXIT, NOW + timedelta(days=10)
        )
        history = history.append(closed)

        assert [item.lifecycle_stage for item in history.observations] == [
            "watching",
            "confirmed",
            "closed",
        ]
        assert history.current.recommended_action is RecommendedAction.EXIT


def _universal_result(**overrides: object) -> UniversalScreeningResult:
    defaults: dict[str, object] = {
        "strategy_id": "watched_event",
        "strategy_version": "1.0.0",
        "symbol": "AAPL",
        "observation_id": "obs-1",
        "opportunity_id": compute_opportunity_id("watched_event", "AAPL", "event-1"),
        "row_type": RowType.RESULT,
        "verdict": "pass",
        "evaluation_state": EvaluationState.PASS,
        "lifecycle_stage": "watching",
        "recommendation_state": None,
        "data_quality": None,
        "metrics": {},
        "economics": {},
        "blockers": (),
        "warnings": (),
        "provenance": (),
        "observed_at": NOW,
    }
    defaults.update(overrides)
    return UniversalScreeningResult(**defaults)  # type: ignore[arg-type]


class TestObserveTransition:
    """SPRINT-009R/EPIC-R3: the lifecycle transition engine -- turning one
    execution's own result into a durable OpportunityObservation, with
    recommended_action always supplied by the caller (never derived here --
    a recommendation engine is this sprint's own explicit non_goal).
    """

    def test_a_lifecycle_carrying_result_produces_a_matching_observation(self) -> None:
        contract = _lifecycle_contract()
        result = _universal_result()

        observation = observe_transition(
            contract, result, recommended_action=RecommendedAction.MONITOR
        )

        assert observation.opportunity_id == result.opportunity_id
        assert observation.strategy_id == result.strategy_id
        assert observation.symbol == result.symbol
        assert observation.lifecycle_stage == result.lifecycle_stage
        assert observation.verdict == result.verdict
        assert observation.recommended_action is RecommendedAction.MONITOR
        assert observation.observed_at == result.observed_at

    def test_a_result_with_no_opportunity_id_is_rejected(self) -> None:
        contract = _lifecycle_contract()
        result = _universal_result(opportunity_id=None, lifecycle_stage=None)

        with pytest.raises(StrategyContractError, match="no opportunity transition"):
            observe_transition(contract, result, recommended_action=RecommendedAction.MONITOR)

    def test_an_undeclared_lifecycle_stage_is_rejected(self) -> None:
        contract = _lifecycle_contract()
        result = _universal_result(lifecycle_stage="not_a_declared_stage")

        with pytest.raises(StrategyContractError, match="not a lifecycle_stage"):
            observe_transition(contract, result, recommended_action=RecommendedAction.MONITOR)

    def test_recommended_action_is_never_derived_only_ever_passed_through(self) -> None:
        contract = _lifecycle_contract()
        result = _universal_result(lifecycle_stage="confirmed")

        observation = observe_transition(
            contract, result, recommended_action=RecommendedAction.EXIT
        )

        assert observation.recommended_action is RecommendedAction.EXIT
