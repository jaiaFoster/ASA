from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from tools.deployment_observer import collect as collect_entrypoint
from tools.deployment_observer.observer import (
    CommandFailure,
    MAX_SUMMARY_LINES,
    collect,
    first_error_cluster,
    parse_json_records,
    redact,
    redact_text,
    railway_command,
    resolve_deployment,
    resolve_known_deployment_id,
    validate_manifest,
)


def deployment(deployment_id: str = "dep-latest") -> dict[str, Any]:
    return {
        "id": deployment_id,
        "status": "FAILED",
        "createdAt": "2026-07-19T01:00:00Z",
        "serviceName": "ASA",
        "environmentName": "production",
        "commitHash": "abc123",
    }


def test_resolves_explicit_deployment_id_before_latest() -> None:
    records = [deployment("latest"), deployment("explicit")]
    records[0]["createdAt"] = "2026-07-20T00:00:00Z"
    result = resolve_deployment("explicit", {}, records, "ASA", "production")
    assert result.deployment_id == "explicit"


def test_resolves_payload_id_before_latest() -> None:
    event = {"deployment": {"payload": {"railway_deployment_id": "payload-id"}}}
    result = resolve_deployment(None, event, [deployment("latest")], "ASA", "production")
    assert result.deployment_id == "payload-id"


def test_target_url_extracts_railway_deployment_id() -> None:
    event = {
        "deployment_status": {
            "target_url": (
                "https://railway.app/project/example/service/example?"
                "id=e9030deb-31ac-4f13-83e3-a236989afb65"
            )
        }
    }
    assert resolve_known_deployment_id(None, event) == "e9030deb-31ac-4f13-83e3-a236989afb65"


def test_payload_id_takes_precedence_over_target_url() -> None:
    event = {
        "deployment": {"payload": {"railway_deployment_id": "payload-id"}},
        "deployment_status": {
            "target_url": "https://railway.app/?id=e9030deb-31ac-4f13-83e3-a236989afb65"
        },
    }
    assert resolve_known_deployment_id(None, event) == "payload-id"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('[{"id":"one"}]', [{"id": "one"}]),
        ('{"deployments":[{"id":"two"}]}', [{"id": "two"}]),
        ('{"message":"a"}\n{"message":"b"}\n', [{"message": "a"}, {"message": "b"}]),
    ],
)
def test_parses_railway_cli_json(raw: str, expected: list[dict[str, Any]]) -> None:
    assert parse_json_records(raw) == expected


def test_redacts_url_userinfo() -> None:
    value, count = redact_text("postgresql://alice:secret@db.example/asa")
    assert value == "postgresql://[REDACTED]@db.example/asa"
    assert count == 1


def test_redacts_bearer_tokens() -> None:
    value, _ = redact_text("Authorization: Bearer abc.def.ghi")
    assert value == "Authorization: Bearer [REDACTED]"


@pytest.mark.parametrize(
    "value",
    [
        "password=hunter2",
        "PGPASSWORD: postgres-secret",
        "DATABASE_URL=postgresql://user:password@host/database",
        "robinhood_totp=123456",
        "refresh_token: refresh-secret",
        "Set-Cookie: session=secret; HttpOnly",
    ],
)
def test_redacts_sensitive_assignments(value: str) -> None:
    result, count = redact_text(value)
    assert "secret" not in result
    assert "hunter2" not in result
    assert "123456" not in result
    assert count >= 1


def test_redaction_is_idempotent() -> None:
    first = redact({"message": "password=secret Authorization: Bearer token"})
    second = redact(first.value)
    assert second.value == first.value
    assert second.count == 0


def test_normal_stack_traces_remain_readable() -> None:
    trace = 'Traceback (most recent call last):\n  File "app.py", line 42\nValueError: boom'
    result, count = redact_text(trace)
    assert result == trace
    assert count == 0


