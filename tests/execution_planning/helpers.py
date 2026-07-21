"""Fixtures for deterministic Execution Planner tests."""

from __future__ import annotations

from decimal import Decimal

from domain.execution import ExecutionContext, PortfolioDecision
from domain.operational import MonetaryAmount, PositionDirection
from execution_planning.engine import plan_execution
from portfolio.engine import evaluate_portfolio
from tests.portfolio.helpers import PORTFOLIO_EVIDENCE, request


def decision() -> PortfolioDecision:
    return evaluate_portfolio(request())[0]


def context(
    *,
    current_direction: PositionDirection | None = None,
    current_quantity: Decimal = Decimal("0"),
    unit_exposure: Decimal = Decimal("200"),
    quantity_increment: Decimal = Decimal("1"),
) -> ExecutionContext:
    portfolio_decision = decision()
    return ExecutionContext(
        "execution-context-1",
        portfolio_decision.portfolio_snapshot_id,
        "account-1",
        portfolio_decision.proposed_position.instrument.identity,
        current_direction,
        current_quantity,
        MonetaryAmount(unit_exposure, portfolio_decision.proposed_position.instrument.currency),
        quantity_increment,
        PORTFOLIO_EVIDENCE,
    )


def plan():  # type: ignore[no-untyped-def]
    return plan_execution(decision(), context())
