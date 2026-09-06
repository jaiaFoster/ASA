from collections.abc import Mapping
from datetime import datetime

from asa.contracts.market import MarketObservation
from asa.contracts.portfolio import EquityPosition, PortfolioSnapshot
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


def project_portfolio_valuation(
    snapshot: PortfolioSnapshot,
    quotes_by_symbol: Mapping[str, MarketObservation] | None = None,
) -> PortfolioValuationProjection:
    """Broker (asa/integrations/providers/robinhood.py) remains the sole
    authority for account identity, quantity, and cost basis -- nothing
    here acquires a quote. ``quotes_by_symbol`` is a caller-supplied,
    already-read lookup from ASA's own existing canonical market-data
    authority (asa.application.use_cases.MarketQuoteService.get_latest_quote,
    a pure read against the persisted market_observations table -- never a
    new acquisition/provider call issued by this module or its caller).
    Equity market value/P&L are DERIVED from that canonical price where
    one is available for the position's own symbol and currency; option
    legs are unaffected (no options capability exists in that lookup) and
    stay exactly as before. Account-level total_value/profit_and_loss are
    also unaffected -- Robinhood's own broker-computed account equity
    remains BROKER_OBSERVED, never silently blended with canonical pricing.
    """
    quotes = quotes_by_symbol or {}
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
        _equity_valuation(
            position, account_currency[position.account_id], quotes.get(position.symbol)
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


def _equity_valuation(
    position: EquityPosition, currency: str, quote: MarketObservation | None
) -> PositionValuation:
    key = f"{position.account_id}:equity:{position.symbol}"
    if quote is None:
        return PositionValuation(
            key,
            _unknown(currency, position.observed_at, "canonical_price_unavailable"),
            _unknown(currency, position.observed_at, "canonical_price_unavailable"),
        )
    if quote.currency != currency:
        return PositionValuation(
            key,
            _unknown(currency, position.observed_at, "canonical_price_currency_mismatch"),
            _unknown(currency, position.observed_at, "canonical_price_currency_mismatch"),
        )
    market_value = MonetaryValue(
        amount=position.quantity * quote.price,
        currency=currency,
        authority=ValueAuthority.DERIVED,
        observed_at=quote.observed_at,
    )
    if position.average_cost is None:
        profit_and_loss = _unknown(
            currency, position.observed_at, "broker_cost_basis_unavailable"
        )
    else:
        profit_and_loss = MonetaryValue(
            amount=(quote.price - position.average_cost) * position.quantity,
            currency=currency,
            authority=ValueAuthority.DERIVED,
            observed_at=quote.observed_at,
        )
    return PositionValuation(key, market_value, profit_and_loss)


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
