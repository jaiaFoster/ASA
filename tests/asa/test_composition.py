from fastapi.testclient import TestClient
from pydantic import SecretStr

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from asa.integrations.providers.deterministic_fake import DeterministicFakeQuoteProvider
from asa.integrations.providers.deterministic_fake_broker import (
    DeterministicFakeBrokerPortfolioProvider,
)
from tests.asa.fakes import InMemoryLatestResultRepository, InMemoryObservationRepository


def test_build_application_activates_injected_dependencies() -> None:
    provider = DeterministicFakeQuoteProvider()
    broker_provider = DeterministicFakeBrokerPortfolioProvider()
    repository = InMemoryObservationRepository()
    latest_result_repository = InMemoryLatestResultRepository()
    app = build_application(
        Settings(),
        DependencyOverrides(
            quote_provider=provider,
            repository=repository,
            broker_provider=broker_provider,
            latest_result_repository=latest_result_repository,
        ),
    )

    assert app.state.dependencies["quote_provider"] is provider
    assert app.state.dependencies["repository"] is repository
    assert app.state.dependencies["broker_provider"] is broker_provider
    assert app.state.dependencies["portfolio_runner"]._provider is broker_provider
    assert app.state.dependencies["latest_result_repository"] is latest_result_repository
    assert callable(app.state.dependencies["agent_authorize"])
    assert TestClient(app).get("/api/v1/health").json() == {"status": "ok"}


def test_default_latest_result_repository_is_postgres_backed_but_lazy() -> None:
    # No override supplied -- build_application() must still succeed
    # without a real database connection (SQLAlchemy engines connect
    # lazily), matching how run_repository/repository already behave with
    # no override in the existing test above's sibling tests.
    from asa.integrations.universal_screening_postgres import PostgresLatestResultRepository

    app = build_application(Settings())
    repository = app.state.dependencies["latest_result_repository"]
    assert isinstance(repository, PostgresLatestResultRepository)


def test_api_version_header_is_present_on_every_response() -> None:
    app = build_application(
        Settings(),
        DependencyOverrides(repository=InMemoryObservationRepository()),
    )
    response = TestClient(app).get("/api/v1/health")
    assert response.headers["API-Version"] == "v1"


def test_public_version_endpoint_reports_configured_build_identity() -> None:
    app = build_application(
        Settings(application_version="2.4.1", release_sha="abc123def"),
        DependencyOverrides(repository=InMemoryObservationRepository()),
    )

    response = TestClient(app).get("/api/v1/version")

    assert response.status_code == 200
    assert response.json() == {
        "application_version": "2.4.1",
        "api_version": "v1",
        "release_sha": "abc123def",
    }


def test_public_version_endpoint_discloses_unavailable_release_explicitly() -> None:
    app = build_application(
        Settings(),
        DependencyOverrides(repository=InMemoryObservationRepository()),
    )

    assert TestClient(app).get("/api/v1/version").json()["release_sha"] is None


def test_agent_api_token_setting_reaches_the_authorizer() -> None:
    app = build_application(
        Settings(agent_api_token=SecretStr("agent-token")),
        DependencyOverrides(repository=InMemoryObservationRepository()),
    )
    from starlette.requests import Request

    authorize = app.state.dependencies["agent_authorize"]
    request = Request({"type": "http", "headers": [(b"authorization", b"Bearer agent-token")]})
    authorize(request)  # does not raise
