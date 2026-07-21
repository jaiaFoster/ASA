from dataclasses import replace
from decimal import Decimal

from domain.execution import PortfolioEvaluationDisposition
from domain.operational import MonetaryAmount, PortfolioSnapshot
from portfolio.engine import evaluate_portfolio
from tests.portfolio.helpers import EVIDENCE, request, snapshot


def test_portfolio_engine_sizes_from_snapshot_not_proposal_reference_capital() -> None:
    item = evaluate_portfolio(request())[0]
    assert item.disposition is PortfolioEvaluationDisposition.DELTA_PRODUCED
    assert item.proposed_delta is not None
    assert item.proposed_delta.target_quantity > 0
    assert "reference_capital" not in dict(request().proposed_positions[0].effective_parameters)


def test_replay_is_stable() -> None:
    assert evaluate_portfolio(request()) == evaluate_portfolio(request())


def test_stale_loss_sign_becomes_non_negative_projected_loss() -> None:
    delta = evaluate_portfolio(request())[0].proposed_delta
    assert delta is not None
    assert delta.projected_maximum_loss.amount >= 0


def test_same_target_is_represented_by_identified_no_change_result() -> None:
    first = evaluate_portfolio(request())[0]
    assert first.proposed_delta is not None
    base = snapshot()
    value = base.instrument_valuations[0]
    quantity = first.proposed_delta.target_quantity
    from domain.operational import Position, PositionDirection

    position = Position(
        "position-1", base.portfolio.account_id, value.instrument, PositionDirection.LONG,
        quantity, value.quantity_increment, value.current_price, value.current_price,
        value.price_multiplier, value.unit_exposure,
        MonetaryAmount(quantity * value.unit_exposure.amount, "USD"),
        MonetaryAmount(quantity * value.unit_exposure.amount, "USD"),
        MonetaryAmount(Decimal("0"), "USD"), MonetaryAmount(Decimal("0"), "USD"),
        value.valued_at, EVIDENCE,
    )
    exposure = quantity * value.unit_exposure.amount
    changed_portfolio = replace(
        base.portfolio,
        positions=(position,),
        cash_balance=MonetaryAmount(
            base.portfolio.net_liquidation_value.amount - exposure,
            "USD",
        ),
        gross_exposure=MonetaryAmount(exposure, "USD"),
    )
    no_change_snapshot = PortfolioSnapshot(
        "snapshot-2", changed_portfolio, base.instrument_valuations, base.observed_at, EVIDENCE
    )
    result = evaluate_portfolio(request(no_change_snapshot))[0]
    assert result.disposition is PortfolioEvaluationDisposition.NO_CHANGE
    assert result.proposed_delta is None
    assert result.portfolio_evaluation_result_id
