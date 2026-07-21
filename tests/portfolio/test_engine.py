"""ASA-CORE-009 deterministic Portfolio Engine tests."""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from domain.execution import PortfolioDecisionState
from domain.operational import PortfolioDecisionRequest
from portfolio.engine import evaluate_portfolio
from portfolio.models import PORTFOLIO_ALGORITHM_VERSION, PortfolioParameters
from tests.portfolio.helpers import holding, instrument, request, snapshot


def test_accepts_complete_proposal_when_every_policy_passes() -> None:
    proposal = request().proposed_positions[0]
    decision = evaluate_portfolio(request())[0]
    assert decision.state is PortfolioDecisionState.ACCEPT
    assert decision.approved_allocation == proposal.target_allocation


def test_replay_and_identity_are_stable() -> None:
    decision_request = request()
    first = evaluate_portfolio(decision_request)
    second = evaluate_portfolio(decision_request)
    assert first == second
    assert first[0].portfolio_decision_id == second[0].portfolio_decision_id


def test_request_order_is_preserved() -> None:
    original = request()
    first = original.proposed_positions[0]
    second = dataclasses.replace(
        first,
        proposed_position_id="proposal-second",
        opportunity_id="opportunity-second",
    )
    decision_request = PortfolioDecisionRequest(
        "request-two",
        original.ranking_result_id,
        original.portfolio_snapshot,
        (second, first),
    )
    decisions = evaluate_portfolio(decision_request)
    assert tuple(item.proposed_position for item in decisions) == (second, first)


def test_insufficient_cash_rejects() -> None:
    decision = evaluate_portfolio(request(snapshot(cash=Decimal("1000"))))[0]
    assert decision.state is PortfolioDecisionState.REJECT
    assert decision.approved_allocation == 0
    assert "cash reserve limits new exposure" in decision.reasons


def test_buying_power_reduces_to_available_capacity() -> None:
    decision = evaluate_portfolio(
        request(snapshot(buying_power=Decimal("5000")))
    )[0]
    assert decision.state is PortfolioDecisionState.REDUCE
    assert decision.approved_allocation == Decimal("0.050000000000")


def test_duplicate_instrument_holds_without_new_exposure() -> None:
    duplicate = holding(instrument())
    decision = evaluate_portfolio(request(snapshot(holdings=(duplicate,))))[0]
    assert decision.state is PortfolioDecisionState.HOLD
    assert decision.approved_allocation == 0
    assert "existing canonical instrument exposure requires hold" in decision.reasons


def test_sector_diversification_limit_reduces_allocation() -> None:
    existing = holding(exposure=Decimal("38000"))
    original = request(snapshot(holdings=(existing,)))
    classified = dataclasses.replace(original.proposed_positions[0], instrument=instrument())
    decision_request = PortfolioDecisionRequest(
        original.decision_request_id,
        original.ranking_result_id,
        original.portfolio_snapshot,
        (classified,),
    )
    decision = evaluate_portfolio(decision_request)[0]
    assert decision.state is PortfolioDecisionState.REDUCE
    assert decision.approved_allocation == Decimal("0.020000000000")
    assert "sector exposure limit constrains diversification" in decision.reasons


def test_single_asset_concentration_limit_is_enforced() -> None:
    decision = evaluate_portfolio(
        request(),
        PortfolioParameters(maximum_single_asset_exposure=Decimal("0.05")),
    )[0]
    assert decision.state is PortfolioDecisionState.REDUCE
    assert decision.approved_allocation == Decimal("0.050000000000")


def test_maximum_position_boundary_is_exact() -> None:
    decision = evaluate_portfolio(
        request(),
        PortfolioParameters(maximum_position_allocation=Decimal("0.082")),
    )[0]
    assert decision.state is PortfolioDecisionState.ACCEPT
    assert decision.approved_allocation == Decimal("0.082000000000")


def test_decision_records_versions_parameters_reasons_and_complete_evidence() -> None:
    existing = holding()
    decision = evaluate_portfolio(request(snapshot(holdings=(existing,))))[0]
    assert decision.decision_algorithm_version == PORTFOLIO_ALGORITHM_VERSION == "v1"
    assert tuple(name for name, _ in decision.policy_versions) == tuple(
        sorted(name for name, _ in decision.policy_versions)
    )
    assert decision.effective_parameters == PortfolioParameters().canonical_items()
    assert len(decision.reasons) == len(decision.policy_versions)
    evidence_ids = {item.referenced_id for item in decision.evidence}
    assert {"portfolio-observation", "holding-valuation"} <= evidence_ids


def test_policy_parameter_change_changes_identity() -> None:
    decision_request = request()
    first = evaluate_portfolio(decision_request)[0]
    second = evaluate_portfolio(
        decision_request,
        PortfolioParameters(cash_reserve_ratio=Decimal("0.05")),
    )[0]
    assert first.portfolio_decision_id != second.portfolio_decision_id


def test_output_is_deeply_immutable() -> None:
    decision = evaluate_portfolio(request())[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.state = PortfolioDecisionState.REJECT
    assert not isinstance(decision.reasons, list)


def test_empty_request_produces_no_decisions() -> None:
    original = request()
    empty = PortfolioDecisionRequest(
        "empty-request",
        original.ranking_result_id,
        original.portfolio_snapshot,
        (),
    )
    assert evaluate_portfolio(empty) == ()


def test_unclassified_instrument_does_not_fabricate_sector() -> None:
    original = request()
    unclassified = dataclasses.replace(
        original.proposed_positions[0],
        instrument=instrument("BBG-UNCLASSIFIED", "OTHER", sector=None),
    )
    decision_request = PortfolioDecisionRequest(
        "unclassified-request",
        original.ranking_result_id,
        original.portfolio_snapshot,
        (unclassified,),
    )
    decision = evaluate_portfolio(decision_request)[0]
    assert decision.state is PortfolioDecisionState.ACCEPT
    assert "sector policy is not applicable to an unclassified instrument" in decision.reasons


@pytest.mark.parametrize(
    "changes",
    [
        {"cash_reserve_ratio": Decimal("-0.01")},
        {"maximum_position_allocation": Decimal("0")},
        {"maximum_sector_exposure": Decimal("1.01")},
        {"maximum_single_asset_exposure": Decimal("0")},
    ],
)
def test_invalid_parameters_are_rejected(changes: dict[str, Decimal]) -> None:
    with pytest.raises(ValueError):
        dataclasses.replace(PortfolioParameters(), **changes)


def test_v1_identity_regression_vector() -> None:
    decision = evaluate_portfolio(request())[0]
    assert decision.portfolio_decision_id == (
        "5c6a980f268389799d24bac468842568535257b727539216c49d846e018eef0e"
    )
