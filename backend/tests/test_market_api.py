from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from asa.integrations.providers.deterministic_fake import DeterministicFakeQuoteProvider
from tests.fakes import InMemoryObservationRepository


def build_test_client(
    repository: InMemoryObservationRepository,
    observed_at: datetime | None = None,
    environment: str = "development",
) -> TestClient:
    return TestClient(
        build_application(
            Settings(environment=environment),
            DependencyOverrides(
                quote_provider=DeterministicFakeQuoteProvider(observed_at=observed_at),
                repository=repository,
            ),
        )
    )


def test_ingest_then_get_reads_persisted_canonical_quote_without_provider_call() -> None:
    repository = InMemoryObservationRepository()
    client = build_test_client(repository)
    ingested = client.post("/api/v1/market/quotes/ingest", json={"symbols": ["AAPL"]})
    assert ingested.status_code == 200
    provider = client.app.state.dependencies["quote_provider"]
    provider.get_quotes = lambda symbols: (_ for _ in ()).throw(AssertionError("provider called"))

    response = client.get("/api/v1/market/quotes/AAPL")

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["price"] == "189.42000000" or body["price"] == "189.42"
    assert body["currency"] == "USD"
    assert body["provenance"]["selected_provider"] == "deterministic_fake"
    assert body["provenance"]["cache_status"] == "persisted"
    assert body["provenance"]["freshness_status"] == "fresh"
    assert body["observed_at"]


def test_stale_observation_never_reports_fresh() -> None:
    repository = InMemoryObservationRepository()
    client = build_test_client(repository, datetime.now(UTC) - timedelta(hours=1))
    response = client.post("/api/v1/market/quotes/ingest", json={"symbols": ["AAPL"]})
    assert response.json()["observations"][0]["provenance"]["freshness_status"] == "stale"
    persisted = client.get("/api/v1/market/quotes/AAPL").json()
    assert persisted["provenance"]["freshness_status"] == "stale"


def test_ingest_endpoint_is_development_only() -> None:
    response = build_test_client(InMemoryObservationRepository(), environment="production").post(
        "/api/v1/market/quotes/ingest", json={"symbols": ["AAPL"]}
    )
    assert response.status_code == 404


def test_readiness_fails_when_database_unavailable() -> None:
    response = build_test_client(InMemoryObservationRepository(healthy=False)).get(
        "/api/v1/readiness"
    )
    assert response.status_code == 503


def test_readiness_uses_database_health_not_credentials() -> None:
    assert not any("credential" in name or "api_key" in name for name in Settings.model_fields)
    response = build_test_client(InMemoryObservationRepository(healthy=True)).get(
        "/api/v1/readiness"
    )
    assert response.json() == {"status": "ready"}
