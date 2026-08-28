from datetime import UTC, datetime

from asa.application.portfolio_use_cases import RunPortfolioIntelligence
from asa.application.portfolio_valuation import (
    project_exit_state,
    project_portfolio_valuation,
)
from asa.contracts.portfolio_valuation import (
    DeclaredExitState,
    ExitPolicyStatus,
    ValueAuthority,
)
from asa.integrations.providers.deterministic_fake_broker import (
    DeterministicFakeBrokerPortfolioProvider,
)

NOW = datetime(2026, 8, 28, 12, tzinfo=UTC)


def _snapshot():
    provider = DeterministicFakeBrokerPortfolioProvider()
    return RunPortfolioIntelligence._normalize(
        provider.fetch_accounts(), provider.fetch_positions()
    )


def test_uses_broker_account_value_and_keeps_unavailable_position_values_unknown() -> None:
    projection = project_portfolio_valuation(_snapshot())

    assert projection.accounts[0].total_value.authority is ValueAuthority.BROKER_OBSERVED
    assert str(projection.accounts[0].total_value.amount) == "50000.00"
    assert projection.accounts[0].profit_and_loss.authority is ValueAuthority.UNKNOWN
    assert all(
        item.market_value.unknown_reason == "broker_position_value_unavailable"
        for item in (*projection.equity_positions, *projection.option_legs)
    )


def test_missing_exit_policy_is_not_defined_and_declared_state_is_only_passed_through() -> None:
    absent = project_exit_state(evaluated_at=NOW, declared=None)
    assert absent.status is ExitPolicyStatus.NOT_DEFINED
    assert absent.policy_id is None

    declared = DeclaredExitState(
        policy_id="authorized-policy",
        policy_version="1.0.0",
        status=ExitPolicyStatus.ACTIVE,
        reason="strategy_owned_condition_not_triggered",
        evaluated_at=NOW,
    )
    assert project_exit_state(evaluated_at=NOW, declared=declared) == absent.__class__(
        status=ExitPolicyStatus.ACTIVE,
        policy_id="authorized-policy",
        policy_version="1.0.0",
        reason="strategy_owned_condition_not_triggered",
        evaluated_at=NOW,
    )
