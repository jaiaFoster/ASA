from datetime import datetime

from asa.contracts.portfolio import PortfolioSnapshot
from asa.contracts.portfolio_valuation import (
    AccountValuation,
    DeclaredExitState,
    ExitPolicyStatus,
    ExitStateProjection,
    MonetaryValue,
    PortfolioValuationProjection,
    PositionValuation,
    ValueAuthority,
)


def project_portfolio_valuation(snapshot: PortfolioSnapshot) -> PortfolioValuationProjection:
    account_currency = {account.id: account.currency for account in snapshot.accounts}
    accounts = tuple(
        AccountValuation(
            account_id=account.id,
            total_value=(
                _unknown(account.currency, account.observed_at, "broker_value_unavailable")
                if account.account_value is None
                else MonetaryValue(
                    amount=account.account_value,
                    currency=account.currency,
                    authority=ValueAuthority.BROKER_OBSERVED,
                    observed_at=account.observed_at,
                )
            ),
            profit_and_loss=_unknown(
                account.currency, account.observed_at, "broker_pnl_unavailable"
            ),
        )
        for account in snapshot.accounts
    )
    equities = tuple(
        PositionValuation(
            position_key=f"{position.account_id}:equity:{position.symbol}",
            market_value=_unknown(
                account_currency[position.account_id],
                position.observed_at,
                "broker_position_value_unavailable",
            ),
            profit_and_loss=_unknown(
                account_currency[position.account_id],
                position.observed_at,
                "broker_position_pnl_unavailable",
            ),
        )
        for position in snapshot.equity_positions
    )
    option_legs = tuple(
        PositionValuation(
            position_key=f"{leg.account_id}:option:{leg.option_symbol}",
            market_value=_unknown(
                account_currency[leg.account_id],
                leg.observed_at,
                "broker_position_value_unavailable",
            ),
            profit_and_loss=_unknown(
                account_currency[leg.account_id],
                leg.observed_at,
                "broker_position_pnl_unavailable",
            ),
        )
        for leg in snapshot.option_legs
    )
    return PortfolioValuationProjection(accounts, equities, option_legs)


def project_exit_state(
    *, evaluated_at: datetime, declared: DeclaredExitState | None
) -> ExitStateProjection:
    """Pass through strategy-owned state; absence remains explicitly undefined."""
    if declared is None:
        return ExitStateProjection(
            status=ExitPolicyStatus.NOT_DEFINED,
            policy_id=None,
            policy_version=None,
            reason="strategy_exit_policy_not_defined",
            evaluated_at=evaluated_at,
        )
    return ExitStateProjection(
        status=declared.status,
        policy_id=declared.policy_id,
        policy_version=declared.policy_version,
        reason=declared.reason,
        evaluated_at=declared.evaluated_at,
    )


def _unknown(currency: str, observed_at: datetime, reason: str) -> MonetaryValue:
    return MonetaryValue(
        amount=None,
        currency=currency,
        authority=ValueAuthority.UNKNOWN,
        observed_at=observed_at,
        unknown_reason=reason,
    )
