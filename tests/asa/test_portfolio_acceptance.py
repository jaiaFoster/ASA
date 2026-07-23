import os
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from asa.integrations.providers.deterministic_fake_broker import (
    DeterministicFakeBrokerPortfolioProvider,
)
from asa.integrations.runs_postgres import PostgresRunPublicationRepository
from tests.asa.fakes import InMemoryObservationRepository

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv("ASA_TEST_DATABASE_URL"),
        reason="ASA_TEST_DATABASE_URL not set",
    ),
]


@pytest.fixture
def portfolio_client() -> TestClient:
    database_url = os.environ["ASA_TEST_DATABASE_URL"]
    os.environ["ASA_DATABASE_URL"] = database_url
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE publication_pointer, publications, option_legs, equity_positions, "
                "broker_accounts, portfolio_snapshots, run_steps, runs CASCADE"
            )
        )
    provider = DeterministicFakeBrokerPortfolioProvider()
    app = build_application(
        Settings(database_url=database_url),
        DependencyOverrides(
            repository=InMemoryObservationRepository(),
            run_repository=PostgresRunPublicationRepository(engine),
            broker_provider=provider,
        ),
    )
    return TestClient(app)


def test_successful_run_publishes_portfolio_and_provider_free_reads(
    portfolio_client: TestClient,
) -> None:
    response = portfolio_client.post(
        "/api/v1/runs",
        json={
            "requested_at": datetime.now(UTC).isoformat(),
            "release_sha": "release-success",
            "effective_config_hash": "config-success",
        },
    )
    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "succeeded"
    assert [step["status"] for step in run["steps"]] == ["succeeded"] * 4

    provider = portfolio_client.app.state.dependencies["broker_provider"]
    provider.fetch_accounts = lambda: (_ for _ in ()).throw(AssertionError("provider called"))
    provider.fetch_positions = lambda: (_ for _ in ()).throw(AssertionError("provider called"))
    portfolio = portfolio_client.get("/api/v1/portfolio")
    positions = portfolio_client.get("/api/v1/positions")

    assert portfolio.status_code == positions.status_code == 200
    portfolio_body = portfolio.json()
    positions_body = positions.json()
    assert portfolio_body["run"]["id"] == positions_body["run"]["id"] == run["id"]
    assert portfolio_body["data"]["publication_id"] == positions_body["data"]["publication_id"]
    assert portfolio_body["data"]["account_count"] == 1
    assert portfolio_body["data"]["equity_position_count"] == 1
    assert portfolio_body["data"]["option_leg_count"] == 2
    assert len(positions_body["data"]["equity_positions"]) == 1
    assert len(positions_body["data"]["option_legs"]) == 2


def test_failed_run_preserves_publication_and_discloses_last_success(
    portfolio_client: TestClient,
) -> None:
    successful = portfolio_client.post(
        "/api/v1/runs",
        json={
            "requested_at": datetime.now(UTC).isoformat(),
            "release_sha": "release-a",
            "effective_config_hash": "config-a",
        },
    ).json()
    provider = portfolio_client.app.state.dependencies["broker_provider"]
    positions = provider.fetch_positions()
    invalid_leg = replace(positions.option_legs[0], option_symbol="")
    provider.fetch_positions = lambda: replace(positions, option_legs=(invalid_leg,))
    failed = portfolio_client.post(
        "/api/v1/runs",
        json={
            "requested_at": datetime.now(UTC).isoformat(),
            "release_sha": "release-b",
            "effective_config_hash": "config-b",
        },
    ).json()

    portfolio = portfolio_client.get("/api/v1/portfolio").json()
    assert failed["status"] == "failed"
    assert failed["steps"][2]["status"] == "failed"
    assert failed["publication_id"] is None
    assert portfolio["run"]["id"] == successful["id"]
    assert portfolio["freshness"]["serving_last_success"] is True


def test_account_only_portfolio_can_be_published(portfolio_client: TestClient) -> None:
    provider = portfolio_client.app.state.dependencies["broker_provider"]
    positions = provider.fetch_positions()
    provider.fetch_positions = lambda: replace(positions, equities=(), option_legs=())

    run = portfolio_client.post(
        "/api/v1/runs",
        json={
            "requested_at": datetime.now(UTC).isoformat(),
            "release_sha": "release-account-only",
            "effective_config_hash": "config-account-only",
        },
    ).json()
    portfolio = portfolio_client.get("/api/v1/portfolio").json()

    assert run["status"] == "succeeded"
    assert portfolio["data"]["account_count"] == 1
    assert portfolio["data"]["equity_position_count"] == 0
    assert portfolio["data"]["option_leg_count"] == 0


def test_failed_broker_acquisition_preserves_last_success(
    portfolio_client: TestClient,
) -> None:
    successful = portfolio_client.post(
        "/api/v1/runs",
        json={
            "requested_at": datetime.now(UTC).isoformat(),
            "release_sha": "release-before-provider-failure",
            "effective_config_hash": "config-before-provider-failure",
        },
    ).json()
    provider = portfolio_client.app.state.dependencies["broker_provider"]
    provider.fetch_accounts = lambda: (_ for _ in ()).throw(
        RuntimeError("sanitized broker acquisition failure")
    )

    failed = portfolio_client.post(
        "/api/v1/runs",
        json={
            "requested_at": datetime.now(UTC).isoformat(),
            "release_sha": "release-provider-failure",
            "effective_config_hash": "config-provider-failure",
        },
    ).json()
    portfolio = portfolio_client.get("/api/v1/portfolio").json()

    assert failed["status"] == "failed"
    assert failed["steps"][0]["status"] == "failed"
    assert portfolio["run"]["id"] == successful["id"]
    assert portfolio["freshness"]["serving_last_success"] is True