def fake_runner(empty_build: bool = False, absent_runtime: bool = False):  # type: ignore[no-untyped-def]
    def run(args: list[str]) -> str:
        if args[:2] == ["deployment", "list"]:
            return json.dumps([deployment()])
        if "--build" in args:
            return "" if empty_build else '{"timestamp":"t","level":"error","message":"failed to build password=secret"}\n'
        if absent_runtime:
            return ""
        return '{"timestamp":"t","level":"info","message":"healthcheck failed"}\n'

    return run


@pytest.mark.parametrize(
    ("empty_build", "absent_runtime", "expected_build", "expected_runtime"),
    [(True, False, 0, 1), (False, True, 1, 0)],
)
def test_handles_empty_or_absent_logs(
    tmp_path: Path,
    empty_build: bool,
    absent_runtime: bool,
    expected_build: int,
    expected_runtime: int,
) -> None:
    _, manifest, _ = collect(
        output_dir=tmp_path / "artifacts",
        service="ASA",
        environment="production",
        explicit_id=None,
        event={},
        include_runtime_logs=True,
        runner=fake_runner(empty_build, absent_runtime),
        now=lambda: datetime(2026, 7, 19, tzinfo=UTC),
    )
    assert manifest["build_log_line_count"] == expected_build
    assert manifest["runtime_log_line_count"] == expected_runtime


