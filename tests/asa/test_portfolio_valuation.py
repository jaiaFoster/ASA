from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from asa.application.portfolio_use_cases import RunPortfolioIntelligence
from asa.application.portfolio_valuation import (
    project_exit_state,
    project_portfolio_valuation,
)
from asa.contracts.market import CacheStatus, FreshnessStatus, MarketObservation, QuoteProvenance
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


def _quote(symbol: str, price: str, currency: str = "USD") -> MarketObservation:
    return MarketObservation(
        symbol=symbol,
        price=Decimal(price),
        currency=currency,
        observed_at=NOW,
        received_at=NOW,
        provenance=QuoteProvenance(
            selected_provider="test_provider",
            original_provider="test_provider",
            cache_status=CacheStatus.PERSISTED,
            freshness_status=FreshnessStatus.FRESH,
            fallback_reason=None,
            provider_request_id="test-request",
        ),
    )


def test_uses_broker_account_value_and_keeps_unavailable_position_values_unknown() -> None:
    projection = project_portfolio_valuation(_snapshot())

    assert projection.accounts[0].total_value.authority is ValueAuthority.BROKER_OBSERVED
    assert str(projection.accounts[0].total_value.amount) == "50000.00"
    assert projection.accounts[0].profit_and_loss.authority is ValueAuthority.UNKNOWN
    # No canonical quote was supplied at all -- every equity reads the
    # canonical-price-specific reason, never the broker one (Robinhood's
    # own integration never fetches a per-position price to begin with).
    assert all(
        item.market_value.unknown_reason == "canonical_price_unavailable"
        for item in projection.equity_positions
    )
    # Option legs have no canonical quote lookup at all -- unaffected.
    assert all(
        item.market_value.unknown_reason == "broker_position_value_unavailable"
        for item in projection.option_legs
    )


def test_equity_market_value_and_pnl_are_derived_from_the_canonical_quote() -> None:
    snapshot = _snapshot()
    (position,) = snapshot.equity_positions  # AAPL, quantity=12, average_cost=172.50
    projection = project_portfolio_valuation(snapshot, {"AAPL": _quote("AAPL", "200.00")})

    (valuation,) = projection.equity_positions
    assert valuation.market_value.authority is ValueAuthority.DERIVED
    assert valuation.market_value.amount == Decimal("2400.00")
    assert valuation.profit_and_loss.authority is ValueAuthority.DERIVED
    assert valuation.profit_and_loss.amount == Decimal("330.00")


def test_equity_pnl_stays_unknown_without_a_broker_cost_basis() -> None:
    snapshot = _snapshot()
    no_cost_basis = replace(snapshot.equity_positions[0], average_cost=None)
    snapshot = replace(snapshot, equity_positions=(no_cost_basis,))
    projection = project_portfolio_valuation(snapshot, {"AAPL": _quote("AAPL", "200.00")})

    (valuation,) = projection.equity_positions
    assert valuation.market_value.authority is ValueAuthority.DERIVED
    assert valuation.profit_and_loss.authority is ValueAuthority.UNKNOWN
    assert valuation.profit_and_loss.unknown_reason == "broker_cost_basis_unavailable"


def test_equity_valuation_refuses_a_currency_mismatch_rather_than_silently_convert() -> None:
    snapshot = _snapshot()
    projection = project_portfolio_valuation(snapshot, {"AAPL": _quote("AAPL", "200.00", "EUR")})

    (valuation,) = projection.equity_positions
    assert valuation.market_value.authority is ValueAuthority.UNKNOWN
    assert valuation.market_value.unknown_reason == "canonical_price_currency_mismatch"


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
