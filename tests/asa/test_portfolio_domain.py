from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from asa.application.portfolio_use_cases import PublishedPortfolioQuery, RunPortfolioIntelligence
from asa.application.ports.brokers import ProviderAccount
from asa.contracts.market import FreshnessStatus
from asa.contracts.portfolio import (
    AccountHoldingsStatus,
    PublishedPortfolio,
    account_holdings_status,
    mask_account_identifier,
    validate_snapshot,
)
from asa.contracts.runs import RunRecord, RunStatus
from asa.integrations.providers.deterministic_fake_broker import (
    DeterministicFakeBrokerPortfolioProvider,
)


def publication_view_for_snapshot(snapshot: object, now: datetime):
    published_run = RunRecord(
        uuid4(),
        RunStatus.SUCCEEDED,
        snapshot.observed_at,
        snapshot.observed_at,
        snapshot.observed_at,
        "release-a",
        "config-a",
        None,
        None,
        (),
    )
    publication = PublishedPortfolio(
        uuid4(), published_run.id, uuid4(), snapshot.observed_at, snapshot
    )

    class QueryRepository:
        def current_portfolio(self) -> PublishedPortfolio:
            return publication

        def get_run(self, run_id: object) -> RunRecord:
            return published_run

        def latest_run(self) -> RunRecord:
            return published_run

    return PublishedPortfolioQuery(
        QueryRepository(),  # type: ignore[arg-type]
        timedelta(minutes=5),
        clock=lambda: now,
    ).current()


def test_fake_broker_normalizes_one_account_equity_and_two_option_legs() -> None:
    provider = DeterministicFakeBrokerPortfolioProvider()
    snapshot = RunPortfolioIntelligence._normalize(
        provider.fetch_accounts(), provider.fetch_positions()
    )

    validate_snapshot(snapshot)
    assert len(snapshot.accounts) == 1
    assert snapshot.accounts[0].external_account_id == "taxable-001"
    assert [item.symbol for item in snapshot.equity_positions] == ["AAPL"]
    assert [item.side.value for item in snapshot.option_legs] == ["long", "short"]


def test_option_leg_validation_rejects_missing_symbol() -> None:
    provider = DeterministicFakeBrokerPortfolioProvider()
    snapshot = RunPortfolioIntelligence._normalize(
        provider.fetch_accounts(), provider.fetch_positions()
    )
    invalid_leg = replace(snapshot.option_legs[0], option_symbol="")
    with pytest.raises(ValueError, match="option legs require"):
        validate_snapshot(replace(snapshot, option_legs=(invalid_leg,)))


def test_stale_equity_evidence_makes_portfolio_stale() -> None:
    provider = DeterministicFakeBrokerPortfolioProvider()
    accounts = provider.fetch_accounts()
    positions = provider.fetch_positions()
    stale_at = provider.observed_at - timedelta(hours=1)
    stale_equity = replace(positions.equities[0], observed_at=stale_at)
    snapshot = RunPortfolioIntelligence._normalize(
        accounts,
        replace(positions, equities=(stale_equity,)),
    )

    view = publication_view_for_snapshot(snapshot, provider.observed_at)
    assert snapshot.observed_at == stale_at
    assert view is not None
    assert view.freshness_status is FreshnessStatus.STALE


def test_stale_option_leg_evidence_makes_portfolio_stale() -> None:
    provider = DeterministicFakeBrokerPortfolioProvider()
    accounts = provider.fetch_accounts()
    positions = provider.fetch_positions()
    stale_at = provider.observed_at - timedelta(hours=1)
    stale_leg = replace(positions.option_legs[0], observed_at=stale_at)
    snapshot = RunPortfolioIntelligence._normalize(
        accounts,
        replace(positions, option_legs=(stale_leg, positions.option_legs[1])),
    )

    view = publication_view_for_snapshot(snapshot, provider.observed_at)
    assert snapshot.observed_at == stale_at
    assert view is not None
    assert view.freshness_status is FreshnessStatus.STALE


def test_account_only_publication_uses_account_observation() -> None:
    provider = DeterministicFakeBrokerPortfolioProvider()
    accounts = provider.fetch_accounts()
    positions = replace(provider.fetch_positions(), equities=(), option_legs=())
    snapshot = RunPortfolioIntelligence._normalize(accounts, positions)

    validate_snapshot(snapshot)
    view = publication_view_for_snapshot(
        snapshot,
        provider.observed_at + timedelta(minutes=1),
    )
    assert snapshot.observed_at == provider.observed_at
    assert view is not None
    assert view.freshness_status is FreshnessStatus.FRESH


