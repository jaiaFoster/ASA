from fastapi.testclient import TestClient

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from asa.integrations.providers.deterministic_fake import DeterministicFakeQuoteProvider
from asa.integrations.providers.deterministic_fake_broker import (
    DeterministicFakeBrokerPortfolioProvider,
)
from tests.fakes import InMemoryObservationRepository


def test_build_application_activates_injected_dependencies() -> None:
    provider = DeterministicFakeQuoteProvider()
    broker_provider = DeterministicFakeBrokerPortfolioProvider()
    repository = InMemoryObservationRepository()
    app = build_application(
        Settings(),
        DependencyOverrides(
            quote_provider=provider,
            repository=repository,
            broker_provider=broker_provider,
        ),
    )

    assert app.state.dependencies["quote_provider"] is provider
    assert app.state.dependencies["repository"] is repository
    assert app.state.dependencies["broker_provider"] is broker_provider
    assert app.state.dependencies["portfolio_runner"]._provider is broker_provider
    assert TestClient(app).get("/api/v1/health").json() == {"status": "ok"}
