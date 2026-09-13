from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from asa.contracts.market import MarketObservation
from asa.contracts.portfolio import EquityPosition, PortfolioSnapshot
from asa.contracts.portfolio_valuation import (
    AccountValuation,
    DeclaredExitState,
    ExitPolicyStatus,
    ExitStateProjection,
    FactLineage,
    FactReference,
    MonetaryValue,
    PortfolioValuationProjection,
    PositionValuation,
    ValueAuthority,
)


def project_portfolio_valuation(
    snapshot: PortfolioSnapshot,
    quotes_by_symbol: Mapping[str, MarketObservation] | None = None,
    *,
    snapshot_id: UUID | None = None,
    computed_at: datetime | None = None,
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
    calculated_at = computed_at or snapshot.observed_at
    snapshot_ref = None if snapshot_id is None else str(snapshot_id)
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
                    lineage=_broker_lineage(
                        fact_id=f"account:{account.id}:account_value",
                        semantic_name="broker_account_value",
                        source=account.provider,
                        observed_at=account.observed_at,
                        fetched_at=snapshot.observed_at,
                        snapshot_id=snapshot_ref,
                    ),
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
            position,
            account_currency[position.account_id],
            quotes.get(position.symbol),
            snapshot_observed_at=snapshot.observed_at,
            snapshot_id=snapshot_ref,
            computed_at=calculated_at,
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
            profit_and_loss_percent=_unknown(
                "%", leg.observed_at, "broker_position_pnl_unavailable"
            ),
        )
        for leg in snapshot.option_legs
    )
    return PortfolioValuationProjection(accounts, equities, option_legs)


def _equity_valuation(
    position: EquityPosition,
    currency: str,
    quote: MarketObservation | None,
    *,
    snapshot_observed_at: datetime,
    snapshot_id: str | None,
    computed_at: datetime,
) -> PositionValuation:
    key = f"{position.account_id}:equity:{position.symbol}"
    if quote is None:
        return PositionValuation(
            key,
            _unknown(currency, position.observed_at, "canonical_price_unavailable"),
            _unknown(currency, position.observed_at, "canonical_price_unavailable"),
            _unknown("%", position.observed_at, "canonical_price_unavailable"),
        )
    if quote.currency != currency:
        return PositionValuation(
            key,
            _unknown(currency, position.observed_at, "canonical_price_currency_mismatch"),
            _unknown(currency, position.observed_at, "canonical_price_currency_mismatch"),
            _unknown("%", position.observed_at, "canonical_price_currency_mismatch"),
        )
    quantity = _broker_reference(position, "quantity", snapshot_observed_at, snapshot_id)
    price = _quote_reference(quote)
    market_value = MonetaryValue(
        amount=position.quantity * quote.price,
        currency=currency,
        authority=ValueAuthority.DERIVED,
        observed_at=quote.observed_at,
        lineage=_derived_lineage(
            key,
            "portfolio_market_value",
            quote,
            computed_at,
            snapshot_id,
            "quantity_times_canonical_price",
            (quantity, price),
        ),
    )
    if position.average_cost is None:
        profit_and_loss = _unknown(currency, position.observed_at, "broker_cost_basis_unavailable")
        profit_and_loss_percent = _unknown(
            "%", position.observed_at, "broker_cost_basis_unavailable"
        )
    else:
        average_cost = _broker_reference(
            position, "average_cost", snapshot_observed_at, snapshot_id
        )
        inputs = (quantity, average_cost, price)
        pnl_amount = (quote.price - position.average_cost) * position.quantity
        profit_and_loss = MonetaryValue(
            amount=pnl_amount,
            currency=currency,
            authority=ValueAuthority.DERIVED,
            observed_at=quote.observed_at,
            lineage=_derived_lineage(
                key,
                "portfolio_unrealized_pnl",
                quote,
                computed_at,
                snapshot_id,
                "canonical_price_minus_average_cost_times_quantity",
                inputs,
            ),
        )
        cost = position.average_cost * position.quantity
        profit_and_loss_percent = (
            _unknown("%", position.observed_at, "zero_cost_basis")
            if cost == 0
            else MonetaryValue(
                amount=(pnl_amount / cost) * Decimal("100"),
                currency="%",
                authority=ValueAuthority.DERIVED,
                observed_at=quote.observed_at,
                lineage=_derived_lineage(
                    key,
                    "portfolio_unrealized_pnl_percent",
                    quote,
                    computed_at,
                    snapshot_id,
                    "unrealized_pnl_divided_by_cost_basis_percent",
                    inputs,
                ),
            )
        )
    return PositionValuation(key, market_value, profit_and_loss, profit_and_loss_percent)


def _broker_reference(
    position: EquityPosition, name: str, fetched_at: datetime, snapshot_id: str | None
) -> FactReference:
    return FactReference(
        fact_id=f"{position.account_id}:equity:{position.symbol}:{name}",
        semantic_name=f"broker_{name}",
        source=position.original_provider,
        observed_at=position.observed_at,
        fetched_at=fetched_at,
        snapshot_id=snapshot_id,
    )


def _quote_reference(quote: MarketObservation) -> FactReference:
    return FactReference(
        fact_id=f"market_quote:{quote.symbol}:{quote.provenance.provider_request_id}",
        semantic_name="canonical_current_price",
        source=quote.provenance.original_provider,
        observed_at=quote.observed_at,
        fetched_at=quote.received_at,
        snapshot_id=quote.provenance.provider_request_id,
    )


def _derived_lineage(
    position_key: str,
    semantic_name: str,
    quote: MarketObservation,
    computed_at: datetime,
    snapshot_id: str | None,
    formula_id: str,
    inputs: tuple[FactReference, ...],
) -> FactLineage:
    return FactLineage(
        fact_id=f"{position_key}:{semantic_name}",
        semantic_name=semantic_name,
        source="asa",
        observed_at=quote.observed_at,
        fetched_at=quote.received_at,
        computed_at=computed_at,
        snapshot_id=snapshot_id,
        freshness_status=quote.provenance.freshness_status.value,
        usability_status="usable",
        formula_id=formula_id,
        formula_version="1.0.0",
        inputs=inputs,
    )


def _broker_lineage(
    *,
    fact_id: str,
    semantic_name: str,
    source: str,
    observed_at: datetime,
    fetched_at: datetime,
    snapshot_id: str | None,
) -> FactLineage:
    return FactLineage(
        fact_id=fact_id,
        semantic_name=semantic_name,
        source=source,
        observed_at=observed_at,
        fetched_at=fetched_at,
        computed_at=None,
        snapshot_id=snapshot_id,
        freshness_status="observed",
        usability_status="usable",
    )


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
