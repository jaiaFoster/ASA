"""Collection, redaction, and deterministic diagnosis helpers."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

REDACTED = "[REDACTED]"
MAX_LOG_LINES = 5_000
MAX_SUMMARY_LINES = 80
MAX_FAILURE_LINES = 100
MAX_FAILURE_BYTES = 16 * 1024
POLL_INTERVAL_SECONDS = 10.0
MAX_POLL_SECONDS = 600.0
TERMINAL_DEPLOYMENT_STATES = frozenset({"SUCCESS", "FAILED", "CRASHED", "REMOVED", "CANCELLED"})
PROHIBITED_MANIFEST_FIELDS = {
    "railway_token",
    "environment_variables",
    "database_url",
    "credentials",
}

_PATTERNS = (
    # Credentials embedded in URI authority sections.
    re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://)([^\s/@:]+):([^\s/@]+)@"),
    re.compile(r"(?i)(\bAuthorization\s*[:=]\s*Bearer\s+)([^\s,;]+)"),
    re.compile(
        r"(?i)(\b(?:access[_-]?token|refresh[_-]?token|session(?:[_-]?(?:cookie|token))?|"
        r"password|pgpassword|database_url|railway_token|robinhood[_-]?(?:username|password|totp|cookie|"
        r"cookies|token|access_token|refresh_token))\b\s*[:=]\s*)([^\s,;]+|\"[^\"]*\"|'[^']*')"
    ),
    re.compile(r"(?i)(\b(?:Cookie|Set-Cookie)\s*:\s*)([^\r\n]+)"),
)


@dataclass(frozen=True)
class RedactionResult:
    value: Any
    count: int


@dataclass(frozen=True)
class Deployment:
    deployment_id: str
    status: str
    created_at: str
    service: str
    environment: str
    source_commit_sha: str


@dataclass(frozen=True)
class CommandFailure(Exception):
    """A bounded, already-redacted Railway CLI failure."""

    command: list[str]
    exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class PollingResult:
    deployment: Deployment
    terminal: bool
    elapsed_seconds: float
    attempt_count: int


def redact_text(value: str) -> tuple[str, int]:
    """Return deterministically redacted text and the replacement count."""
    count = 0
    result = value
    for index, pattern in enumerate(_PATTERNS):
        if index == 0:
            result, replacements = pattern.subn(r"\1[REDACTED]@", result)
            count += replacements
        else:
            def replace(match: re.Match[str]) -> str:
                nonlocal count
                if match.group(2) == REDACTED:
                    return match.group(0)
                count += 1
                return f"{match.group(1)}{REDACTED}"

            result = pattern.sub(replace, result)
    return result, count


def redact(value: Any) -> RedactionResult:
    """Redact every string value in a JSON-compatible structure."""
    if isinstance(value, str):
        text, count = redact_text(value)
        return RedactionResult(text, count)
    if isinstance(value, list):
        output: list[Any] = []
        count = 0
        for item in value:
            redacted = redact(item)
            output.append(redacted.value)
            count += redacted.count
        return RedactionResult(output, count)
    if isinstance(value, dict):
        output_dict: dict[str, Any] = {}
        count = 0
        for key, item in value.items():
            redacted = redact(item)
            output_dict[str(key)] = redacted.value
            count += redacted.count
        return RedactionResult(output_dict, count)
    return RedactionResult(value, 0)


def parse_json_records(raw: str) -> list[dict[str, Any]]:
    """Parse Railway JSON arrays, wrapper objects, or JSONL output."""
    if not raw.strip():
        return []
    try:
        parsed: Any = json.loads(raw)
    except json.JSONDecodeError:
        records = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            records.append(item if isinstance(item, dict) else {"message": item})
        return records
    if isinstance(parsed, list):
        return [item if isinstance(item, dict) else {"message": item} for item in parsed]
    if isinstance(parsed, dict):
        for key in ("deployments", "logs", "data"):
            nested = parsed.get(key)
            if isinstance(nested, list):
                return [item if isinstance(item, dict) else {"message": item} for item in nested]
        return [parsed]
    return [{"message": parsed}]


def _first(record: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value is not None:
            return str(value)
    return ""


def _payload_deployment_id(event: Mapping[str, Any]) -> str | None:
    deployment = event.get("deployment")
    if not isinstance(deployment, Mapping):
        return None
    payload = deployment.get("payload")
    if not isinstance(payload, Mapping):
        return None
    for key in ("railway_deployment_id", "railwayDeploymentId", "deployment_id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    railway = payload.get("railway")
    if isinstance(railway, Mapping):
        value = railway.get("deployment_id") or railway.get("deploymentId")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _target_url_deployment_id(event: Mapping[str, Any]) -> str | None:
    status = event.get("deployment_status")
    if not isinstance(status, Mapping):
        return None
    target_url = status.get("target_url")
    if not isinstance(target_url, str):
        return None
    parsed = urlparse(target_url)
    hostname = (parsed.hostname or "").lower()
    if hostname not in {"railway.app", "railway.com"} and not hostname.endswith(
        (".railway.app", ".railway.com")
    ):
        return None
    candidate = parse_qs(parsed.query).get("id", [""])[0]
    if re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", candidate):
        return candidate
    return None


def resolve_known_deployment_id(
    explicit_id: str | None, event: Mapping[str, Any]
) -> str | None:
    """Resolve an ID without contacting Railway."""
    return (explicit_id or "").strip() or _payload_deployment_id(event) or _target_url_deployment_id(
        event
    )


def resolve_deployment(
    explicit_id: str | None,
    event: Mapping[str, Any],
    deployments: list[dict[str, Any]],
    service: str,
    environment: str,
) -> Deployment:
    """Resolve explicit, payload-derived, target-URL, then latest deployment."""
    wanted = resolve_known_deployment_id(explicit_id, event)
    record: dict[str, Any] | None = None
    if wanted:
        record = next(
            (item for item in deployments if _first(item, "id", "deploymentId") == wanted), None
        )
        status = event.get("deployment_status")
        status_record = status if isinstance(status, Mapping) else {}
        github_deployment = event.get("deployment")
        github_record = github_deployment if isinstance(github_deployment, Mapping) else {}
        record = record or {
            "id": wanted,
            "status": status_record.get("state", "unknown"),
            "createdAt": status_record.get("created_at", ""),
            "commitHash": github_record.get("sha", ""),
        }
    elif deployments:
        record = max(
            deployments,
            key=lambda item: _first(item, "createdAt", "created_at", "created") or "",
        )
    if record is None:
        raise RuntimeError("No Railway deployment could be resolved")
    deployment_id = _first(record, "id", "deploymentId")
    if not deployment_id:
        raise RuntimeError("Resolved Railway deployment has no ID")
    return Deployment(
        deployment_id=deployment_id,
        status=_first(record, "status", "deploymentStatus") or "unknown",
        created_at=_first(record, "createdAt", "created_at", "created"),
        service=_first(record, "serviceName", "service") or service,
        environment=_first(record, "environmentName", "environment") or environment,
        source_commit_sha=_first(record, "commitHash", "sourceCommitSha", "source_commit_sha"),
    )


CLASSIFICATION_RULES = (
    ("failed to build", "build", "build"),
    ("no module named", "startup_or_packaging", "startup"),
    ("validationerror", "configuration", "pre-deploy"),
    ("could not parse sqlalchemy url", "configuration", "pre-deploy"),
    ("connection refused", "database_connectivity", "startup"),
    ("healthcheck", "healthcheck", "healthcheck"),
)

AFFIRMATIVE_FAILURE = re.compile(
    r"(?i)traceback|exception|fatal|failed|failure|error|non[- ]?zero|exit(?:ed)?\s+(?:code|status)\s*[1-9]"
)


def classify(lines: Iterable[dict[str, Any]], source: str) -> tuple[str, str]:
    messages = [str(line.get("message", "")).lower() for line in lines]
    text = "\n".join(messages)
    if any("alembic" in message and AFFIRMATIVE_FAILURE.search(message) for message in messages):
        return "migration", "pre-deploy"
    for needle, classification, phase in CLASSIFICATION_RULES:
        if needle in text:
            return classification, phase
    if source == "build" and text:
        return "unknown", "build"
    return "unknown", "unknown"


def first_error_cluster(
    build_logs: list[dict[str, Any]], runtime_logs: list[dict[str, Any]]
) -> tuple[list[str], str, str]:
    """Return at most 80 lines around the first deterministic error marker."""
    for source, records in (("build", build_logs), ("runtime", runtime_logs)):
        rendered = [json.dumps(record, sort_keys=True, ensure_ascii=False) for record in records]
        marker = next(
            (
                index
                for index, record in enumerate(records)
                if AFFIRMATIVE_FAILURE.search(str(record.get("message", "")))
            ),
            None,
        )
        if marker is not None:
            start = max(0, marker - 5)
            cluster = rendered[start : start + MAX_SUMMARY_LINES]
            classification, phase = classify(records[start : start + MAX_SUMMARY_LINES], source)
            return cluster, classification, phase
    return [], "unknown", "unknown"


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    required = {
        "collected_at",
        "deployment_id",
        "service",
        "environment",
        "deployment_status",
        "collection_status",
        "source_commit_sha",
        "build_log_line_count",
        "runtime_log_line_count",
        "redaction_count",
    }
    if manifest.get("version") != 1 or not required.issubset(manifest):
        raise ValueError("Manifest does not satisfy schema version 1")
    if PROHIBITED_MANIFEST_FIELDS.intersection(key.lower() for key in manifest):
        raise ValueError("Manifest contains a prohibited field")


def _redact_failure_text(value: str) -> str:
    """Remove authorization headers and redact known secret forms and the Railway token."""
    token = os.environ.get("RAILWAY_TOKEN", "")
    without_token = value.replace(token, REDACTED) if token else value
    without_authorization = re.sub(
        r"(?i)\bAuthorization\s*[:=]\s*(?:Bearer\s+)?[^\r\n]*",
        REDACTED,
        without_token,
    )
    without_bearer_token = re.sub(
        r"(?i)(\bBearer\s+)[^\s,;]+", r"\1[REDACTED]", without_authorization
    )
    return redact_text(without_bearer_token)[0]


def _bounded_output(value: str) -> str:
    """Redact output, then retain its first 100 lines and at most 16 KiB."""
    lines = _redact_failure_text(value).splitlines()[:MAX_FAILURE_LINES]
    encoded = "\n".join(lines).encode()[:MAX_FAILURE_BYTES]
    return encoded.decode(errors="ignore")


def railway_command(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["railway", *args], check=True, capture_output=True, text=True, timeout=120
        )
    except subprocess.CalledProcessError as error:
        raise CommandFailure(
            command=[_redact_failure_text(part) for part in ["railway", *args]],
            exit_code=error.returncode,
            stdout=_bounded_output(error.stdout or ""),
            stderr=_bounded_output(error.stderr or ""),
        ) from None
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode(errors="ignore") if isinstance(error.stdout, bytes) else error.stdout
        stderr = error.stderr.decode(errors="ignore") if isinstance(error.stderr, bytes) else error.stderr
        raise CommandFailure(
            command=[_redact_failure_text(part) for part in ["railway", *args]],
            exit_code=124,
            stdout=_bounded_output(stdout or ""),
            stderr=_bounded_output(stderr or ""),
        ) from None
    return completed.stdout


def _deployment_list_command(service: str, environment: str) -> list[str]:
    return [
        "deployment",
        "list",
        "--service",
        service,
        "--environment",
        environment,
        "--json",
    ]


def wait_for_terminal_deployment(
    deployment: Deployment,
    *,
    service: str,
    environment: str,
    runner: Callable[[list[str]], str],
    initial_status_was_queried: bool,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    interval_seconds: float = POLL_INTERVAL_SECONDS,
    maximum_wait_seconds: float = MAX_POLL_SECONDS,
) -> PollingResult:
    """Poll read-only deployment state until terminal or the monotonic deadline."""
    started_at = monotonic()
    current = deployment
    attempt_count = 0
    needs_query = not initial_status_was_queried or current.status.upper() not in TERMINAL_DEPLOYMENT_STATES
    while needs_query:
        elapsed = max(0.0, monotonic() - started_at)
        if attempt_count and elapsed >= maximum_wait_seconds:
            return PollingResult(current, False, elapsed, attempt_count)
        records = parse_json_records(runner(_deployment_list_command(service, environment)))
        observed = resolve_deployment(current.deployment_id, {}, records, service, environment)
        current = Deployment(
            deployment_id=current.deployment_id,
            status=observed.status,
            created_at=observed.created_at or current.created_at,
            service=observed.service or current.service,
            environment=observed.environment or current.environment,
            source_commit_sha=observed.source_commit_sha or current.source_commit_sha,
        )
        attempt_count += 1
        elapsed = max(0.0, monotonic() - started_at)
        if current.status.upper() in TERMINAL_DEPLOYMENT_STATES:
            return PollingResult(current, True, elapsed, attempt_count)
        if elapsed >= maximum_wait_seconds:
            return PollingResult(current, False, elapsed, attempt_count)
        sleeper(min(interval_seconds, maximum_wait_seconds - elapsed))
        needs_query = True
    return PollingResult(current, True, max(0.0, monotonic() - started_at), attempt_count)


def _write_timeout_artifacts(
    output_dir: Path,
    deployment: Deployment,
    *,
    elapsed_seconds: float,
    attempt_count: int,
    now: Callable[[], datetime],
) -> tuple[dict[str, Any], str]:
    elapsed = round(elapsed_seconds, 3)
    manifest: dict[str, Any] = {
        "version": 1,
        "collected_at": now().isoformat(),
        "deployment_id": deployment.deployment_id,
        "service": deployment.service,
        "environment": deployment.environment,
        "deployment_status": deployment.status,
        "collection_status": "incomplete",
        "classification": "observer-timeout",
        "source_commit_sha": deployment.source_commit_sha,
        "build_log_line_count": 0,
        "runtime_log_line_count": 0,
        "redaction_count": 0,
    }
    validate_manifest(manifest)
    failure = {
        "deployment_id": deployment.deployment_id,
        "last_observed_status": deployment.status,
        "elapsed_seconds": elapsed,
        "polling_attempt_count": attempt_count,
    }
    summary = (
        "## Railway deployment observer\n\n"
        "Collection stopped at the bounded polling deadline.\n\n"
        f"- Deployment ID: `{deployment.deployment_id}`\n"
        f"- Last observed status: `{deployment.status}`\n"
        "- Classification: `observer-timeout`\n"
        f"- Elapsed seconds: `{elapsed}`\n"
        f"- Polling attempts: `{attempt_count}`\n"
        "- Sanitized diagnostics: `failure.json`\n"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output_dir / "summary.md").write_text(summary)
    (output_dir / "failure.json").write_text(json.dumps(failure, indent=2) + "\n")
    return manifest, summary


def collect(
    *,
    output_dir: Path,
    service: str,
    environment: str,
    explicit_id: str | None,
    event: Mapping[str, Any],
    include_runtime_logs: bool,
    runner: Callable[[list[str]], str] = railway_command,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    poll_interval_seconds: float = POLL_INTERVAL_SECONDS,
    maximum_wait_seconds: float = MAX_POLL_SECONDS,
) -> tuple[Deployment, dict[str, Any], str]:
    """Collect all content in memory, redact it, then atomically expose safe files."""
    known_id = resolve_known_deployment_id(explicit_id, event)
    deployments: list[dict[str, Any]] = []
    if known_id is None:
        deployments = parse_json_records(runner(_deployment_list_command(service, environment)))
    deployment = resolve_deployment(known_id, event, deployments, service, environment)
    polling = wait_for_terminal_deployment(
        deployment,
        service=service,
        environment=environment,
        runner=runner,
        initial_status_was_queried=known_id is None,
        monotonic=monotonic,
        sleeper=sleeper,
        interval_seconds=poll_interval_seconds,
        maximum_wait_seconds=maximum_wait_seconds,
    )
    deployment = polling.deployment
    if not polling.terminal:
        timeout_manifest, summary = _write_timeout_artifacts(
            output_dir,
            deployment,
            elapsed_seconds=polling.elapsed_seconds,
            attempt_count=polling.attempt_count,
            now=now,
        )
        return deployment, timeout_manifest, summary
    build_raw = parse_json_records(
        runner(
            [
                "logs",
                deployment.deployment_id,
                "--service",
                service,
                "--environment",
                environment,
                "--build",
                "--lines",
                "5000",
                "--json",
            ]
        )
    )[:MAX_LOG_LINES]
    runtime_raw = (
        parse_json_records(
            runner(
                [
                    "logs",
                    deployment.deployment_id,
                    "--service",
                    service,
                    "--environment",
                    environment,
                    "--deployment",
                    "--lines",
                    "5000",
                    "--json",
                ]
            )
        )[:MAX_LOG_LINES]
        if include_runtime_logs
        else []
    )
    redacted_build = redact(build_raw)
    redacted_runtime = redact(runtime_raw)
    build_logs = list(redacted_build.value)
    runtime_logs = list(redacted_runtime.value)
    cluster, classification, phase = first_error_cluster(build_logs, runtime_logs)
    artifact_name = f"railway-deployment-{deployment.deployment_id}"
    manifest: dict[str, Any] = {
        "version": 1,
        "collected_at": now().isoformat(),
        "deployment_id": deployment.deployment_id,
        "service": deployment.service,
        "environment": deployment.environment,
        "deployment_status": deployment.status,
        "collection_status": "complete",
        "source_commit_sha": deployment.source_commit_sha,
        "build_log_line_count": len(build_logs),
        "runtime_log_line_count": len(runtime_logs),
        "redaction_count": redacted_build.count + redacted_runtime.count,
    }
    validate_manifest(manifest)
    quoted = "\n".join(f"    {line}" for line in cluster) or "    No error cluster found."
    summary = (
        "## Railway deployment observer\n\n"
        f"- Deployment ID: `{deployment.deployment_id}`\n"
        f"- Service: `{deployment.service}`\n"
        f"- Environment: `{deployment.environment}`\n"
        f"- Status: `{deployment.status}`\n"
        f"- Commit SHA: `{deployment.source_commit_sha or 'unknown'}`\n"
        f"- Build/runtime lines: `{len(build_logs)}` / `{len(runtime_logs)}`\n"
        f"- Classification: `{classification}`\n"
        f"- Likely failing phase: `{phase}`\n"
        f"- Artifact: `{artifact_name}`\n\n"
        "### First bounded error cluster\n\n"
        f"{quoted}\n"
    )
    # All potentially sensitive processing has succeeded before the directory is populated.
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    _write_jsonl(output_dir / "build-log.jsonl", build_logs)
    _write_jsonl(output_dir / "runtime-log.jsonl", runtime_logs)
    (output_dir / "summary.md").write_text(summary)
    return deployment, manifest, summary


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    content = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    path.write_text(content)
