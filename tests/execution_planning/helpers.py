from portfolio.engine import evaluate_portfolio
from risk.engine import evaluate_risk
from tests.portfolio.helpers import request


def decision():  # type: ignore[no-untyped-def]
    evaluation_request = request()
    result = evaluate_portfolio(evaluation_request)[0]
    return evaluate_risk(result, evaluation_request.portfolio_snapshot)


def snapshot():  # type: ignore[no-untyped-def]
    return request().portfolio_snapshot
