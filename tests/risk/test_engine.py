from dataclasses import replace
from decimal import Decimal

from domain.execution import RiskDecisionState
from domain.operational import RiskPolicyType
from portfolio.engine import evaluate_portfolio, reduction_candidates
from risk.engine import evaluate_risk
from tests.portfolio.helpers import policy, request


def test_permissive_platform_policies_approve_deterministically() -> None:
    evaluation_request = request()
    result = evaluate_portfolio(evaluation_request)[0]
    first = evaluate_risk(result, evaluation_request.portfolio_snapshot)
    second = evaluate_risk(result, evaluation_request.portfolio_snapshot)
    assert first == second
    assert first.decision is RiskDecisionState.APPROVE
    assert first.approved_delta is not None


def test_maximum_loss_policy_rejects_without_plan() -> None:
    evaluation_request = request()
    result = evaluate_portfolio(evaluation_request)[0]
    restrictive = policy(RiskPolicyType.MAXIMUM_LOSS, (("maximum_amount", Decimal("0")),))
    policy_set = tuple(
        restrictive if item.policy_type is RiskPolicyType.MAXIMUM_LOSS else item
        for item in evaluation_request.portfolio_snapshot.portfolio.platform_risk_policies
    )
    source = replace(
        evaluation_request.portfolio_snapshot,
        portfolio=replace(
            evaluation_request.portfolio_snapshot.portfolio,
            platform_risk_policies=policy_set,
        ),
    )
    decision = evaluate_risk(result, source)
    assert decision.decision is RiskDecisionState.REJECT
    assert decision.approved_delta is None


def test_failing_ceiling_selects_greatest_passing_increment() -> None:
    evaluation_request = request()
    result = evaluate_portfolio(evaluation_request)[0]
    restrictive = policy(
        RiskPolicyType.MAX_POSITION_ALLOCATION,
        (("maximum_ratio", Decimal("0.04")),),
    )
    policy_set = tuple(
        restrictive if item.policy_type is RiskPolicyType.MAX_POSITION_ALLOCATION else item
        for item in evaluation_request.portfolio_snapshot.portfolio.platform_risk_policies
    )
    source = replace(
        evaluation_request.portfolio_snapshot,
        portfolio=replace(
            evaluation_request.portfolio_snapshot.portfolio,
            platform_risk_policies=policy_set,
        ),
    )
    candidates = reduction_candidates(result, source)
    decision = evaluate_risk(result, source, reduced_candidates=candidates)
    assert decision.decision is RiskDecisionState.REDUCE
    assert decision.approved_delta is not None
    assert decision.approved_delta.target_quantity < result.proposed_delta.target_quantity  # type: ignore[union-attr]
    assert decision.approved_delta.predecessor_delta_id is not None
