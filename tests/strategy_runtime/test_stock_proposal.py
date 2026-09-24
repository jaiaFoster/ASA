from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from strategy_runtime.adapters import B001_CONTRACT, B002_CONTRACT
from strategy_runtime.adapters.forward_factor import FORWARD_FACTOR_CONTRACT
from strategy_runtime.result import EvaluationState, RowType, UniversalScreeningResult
from strategy_runtime.stock_proposal import StockProposalStatus, build_stock_opportunity_proposal
from strategy_runtime.values import TypedValue

NOW = datetime(2026, 9, 24, 16, 43, tzinfo=UTC)


def _result(
    strategy_id: str = "B002",
    *,
    verdict: str | None = "PASS",
    state: EvaluationState = EvaluationState.PASS,
    metrics: dict[str, TypedValue] | None = None,
    blockers: tuple[str, ...] = (),
) -> UniversalScreeningResult:
    return UniversalScreeningResult(
        strategy_id=strategy_id,
        strategy_version="1.0.0",
        symbol="SPY",
        observation_id=f"{strategy_id}-SPY-obs",
        opportunity_id=None,
        row_type=RowType.RESULT,
        verdict=verdict,
        evaluation_state=state,
        lifecycle_stage=None,
        recommendation_state=None,
        data_quality=None,
        metrics=(
            {
                "price": TypedValue.of_decimal(Decimal("768.6")),
                "sma_10m_completed_months": TypedValue.of_decimal(Decimal("701.2")),
                "decision.direction": TypedValue.of_string("BUY"),
            }
            if metrics is None
            else metrics
        ),
        economics={},
        blockers=blockers,
        warnings=(),
        provenance=("quote:fixture",),
        observed_at=NOW,
    )


def test_pass_with_emitted_action_is_actionable_without_invented_sizing() -> None:
    proposal = build_stock_opportunity_proposal(_result(), B002_CONTRACT)

    assert proposal.status is StockProposalStatus.ACTIONABLE
    assert proposal.action == "BUY"
    assert proposal.instrument == "SPY"
    assert proposal.signal_metrics == (
        ("price", "768.6"),
        ("sma_10m_completed_months", "701.2"),
    )
    assert proposal.allocation is None
    assert proposal.allocation_reason == "not_defined_by_strategy"
    assert proposal.invalidation_notes == ("not_defined_by_strategy",)
    assert proposal.rationale[0] == B002_CONTRACT.description
    assert proposal.provenance == ("quote:fixture",)


def test_no_signal_never_receives_an_inferred_action() -> None:
    result = _result(
        verdict="FAIL",
        state=EvaluationState.NO_SIGNAL,
        metrics={"price": TypedValue.of_decimal(Decimal("600"))},
    )

    proposal = build_stock_opportunity_proposal(result, B002_CONTRACT)

    assert proposal.status is StockProposalStatus.NO_ACTION
    assert proposal.action is None
    assert proposal.action_reason == "no_action_emitted_by_strategy"


def test_missing_data_stays_typed_unknown() -> None:
    result = _result(
        verdict=None,
        state=EvaluationState.MISSING_DATA,
        metrics={},
        blockers=("typed unknown evidence gap: unusable_historical_bars",),
    )

    proposal = build_stock_opportunity_proposal(result, B002_CONTRACT)

    assert proposal.status is StockProposalStatus.UNKNOWN
    assert proposal.unknown_reasons == ("typed unknown evidence gap: unusable_historical_bars",)
    assert proposal.action_reason == "evaluation_incomplete"


def test_strategy_emitted_allocation_is_projected_verbatim() -> None:
    result = _result()
    result = replace(
        result,
        metrics={**result.metrics, "decision.target_weight": TypedValue.of_decimal(Decimal("0.6"))},
    )

    proposal = build_stock_opportunity_proposal(result, B002_CONTRACT)

    assert proposal.allocation == "0.6"
    assert proposal.allocation_reason is None


def test_option_structured_or_mismatched_contracts_are_refused() -> None:
    with pytest.raises(ValueError, match="no option structure"):
        build_stock_opportunity_proposal(_result("forward_factor"), FORWARD_FACTOR_CONTRACT)
    with pytest.raises(ValueError, match="does not belong"):
        build_stock_opportunity_proposal(_result("B002"), B001_CONTRACT)
