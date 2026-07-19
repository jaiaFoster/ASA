from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from asa.application.portfolio_use_cases import PublishedPortfolioQuery, RunPortfolioIntelligence
from asa.domain.market import FreshnessStatus
from asa.domain.portfolio import PublishedPortfolio, validate_snapshot
from asa.domain.runs import RunRecord, RunStatus
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
