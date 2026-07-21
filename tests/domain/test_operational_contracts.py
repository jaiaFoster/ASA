import dataclasses

from domain.operational import (
    InstrumentValuation,
    Portfolio,
    PortfolioEvaluationRequest,
    PortfolioSnapshot,
    Position,
    ProposedPosition,
    RiskPolicy,
)


def test_arch_006_operational_contracts_are_immutable() -> None:
    for contract in (
        InstrumentValuation, Portfolio, PortfolioEvaluationRequest, PortfolioSnapshot,
        Position, ProposedPosition, RiskPolicy,
    ):
        assert dataclasses.is_dataclass(contract)
        assert contract.__dataclass_params__.frozen


def test_superseded_operational_contract_names_are_absent() -> None:
    import domain.operational as operational

    assert not hasattr(operational, "Holding")
    assert not hasattr(operational, "PortfolioDecisionRequest")


def test_proposed_position_has_no_reference_capital_or_portfolio_state() -> None:
    names = {field.name for field in dataclasses.fields(ProposedPosition)}
    assert "reference_capital" not in names
    assert "portfolio" not in names
    assert "account_id" not in names
