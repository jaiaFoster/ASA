from __future__ import annotations

from fastapi.testclient import TestClient

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from tests.asa.fakes import InMemoryLatestResultRepository, InMemoryObservationRepository
from tests.asa.test_screening_routes import _record

HEADERS = {"Authorization": "Bearer test-token"}


def _client() -> TestClient:
    results = InMemoryLatestResultRepository()
    for row in (
        _record("B001", "SPY", blockers=()),
        _record("B002", "SPY", "missing_data", verdict=None),
        _record("forward_factor", "AAPL"),
        _record("B001", "QQQ", blockers=()),
    ):
        results.upsert(row)
    return TestClient(
        build_application(
            Settings(agent_api_token="test-token", _env_file=None),
            DependencyOverrides(
                repository=InMemoryObservationRepository(), latest_result_repository=results
            ),
        )
    )


def test_stock_proposal_endpoint_projects_benchmark_result() -> None:
    response = _client().get("/api/v1/screening/B001/SPY/stock-proposal", headers=HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["instrument"] == "SPY"
    assert body["strategy_id"] == "B001"
    assert body["signal_verdict"] == "PASS"
    assert body["allocation"] is None
    assert body["allocation_reason"] == "not_defined_by_strategy"
    assert body["freshness"] in {"fresh", "stale"}
    assert body["strategy_description"].startswith("SPY buy-and-hold")


def test_stock_proposal_keeps_missing_data_typed_unknown() -> None:
    response = _client().get("/api/v1/screening/B002/SPY/stock-proposal", headers=HEADERS)

    assert response.status_code == 200
    assert response.json()["status"] == "unknown"
    assert response.json()["unknown_reasons"] == ["capital unavailable"]


def test_option_structured_signal_has_no_stock_proposal() -> None:
    response = _client().get(
        "/api/v1/screening/forward_factor/AAPL/stock-proposal", headers=HEADERS
    )

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "NO_STOCK_PROPOSAL"


def test_active_scope_includes_scheduler_declared_benchmark_pairs_only() -> None:
    response = _client().get("/api/v1/screening?active_only=true&limit=50", headers=HEADERS)

    pairs = {(item["signal_id"], item["symbol"]) for item in response.json()["results"]}
    assert ("B001", "SPY") in pairs
    assert ("B002", "SPY") in pairs
    assert ("forward_factor", "AAPL") in pairs
    # QQQ is neither an S&P member nor a scheduled benchmark pair.
    assert ("B001", "QQQ") not in pairs
    assert response.json()["retained_nonactive_total"] == 1


def test_capabilities_expose_declared_structure_and_category() -> None:
    response = _client().get("/api/v1/capabilities", headers=HEADERS)

    by_id = {item["signal_id"]: item for item in response.json()["signals"]}
    assert by_id["B001"]["structure"] == "none"
    assert by_id["B001"]["category"] == "stock_benchmark"
    assert by_id["forward_factor"]["structure"] == "calendar"
