from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from tools.deployment_observer import collect as collect_entrypoint
from tools.deployment_observer.observer import (
    MAX_SUMMARY_LINES,
    collect,
    first_error_cluster,
    parse_json_records,
    redact,
    redact_text,
    resolve_deployment,
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
        ["logs", "dep-latest", "--build", "--lines", "5000", "--json"],
        ["logs", "dep-latest", "--deployment", "--lines", "5000", "--json"],
    ]


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
    assert [path.name for path in output.iterdir()] == ["summary.md"]
    assert "logs were uploaded" in (output / "summary.md").read_text()


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
    }
    validate_manifest(valid)
    for field in ("railway_token", "environment_variables", "database_url", "credentials"):
        with pytest.raises(ValueError):
            validate_manifest({**valid, field: "forbidden"})


def test_summary_remains_bounded() -> None:
    logs = [{"message": f"error {index}"} for index in range(200)]
    cluster, _, _ = first_error_cluster(logs, [])
    assert len(cluster) == MAX_SUMMARY_LINES


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
