"""API-003: GET /api/v1/capabilities, GET /api/v1/screening[/{signal}[/{symbol}]]."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from pydantic import SecretStr

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from screening.state import ScreeningStateRecord
from tests.asa.fakes import InMemoryScreeningStateRepository

NOW = datetime(2026, 7, 23, 16, 0, tzinfo=UTC)


def _record(signal_id: str, symbol: str, outcome: str = "pass") -> ScreeningStateRecord:
    return ScreeningStateRecord(
        signal_id=signal_id,
        signal_version="1.0.0",
        symbol=symbol,
        outcome=outcome,
        explanation="PASS",
        metrics={"strategy_native_score": "75"},
        updated_at=NOW,
        dependency_timestamps={"as_of": NOW},
    )


def _client(
    repository: InMemoryScreeningStateRepository | None = None,
    token: str | None = "correct-token",
) -> TestClient:
    return TestClient(
        build_application(
            Settings(agent_api_token=SecretStr(token) if token else None, _env_file=None),
            DependencyOverrides(
                screening_state_repository=repository or InMemoryScreeningStateRepository()
            ),
        )
    )


def _auth(token: str = "correct-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestAuthentication:
    def test_capabilities_without_authorization_header_is_404(self) -> None:
        response = _client().get("/api/v1/capabilities")
        assert response.status_code == 404

    def test_screening_list_without_authorization_header_is_404(self) -> None:
        response = _client().get("/api/v1/screening")
        assert response.status_code == 404

    def test_screening_by_signal_without_authorization_header_is_404(self) -> None:
        response = _client().get("/api/v1/screening/forward_factor")
        assert response.status_code == 404

    def test_screening_result_without_authorization_header_is_404(self) -> None:
        response = _client().get("/api/v1/screening/forward_factor/AAPL")
        assert response.status_code == 404

    def test_wrong_token_is_404_not_401(self) -> None:
        response = _client().get("/api/v1/capabilities", headers=_auth("wrong-token"))
        assert response.status_code == 404

    def test_correct_token_is_accepted(self) -> None:
        response = _client().get("/api/v1/capabilities", headers=_auth())
        assert response.status_code == 200


class TestCapabilities:
    def test_lists_every_registered_signal(self) -> None:
        response = _client().get("/api/v1/capabilities", headers=_auth())
        assert response.status_code == 200
        signal_ids = {item["signal_id"] for item in response.json()["signals"]}
        assert signal_ids == {"earnings_calendar", "forward_factor", "skew_momentum"}

    def test_each_signal_declares_required_capabilities(self) -> None:
        response = _client().get("/api/v1/capabilities", headers=_auth())
        for item in response.json()["signals"]:
            assert item["required_capabilities"]


class TestListScreening:
    def test_empty_repository_returns_empty_envelope(self) -> None:
        response = _client().get("/api/v1/screening", headers=_auth())
        assert response.status_code == 200
        body = response.json()
        assert body == {"results": [], "total": 0, "limit": 100, "offset": 0}

    def test_returns_every_result_deterministically_ordered(self) -> None:
        repository = InMemoryScreeningStateRepository()
        repository.upsert(_record("skew_momentum", "MSFT"))
        repository.upsert(_record("forward_factor", "AAPL"))
        response = _client(repository).get("/api/v1/screening", headers=_auth())
        body = response.json()
        assert [(item["signal_id"], item["symbol"]) for item in body["results"]] == [
            ("forward_factor", "AAPL"),
            ("skew_momentum", "MSFT"),
        ]
        assert body["total"] == 2

    def test_every_result_exposes_updated_at_and_age_seconds(self) -> None:
        repository = InMemoryScreeningStateRepository()
        repository.upsert(_record("forward_factor", "AAPL"))
        response = _client(repository).get("/api/v1/screening", headers=_auth())
        (result,) = response.json()["results"]
        assert result["updated_at"] is not None
        assert result["age_seconds"] >= 0

    def test_pagination_limit_and_offset(self) -> None:
        repository = InMemoryScreeningStateRepository()
        for symbol in ["AAPL", "MSFT", "NVDA"]:
            repository.upsert(_record("forward_factor", symbol))
        response = _client(repository).get(
            "/api/v1/screening", headers=_auth(), params={"limit": 1, "offset": 1}
        )
        body = response.json()
        assert body["total"] == 3
        assert body["limit"] == 1
        assert body["offset"] == 1
        assert [item["symbol"] for item in body["results"]] == ["MSFT"]

    def test_limit_above_maximum_is_rejected(self) -> None:
        response = _client().get(
            "/api/v1/screening", headers=_auth(), params={"limit": 501}
        )
        assert response.status_code == 422


class TestListScreeningForSignal:
    def test_filters_to_the_requested_signal_only(self) -> None:
        repository = InMemoryScreeningStateRepository()
        repository.upsert(_record("forward_factor", "AAPL"))
        repository.upsert(_record("skew_momentum", "AAPL"))
        response = _client(repository).get("/api/v1/screening/forward_factor", headers=_auth())
        body = response.json()
        assert [item["signal_id"] for item in body["results"]] == ["forward_factor"]

    def test_unknown_signal_is_404_with_deterministic_error_shape(self) -> None:
        response = _client().get("/api/v1/screening/not_a_real_signal", headers=_auth())
        assert response.status_code == 404
        assert response.json()["detail"]["error_code"] == "UNKNOWN_SIGNAL"

    def test_known_signal_with_no_results_yet_returns_empty_envelope_not_404(self) -> None:
        response = _client().get("/api/v1/screening/forward_factor", headers=_auth())
        assert response.status_code == 200
        assert response.json()["results"] == []


class TestGetScreeningResult:
    def test_returns_the_single_result(self) -> None:
        repository = InMemoryScreeningStateRepository()
        repository.upsert(_record("forward_factor", "AAPL"))
        response = _client(repository).get(
            "/api/v1/screening/forward_factor/AAPL", headers=_auth()
        )
        assert response.status_code == 200
        body = response.json()
        assert body["signal_id"] == "forward_factor"
        assert body["symbol"] == "AAPL"
        assert body["updated_at"] is not None
        assert body["age_seconds"] >= 0

    def test_unknown_signal_is_404_with_deterministic_error_shape(self) -> None:
        response = _client().get("/api/v1/screening/not_a_real_signal/AAPL", headers=_auth())
        assert response.status_code == 404
        assert response.json()["detail"]["error_code"] == "UNKNOWN_SIGNAL"

    def test_known_signal_with_no_result_for_symbol_is_404(self) -> None:
        response = _client().get("/api/v1/screening/forward_factor/AAPL", headers=_auth())
        assert response.status_code == 404
        assert response.json()["detail"]["error_code"] == "NO_SCREENING_RESULT"


class _RepositoryThatFailsOnUpsert(InMemoryScreeningStateRepository):
    """Reads must never write -- any call to upsert() means a read endpoint
    tried to trigger computation instead of only reading persisted state."""

    def upsert(self, record: ScreeningStateRecord) -> None:
        raise AssertionError("read endpoint attempted to persist a new result")


class TestReadsNeverComputeOrPersist:
    def test_list_screening_never_calls_upsert(self) -> None:
        response = _client(_RepositoryThatFailsOnUpsert()).get("/api/v1/screening", headers=_auth())
        assert response.status_code == 200

    def test_capabilities_never_calls_upsert(self) -> None:
        response = _client(_RepositoryThatFailsOnUpsert()).get(
            "/api/v1/capabilities", headers=_auth()
        )
        assert response.status_code == 200
