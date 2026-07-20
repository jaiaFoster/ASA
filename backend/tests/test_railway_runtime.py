from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from asa.asgi import create_application
from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from tests.fakes import InMemoryObservationRepository


class BrokerMustNotBeCalled:
    name = "must-not-be-called"

    def fetch_accounts(self) -> None:
        raise AssertionError("health endpoint called broker provider")

    def fetch_positions(self) -> None:
        raise AssertionError("health endpoint called broker provider")


EXPECTED_START_COMMAND = (
    "export PYTHONPATH=src && python -m alembic upgrade head && "
    "exec python -m uvicorn asa.asgi:create_application --factory "
    '--host 0.0.0.0 --port "${PORT}"'
)


def test_railway_backend_runtime_contract() -> None:
    backend_root = Path(__file__).parents[1]
    config = json.loads((backend_root / "railway.json").read_text())

    assert config["deploy"]["preDeployCommand"] == "python -m alembic upgrade head"
    assert config["deploy"]["startCommand"] == EXPECTED_START_COMMAND
    assert config["deploy"]["healthcheckPath"] == "/api/v1/health"


def test_railpack_python_installation_markers() -> None:
    backend_root = Path(__file__).parents[1]

    assert (backend_root / ".python-version").read_text() == "3.12.13\n"
    assert (backend_root / "requirements.txt").read_text() == ".\n"


def test_backend_entrypoint_uses_configured_port() -> None:
    backend_root = Path(__file__).parents[1]
    entrypoint = (backend_root / "src" / "asa" / "__main__.py").read_text()

    assert "port=settings.port" in entrypoint


def test_asgi_factory_imports_and_builds_fastapi_application() -> None:
    assert isinstance(create_application(), FastAPI)


def _production_environment(tmp_path: Path, migration_exit_code: int) -> tuple[dict[str, str], int]:
    with socket.socket() as reserved_port:
        reserved_port.bind(("127.0.0.1", 0))
        port = reserved_port.getsockname()[1]
    python_wrapper = tmp_path / "python"
    python_wrapper.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "-m" ] && [ "$2" = "alembic" ]; then\n'
        '  exit "$MIGRATION_EXIT_CODE"\n'
        "fi\n"
        'exec "$REAL_PYTHON" "$@"\n'
    )
    python_wrapper.chmod(0o755)
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{tmp_path}:{environment['PATH']}",
            "PORT": str(port),
            "REAL_PYTHON": sys.executable,
            "MIGRATION_EXIT_CODE": str(migration_exit_code),
            "ASA_BROKER_PORTFOLIO_PROVIDER": "deterministic_fake_broker",
            "DATABASE_URL": "postgresql+psycopg://asa:asa@localhost:5432/asa",
        }
    )
    return environment, port


def test_exact_production_command_runs_migration_then_serves_health(tmp_path: Path) -> None:
    backend_root = Path(__file__).parents[1]
    environment, port = _production_environment(tmp_path, migration_exit_code=0)
    started_at = time.monotonic()
    process = subprocess.Popen(
        EXPECTED_START_COMMAND,
        cwd=backend_root,
        env=environment,
        executable="/bin/sh",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    response_body = None
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = "" if process.stdout is None else process.stdout.read()
                raise AssertionError(f"production server exited before healthcheck: {output}")
            try:
                with urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=1) as response:
                    assert response.status == 200
                    response_body = json.loads(response.read())
                    break
            except URLError:
                time.sleep(0.05)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    assert response_body == {"status": "ok"}
    assert time.monotonic() - started_at < 5


def test_production_command_exits_when_migration_fails(tmp_path: Path) -> None:
    backend_root = Path(__file__).parents[1]
    environment, port = _production_environment(tmp_path, migration_exit_code=37)

    completed = subprocess.run(
        EXPECTED_START_COMMAND,
        cwd=backend_root,
        env=environment,
        executable="/bin/sh",
        shell=True,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    assert completed.returncode == 37
    with pytest.raises(URLError):
        urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=0.1)


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
