from fastapi.testclient import TestClient

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from asa.integrations.providers.deterministic_fake import DeterministicFakeQuoteProvider
from tests.fakes import InMemoryObservationRepository


def test_build_application_activates_injected_dependencies() -> None:
    provider = DeterministicFakeQuoteProvider()
    repository = InMemoryObservationRepository()
    app = build_application(
        Settings(),
        DependencyOverrides(quote_provider=provider, repository=repository),
    )

    assert app.state.dependencies["quote_provider"] is provider
    assert app.state.dependencies["repository"] is repository
    assert TestClient(app).get("/api/v1/health").json() == {"status": "ok"}