def test_uses_only_required_read_only_railway_commands(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(args: list[str]) -> str:
        calls.append(args)
        return json.dumps([deployment()]) if args[:2] == ["deployment", "list"] else ""

    collect(
        output_dir=tmp_path / "artifacts",
        service="ASA",
        environment="production",
        explicit_id=None,
        event={},
        include_runtime_logs=True,
        runner=runner,
    )
    assert calls == [
        ["deployment", "list", "--service", "ASA", "--environment", "production", "--json"],
        [
            "logs",
            "dep-latest",
            "--service",
            "ASA",
            "--environment",
            "production",
            "--build",
            "--lines",
            "5000",
            "--json",
        ],
        [
            "logs",
            "dep-latest",
            "--service",
            "ASA",
            "--environment",
            "production",
            "--deployment",
            "--lines",
            "5000",
            "--json",
        ],
    ]


def test_explicit_id_is_refreshed_before_log_collection(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(args: list[str]) -> str:
        calls.append(args)
        return json.dumps([deployment("e9030deb-31ac-4f13-83e3-a236989afb65")]) if args[:2] == ["deployment", "list"] else ""

    collect(
        output_dir=tmp_path / "artifacts",
        service="ASA",
        environment="production",
        explicit_id="e9030deb-31ac-4f13-83e3-a236989afb65",
        event={},
        include_runtime_logs=True,
        runner=runner,
    )
    assert calls == [
        ["deployment", "list", "--service", "ASA", "--environment", "production", "--json"],
        [
            "logs",
            "e9030deb-31ac-4f13-83e3-a236989afb65",
            "--service",
            "ASA",
            "--environment",
            "production",
            "--build",
            "--lines",
            "5000",
            "--json",
        ],
        [
            "logs",
            "e9030deb-31ac-4f13-83e3-a236989afb65",
            "--service",
            "ASA",
            "--environment",
            "production",
            "--deployment",
            "--lines",
            "5000",
            "--json",
        ],
    ]


def test_deployment_list_resolves_fallback_and_refreshes_known_status(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(args: list[str]) -> str:
        calls.append(args)
        return (
            json.dumps([deployment(), deployment("known-id")])
            if args[:2] == ["deployment", "list"]
            else ""
        )

    collect(
        output_dir=tmp_path / "fallback",
        service="ASA",
        environment="production",
        explicit_id=None,
        event={},
        include_runtime_logs=False,
        runner=runner,
    )
    assert calls[0][:2] == ["deployment", "list"]

    calls.clear()
    collect(
        output_dir=tmp_path / "known",
        service="ASA",
        environment="production",
        explicit_id="known-id",
        event={},
        include_runtime_logs=False,
        runner=runner,
    )
    assert calls[0][:2] == ["deployment", "list"]


def test_log_commands_use_explicit_noninteractive_read_only_context(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(args: list[str]) -> str:
        calls.append(args)
        return json.dumps([deployment("deployment-id")]) if args[:2] == ["deployment", "list"] else ""

    collect(
        output_dir=tmp_path / "artifacts",
        service="ASA",
        environment="production",
        explicit_id="deployment-id",
        event={},
        include_runtime_logs=True,
        runner=runner,
    )
    log_calls = [command for command in calls if command[0] == "logs"]
    assert len(log_calls) == 2
    for command in log_calls:
        assert command[0] == "logs"
        assert command[command.index("--service") + 1] == "ASA"
        assert command[command.index("--environment") + 1] == "production"
        assert not {"link", "service", "environment", "up", "redeploy", "restart", "rollback"}.intersection(
            command
        )


def test_collection_writes_only_redacted_logs_and_schema(tmp_path: Path) -> None:
    output = tmp_path / "artifacts"
    _, manifest, summary = collect(
        output_dir=output,
        service="ASA",
        environment="production",
        explicit_id=None,
        event={},
        include_runtime_logs=True,
        runner=fake_runner(),
    )
    assert {path.name for path in output.iterdir()} == {
        "manifest.json",
        "build-log.jsonl",
        "runtime-log.jsonl",
        "summary.md",
    }
    combined = "".join(path.read_text() for path in output.iterdir())
    assert "password=secret" not in combined
    assert "[REDACTED]" in combined
    assert manifest["redaction_count"] == 1
    assert "Likely failing phase: `build`" in summary


def test_redaction_failure_prevents_raw_artifact_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "artifacts"
    event_path = tmp_path / "event.json"
    event_path.write_text("{}")
    monkeypatch.setenv("OBSERVER_OUTPUT_DIR", str(output))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setattr(collect_entrypoint, "collect", lambda **_: (_ for _ in ()).throw(ValueError()))
    assert collect_entrypoint.main() == 1
    assert {path.name for path in output.iterdir()} == {"failure.json", "summary.md"}
    assert "logs were uploaded" in (output / "summary.md").read_text()


def test_called_process_error_output_is_redacted_and_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = "seeded-railway-token-value"
    monkeypatch.setenv("RAILWAY_TOKEN", token)
    stdout = "\n".join(
        [f"line-{index} {token} {'x' * 1_000}" for index in range(200)]
    )
    stderr = "Authorization: Bearer hidden\n" + "\n".join(
        [f"stderr-{index} {'y' * 1_000}" for index in range(200)]
    )

    def fail(*_: Any, **__: Any) -> None:
        raise subprocess.CalledProcessError(
            17,
            ["railway", "logs"],
            output=stdout,
            stderr=stderr,
        )

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(CommandFailure) as raised:
        railway_command(["logs", "deployment-id", "--build", "--lines", "5000", "--json"])
    failure = raised.value
    assert failure.command == [
        "railway",
        "logs",
        "deployment-id",
        "--build",
        "--lines",
        "5000",
        "--json",
    ]
    assert failure.exit_code == 17
    assert token not in failure.stdout + failure.stderr
    assert "Authorization" not in failure.stderr
    assert len(failure.stdout.encode()) <= 16 * 1024
    assert len(failure.stderr.encode()) <= 16 * 1024
    assert len(failure.stdout.splitlines()) <= 100
    assert len(failure.stderr.splitlines()) <= 100


def test_command_and_bearer_values_are_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "command-secret-token"
    monkeypatch.setenv("RAILWAY_TOKEN", token)

    def fail(*_: Any, **__: Any) -> None:
        raise subprocess.CalledProcessError(
            1,
            ["railway", "logs"],
            output="Bearer other-secret",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(CommandFailure) as raised:
        railway_command(["logs", "deployment-id", "--filter", f"token={token}"])
    serialized = json.dumps(raised.value.command) + raised.value.stdout
    assert token not in serialized
    assert "other-secret" not in serialized
    assert "[REDACTED]" in serialized


def test_safe_failure_artifacts_include_category_and_exit_code_without_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "artifacts"
    event_path = tmp_path / "event.json"
    event_path.write_text("{}")
    token = "never-serialize-this-token"
    monkeypatch.setenv("RAILWAY_TOKEN", token)
    monkeypatch.setenv("OBSERVER_OUTPUT_DIR", str(output))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    command = ["railway", "logs", "deployment-id", "--deployment", "--json"]
    failure = CommandFailure(command, 23, "token=[REDACTED]", "password=[REDACTED]")
    monkeypatch.setattr(
        collect_entrypoint, "collect", lambda **_: (_ for _ in ()).throw(failure)
    )
    assert collect_entrypoint.main() == 1
    assert {path.name for path in output.iterdir()} == {"failure.json", "summary.md"}
    combined = "".join(path.read_text() for path in output.iterdir())
    data = json.loads((output / "failure.json").read_text())
    assert data["command"] == command
    assert data["exit_code"] == 23
    assert data["stdout"] == "token=[REDACTED]"
    assert data["stderr"] == "password=[REDACTED]"
    assert token not in combined
    summary = (output / "summary.md").read_text()
    assert "Failed command" in summary
    assert "failure.json" in summary


def test_called_process_error_produces_failure_json_and_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "artifacts"
    token = "integration-railway-token"
    monkeypatch.setenv("RAILWAY_TOKEN", token)
    monkeypatch.setenv("OBSERVER_OUTPUT_DIR", str(output))
    monkeypatch.setenv("INPUT_DEPLOYMENT_ID", "e9030deb-31ac-4f13-83e3-a236989afb65")

    def fail(*_: Any, **__: Any) -> None:
        raise subprocess.CalledProcessError(
            9,
            ["railway", "logs"],
            output=f"password=stdout-secret {token}",
            stderr=f"Authorization: Bearer {token}",
        )

    monkeypatch.setattr(subprocess, "run", fail)
    assert collect_entrypoint.main() == 1
    data = json.loads((output / "failure.json").read_text())
    assert data == {
        "command": [
            "railway",
            "deployment",
            "list",
            "--service",
            "ASA",
            "--environment",
            "production",
            "--json",
        ],
        "exit_code": 9,
        "stdout": "password=[REDACTED] [REDACTED]",
        "stderr": "[REDACTED]",
    }
    combined = (output / "failure.json").read_text() + (output / "summary.md").read_text()
    assert token not in combined
    assert "Authorization" not in combined
    assert not (output / "build-log.jsonl").exists()
    assert not (output / "runtime-log.jsonl").exists()


def test_manifest_never_contains_prohibited_fields() -> None:
    valid = {
        "version": 1,
        "collected_at": "now",
        "deployment_id": "id",
        "service": "ASA",
        "environment": "production",
        "deployment_status": "FAILED",
        "collection_status": "complete",
        "source_commit_sha": "sha",
        "build_log_line_count": 0,
        "runtime_log_line_count": 0,
        "redaction_count": 0,
        "pull_request_resolution_status": "not_found",
        "pull_request_number": None,
        "pull_request_url": None,
        "pull_request_comment_status": "skipped",
        "pull_request_comment_url": None,
    }
    validate_manifest(valid)
    for field in ("railway_token", "environment_variables", "database_url", "credentials"):
        with pytest.raises(ValueError):
            validate_manifest({**valid, field: "forbidden"})


def test_summary_remains_bounded() -> None:
    logs = [{"message": f"error {index}"} for index in range(200)]
    cluster, _, _ = first_error_cluster(logs, [])
    assert len(cluster) == MAX_SUMMARY_LINES


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


def status_runner(
    statuses: list[str], calls: list[list[str]]
) -> Callable[[list[str]], str]:
    remaining = iter(statuses)

    def run(args: list[str]) -> str:
        calls.append(args)
        if args[:2] == ["deployment", "list"]:
            item = deployment("polled-id")
            item["status"] = next(remaining)
            return json.dumps([item])
        if "--build" in args:
            return '{"level":"info","message":"build complete"}\n'
        return '{"level":"info","message":"server healthy"}\n'

    return run


@pytest.mark.parametrize("terminal_status", ["SUCCESS", "FAILED"])
def test_non_terminal_deployment_is_polled_before_final_collection(
    tmp_path: Path,
    terminal_status: str,
) -> None:
    calls: list[list[str]] = []
    clock = FakeClock()

    _, manifest, _ = collect(
        output_dir=tmp_path / terminal_status.lower(),
        service="ASA",
        environment="production",
        explicit_id="polled-id",
        event={},
        include_runtime_logs=True,
        runner=status_runner(["BUILDING", terminal_status], calls),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    assert manifest["deployment_status"] == terminal_status
    assert manifest["collection_status"] == "complete"
    assert [call[0] for call in calls] == ["deployment", "deployment", "logs", "logs"]


@pytest.mark.parametrize("observed_status", ["BUILDING", "UNRECOGNIZED"])
def test_non_terminal_or_unknown_status_times_out_with_bounded_artifacts(
    tmp_path: Path,
    observed_status: str,
) -> None:
    output = tmp_path / observed_status.lower()
    calls: list[list[str]] = []
    clock = FakeClock()

    _, manifest, summary = collect(
        output_dir=output,
        service="ASA",
        environment="production",
        explicit_id="polled-id",
        event={},
        include_runtime_logs=True,
        runner=status_runner([observed_status] * 3, calls),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
        poll_interval_seconds=10,
        maximum_wait_seconds=20,
    )

    assert manifest["collection_status"] == "incomplete"
    assert manifest["deployment_status"] == observed_status
    assert manifest["classification"] == "observer-timeout"
    assert {path.name for path in output.iterdir()} == {"manifest.json", "summary.md", "failure.json"}
    failure = json.loads((output / "failure.json").read_text())
    assert failure == {
        "deployment_id": "polled-id",
        "last_observed_status": observed_status,
        "elapsed_seconds": 20.0,
        "polling_attempt_count": 2,
    }
    assert "observer-timeout" in summary
    assert all(call[:2] == ["deployment", "list"] for call in calls)


def test_alembic_info_on_error_stream_is_not_a_migration_failure() -> None:
    logs = [
        {
            "level": "error",
            "message": "INFO [alembic.runtime.migration] Context impl PostgresqlImpl.",
        },
        {
            "level": "error",
            "message": "INFO [alembic.runtime.migration] Will assume transactional DDL.",
        },
    ]

    assert first_error_cluster([], logs) == ([], "unknown", "unknown")


def test_alembic_info_before_healthcheck_failure_does_not_mask_classification() -> None:
    logs = [
        {
            "level": "error",
            "message": "INFO [alembic.runtime.migration] Context impl PostgresqlImpl.",
        },
        {"level": "error", "message": "Healthcheck failed"},
    ]

    _, classification, phase = first_error_cluster([], logs)
    assert (classification, phase) == ("healthcheck", "healthcheck")


def test_real_alembic_exception_is_classified_as_migration_failure() -> None:
    logs = [
        {
            "level": "error",
            "message": "Traceback: Alembic upgrade failed with RuntimeError",
        }
    ]

    _, classification, phase = first_error_cluster([], logs)
    assert (classification, phase) == ("migration", "pre-deploy")


@pytest.mark.parametrize(
    ("message", "classification", "phase"),
    [
        ("No module named foo", "startup_or_packaging", "startup"),
        ("ValidationError", "configuration", "pre-deploy"),
        ("Could not parse SQLAlchemy URL", "configuration", "pre-deploy"),
        ("connection refused", "database_connectivity", "startup"),
        ("alembic upgrade failed", "migration", "pre-deploy"),
        ("healthcheck failed", "healthcheck", "healthcheck"),
        ("failed to build wheel", "build", "build"),
        ("unrecognized failure", "unknown", "build"),
    ],
)
def test_failure_phase_classification_is_deterministic(
    message: str, classification: str, phase: str
) -> None:
    first = first_error_cluster([{"message": f"ERROR: {message}"}], [])
    second = first_error_cluster([{"message": f"ERROR: {message}"}], [])
    assert first == second
    assert first[1:] == (classification, phase)