def test_publication_freshness_and_last_success_are_application_fields() -> None:
    provider = DeterministicFakeBrokerPortfolioProvider()
    snapshot = RunPortfolioIntelligence._normalize(
        provider.fetch_accounts(), provider.fetch_positions()
    )
    published_run = RunRecord(
        uuid4(),
        RunStatus.SUCCEEDED,
        snapshot.observed_at,
        snapshot.observed_at,
        snapshot.observed_at,
        "release-a",
        "config-a",
        None,
        None,
        (),
    )
    failed_run = replace(
        published_run,
        id=uuid4(),
        status=RunStatus.FAILED,
        release_sha="release-b",
    )
    publication = PublishedPortfolio(
        uuid4(), published_run.id, uuid4(), snapshot.observed_at, snapshot
    )

    class QueryRepository:
        def current_portfolio(self) -> PublishedPortfolio:
            return publication

        def get_run(self, run_id: object) -> RunRecord:
            return published_run

        def latest_run(self) -> RunRecord:
            return failed_run

    view = PublishedPortfolioQuery(
        QueryRepository(),  # type: ignore[arg-type]
        timedelta(minutes=5),
        clock=lambda: datetime(2026, 7, 20, tzinfo=UTC),
    ).current()
    assert view is not None
    assert view.freshness_status is FreshnessStatus.STALE
    assert view.serving_last_success is True


def test_mask_account_identifier_keeps_only_the_last_four_characters() -> None:
    assert mask_account_identifier("RH-ACCOUNT-1234") == "***********1234"


def test_mask_account_identifier_masks_entirely_when_four_characters_or_fewer() -> None:
    assert mask_account_identifier("ab1") == "***"
    assert mask_account_identifier("ab12") == "****"


class TestAccountHoldingsStatus:
    NOW = datetime(2026, 7, 19, 12, 30, tzinfo=UTC)
    FRESH_FOR = timedelta(minutes=45)

    def test_current_with_positions_is_success(self) -> None:
        status = account_holdings_status(
            account_observed_at=self.NOW,
            has_positions=True,
            now=self.NOW,
            fresh_for=self.FRESH_FOR,
            serving_last_success=False,
        )
        assert status is AccountHoldingsStatus.SUCCESS

    def test_current_without_positions_is_success_empty(self) -> None:
        status = account_holdings_status(
            account_observed_at=self.NOW,
            has_positions=False,
            now=self.NOW,
            fresh_for=self.FRESH_FOR,
            serving_last_success=False,
        )
        assert status is AccountHoldingsStatus.SUCCESS_EMPTY

    def test_outside_the_window_after_a_failed_refresh_is_stale_fallback(self) -> None:
        status = account_holdings_status(
            account_observed_at=self.NOW - timedelta(hours=2),
            has_positions=True,
            now=self.NOW,
            fresh_for=self.FRESH_FOR,
            serving_last_success=True,
        )
        assert status is AccountHoldingsStatus.STALE_FALLBACK

    def test_outside_the_window_with_no_known_failure_is_plain_stale(self) -> None:
        status = account_holdings_status(
            account_observed_at=self.NOW - timedelta(hours=2),
            has_positions=True,
            now=self.NOW,
            fresh_for=self.FRESH_FOR,
            serving_last_success=False,
        )
        assert status is AccountHoldingsStatus.STALE


def test_per_account_holdings_status_distinguishes_holdings_from_empty_accounts() -> None:
    """A second, genuinely empty account (e.g. a Roth IRA with no positions
    yet) must read SUCCESS_EMPTY, never be confused with the funded
    taxable account's own SUCCESS -- and never with a fetch failure.
    """
    provider = DeterministicFakeBrokerPortfolioProvider()
    accounts_result = provider.fetch_accounts()
    empty_account = ProviderAccount(
        external_account_id="roth-002",
        connection_id="fake-connection-secondary",
        provider=provider.name,
        account_type="roth_ira",
        display_name="Roth IRA",
        currency="USD",
        cash_balance=None,
        cash_available_for_withdrawal=None,
        buying_power=None,
        account_value=None,
        observed_at=provider.observed_at,
    )
    accounts_result = replace(
        accounts_result, accounts=(*accounts_result.accounts, empty_account)
    )
    snapshot = RunPortfolioIntelligence._normalize(accounts_result, provider.fetch_positions())

    view = publication_view_for_snapshot(snapshot, provider.observed_at)

    assert view is not None
    assert len(snapshot.accounts) == 2
    funded = next(a for a in snapshot.accounts if a.external_account_id == "taxable-001")
    empty = next(a for a in snapshot.accounts if a.external_account_id == "roth-002")
    assert view.account_holdings[funded.id].status is AccountHoldingsStatus.SUCCESS
    assert view.account_holdings[empty.id].status is AccountHoldingsStatus.SUCCESS_EMPTY
    assert view.account_holdings[empty.id].as_of == empty.observed_at
