from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from tests.fakes import InMemoryObservationRepository


class BrokerMustNotBeCalled:
    name = "must-not-be-called"

    def fetch_accounts(self) -> None:
        raise AssertionError("health endpoint called broker provider")

    def fetch_positions(self) -> None:
        raise AssertionError("health endpoint called broker provider")


def test_railway_backend_runtime_contract() -> None:
    backend_root = Path(__file__).parents[1]
    config = json.loads((backend_root / "railway.json").read_text())

    assert config["deploy"]["preDeployCommand"] == "python -m alembic upgrade head"
    assert config["deploy"]["startCommand"] == "python -m asa"
    assert config["deploy"]["healthcheckPath"] == "/api/v1/health"


def test_railpack_python_installation_markers() -> None:
    backend_root = Path(__file__).parents[1]

    assert (backend_root / ".python-version").read_text() == "3.12.13\n"
    assert (backend_root / "requirements.txt").read_text() == ".\n"


def test_backend_entrypoint_uses_configured_port() -> None:
    backend_root = Path(__file__).parents[1]
    entrypoint = (backend_root / "src" / "asa" / "__main__.py").read_text()

    assert "port=settings.port" in entrypoint


def test_health_and_readiness_never_authenticate_or_start_portfolio_run() -> None:
    client = TestClient(
        build_application(
            Settings(_env_file=None),
            DependencyOverrides(
                repository=InMemoryObservationRepository(healthy=True),
                broker_provider=BrokerMustNotBeCalled(),
            ),
        )
    )

    assert client.get("/api/v1/health").json() == {"status": "ok"}
    assert client.get("/api/v1/readiness").json() == {"status": "ready"}
