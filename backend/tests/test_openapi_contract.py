import json
from pathlib import Path

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from tests.fakes import InMemoryObservationRepository


def test_frontend_openapi_contract_matches_backend_quote_shape() -> None:
    app = build_application(
        Settings(),
        DependencyOverrides(repository=InMemoryObservationRepository()),
    )
    backend_schema = app.openapi()
    contract_path = Path(__file__).parents[2] / "frontend" / "src" / "api" / "openapi.json"
    frontend_schema = json.loads(contract_path.read_text())

    operation = backend_schema["paths"]["/api/v1/market/quotes/{symbol}"]["get"]
    assert operation["operationId"] == "getLatestQuote"
    assert (
        frontend_schema["paths"]["/api/v1/market/quotes/{symbol}"]["get"]["operationId"]
        == "getLatestQuote"
    )
    for model in ("QuoteResponse", "ProvenanceResponse"):
        backend_required = set(backend_schema["components"]["schemas"][model]["required"])
        frontend_required = set(frontend_schema["components"]["schemas"][model]["required"])
        assert backend_required == frontend_required
