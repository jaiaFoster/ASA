from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient
from pydantic import SecretStr

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from tests.asa.fakes import InMemoryLatestResultRepository, InMemoryObservationRepository
from tools.screening_smoke import run_smoke


def test_cors_preflight_allows_authorization_for_screening_routes() -> None:
    app = build_application(
        Settings(
            agent_api_token=SecretStr("correct-token"),
            cors_origins="https://agent.example",
            _env_file=None,
        ),
        DependencyOverrides(
            repository=InMemoryObservationRepository(),
            latest_result_repository=InMemoryLatestResultRepository(),
        ),
    )
    response = TestClient(app).options(
        "/api/v1/screening",
        headers={
            "Origin": "https://agent.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert response.status_code == 200
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


@dataclass(frozen=True)
class _Response:
    status: int = 200


def test_smoke_harness_covers_required_paths_without_printing_token(capsys) -> None:  # noqa: ANN001
    requests = []

    def opener(request, *, timeout):  # noqa: ANN001
        requests.append((request, timeout))
        return _Response()

    token = "never-print-this-token"
    assert run_smoke("https://asa.example", token, "skew_momentum", "AAPL", opener=opener) == 0
    output = capsys.readouterr()
    assert token not in output.out + output.err
    assert [request.full_url for request, _ in requests] == [
        "https://asa.example/api/v1/health",
        "https://asa.example/api/v1/readiness",
        "https://asa.example/api/v1/capabilities",
        "https://asa.example/api/v1/screening",
        "https://asa.example/api/v1/screening/skew_momentum/AAPL/refresh",
        "https://asa.example/api/v1/screening/skew_momentum/AAPL",
    ]
    assert "Authorization" not in output.out


def test_smoke_harness_fails_closed_without_exposing_response_body(capsys) -> None:  # noqa: ANN001
    class Failure:
        status = 503

    assert (
        run_smoke(
            "https://asa.example",
            "secret",
            "skew_momentum",
            "AAPL",
            opener=lambda request, timeout: Failure(),  # noqa: ARG005
        )
        == 1
    )
    output = capsys.readouterr()
    assert "secret" not in output.out + output.err
    assert "status=503" in output.out
