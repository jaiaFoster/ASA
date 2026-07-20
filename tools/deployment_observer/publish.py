#!/usr/bin/env python3
"""Publish a bounded Railway report to the pull request for the deployed commit."""

from __future__ import annotations

import html
import json
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.deployment_observer.observer import (
    REDACTED,
    first_error_cluster,
    redact_text,
    validate_manifest,
)

COMMENT_MARKER = "<!-- ASA_RAILWAY_DEPLOYMENT_OBSERVER -->"
MAX_COMMENT_CHARACTERS = 50_000
MAX_ROOT_CAUSE_LINES = 20
MAX_BUILD_LOG_LINES = 100
MAX_RUNTIME_LOG_LINES = 150
MAX_HEALTHCHECK_LOG_LINES = 100
SUPPORTED_CLASSIFICATIONS = frozenset(
    {
        "build",
        "startup",
        "import",
        "migration",
        "healthcheck",
        "crash",
        "timeout",
        "infrastructure",
        "unknown",
    }
)


class GitHubApiError(RuntimeError):
    """A safe GitHub API failure without response content or credentials."""


@dataclass(frozen=True)
class PullRequest:
    number: int
    url: str


@dataclass(frozen=True)
class Resolution:
    status: str
    pull_request: PullRequest | None = None


ApiCall = Callable[[str, str, Mapping[str, Any] | None], Any]


class GitHubClient:
    def __init__(
        self, repository: str, token: str, api_url: str = "https://api.github.com"
    ) -> None:
        self.repository = repository
        self._token = token
        self._api_url = api_url.rstrip("/")

    def call(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> Any:
        body = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            f"{self._api_url}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "asa-railway-deployment-observer",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310 -- fixed GitHub API origin
                raw = response.read()
        except (HTTPError, URLError, TimeoutError) as error:
            raise GitHubApiError(f"GitHub API request failed ({type(error).__name__})") from None
        return json.loads(raw) if raw else None


def resolve_pull_request(repository: str, commit_sha: str, api_call: ApiCall) -> Resolution:
    """Resolve one PR without branch-name inference, preferring exact merge commits."""
    encoded_repository = quote(repository, safe="/")
    encoded_sha = quote(commit_sha, safe="")
    try:
        repository_data = api_call("GET", f"/repos/{encoded_repository}", None)
        candidates = api_call(
            "GET", f"/repos/{encoded_repository}/commits/{encoded_sha}/pulls?per_page=100", None
        )
    except GitHubApiError:
        return Resolution("error")
    if not isinstance(repository_data, Mapping) or not isinstance(candidates, list):
        return Resolution("error")
    default_branch = str(repository_data.get("default_branch", ""))
    records = [item for item in candidates if isinstance(item, Mapping)]
    exact = [item for item in records if item.get("merge_commit_sha") == commit_sha]
    selected = _select_one(exact, default_branch)
    if selected is None and not exact:
        selected = _select_one(records, default_branch)
    if selected is not None:
        number = selected.get("number")
        url = selected.get("html_url")
        if isinstance(number, int) and isinstance(url, str):
            return Resolution("resolved", PullRequest(number, url))
        return Resolution("error")
    return Resolution("not_found" if not records else "ambiguous")


def _select_one(records: list[Mapping[str, Any]], default_branch: str) -> Mapping[str, Any] | None:
    merged_to_default = [
        item
        for item in records
        if item.get("merged_at")
        and isinstance(item.get("base"), Mapping)
        and item["base"].get("ref") == default_branch
    ]
    if len(merged_to_default) == 1:
        return merged_to_default[0]
    if len(merged_to_default) > 1:
        return None
    return records[0] if len(records) == 1 else None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        parsed = json.loads(line)
        if isinstance(parsed, dict):
            records.append(parsed)
    return records


def _safe_inline(value: Any) -> str:
    redacted = _redact_for_comment(str(value or "unknown"))
    single_line = " ".join(redacted.splitlines())
    return html.escape(single_line, quote=False).replace("|", "\\|").replace("`", "'")


def _redact_for_comment(value: str) -> str:
    safe = value
    for variable in ("RAILWAY_TOKEN", "GITHUB_TOKEN"):
        secret = os.environ.get(variable, "")
        if secret:
            safe = safe.replace(secret, REDACTED)
    return redact_text(safe)[0]


def _bounded_code(lines: list[str], maximum_lines: int, maximum_characters: int) -> str:
    safe_lines: list[str] = []
    used = 0
    for line in lines[:maximum_lines]:
        redacted = _redact_for_comment(line)
        safe = html.escape(redacted, quote=False).replace("```", "` ` `")
        remaining = maximum_characters - used
        if remaining <= 0:
            break
        safe_lines.append(safe[:remaining])
        used += len(safe_lines[-1]) + 1
    return "\n".join(safe_lines) or "No relevant log lines were collected."


def _message_lines(records: list[dict[str, Any]]) -> list[str]:
    return [json.dumps(record, sort_keys=True, ensure_ascii=False) for record in records]


def _public_classification(manifest: Mapping[str, Any], root_lines: list[str]) -> str:
    raw = str(manifest.get("classification", "unknown"))
    text = "\n".join(root_lines).lower()
    if raw in SUPPORTED_CLASSIFICATIONS:
        return raw
    if raw == "observer-timeout":
        return "timeout"
    if raw == "startup_or_packaging":
        return "import" if "no module named" in text else "startup"
    if raw in {"configuration", "database_connectivity"}:
        return "startup"
    return "unknown"


def render_comment(
    manifest: Mapping[str, Any], output_dir: Path, workflow_run_url: str, artifact_url: str
) -> str:
    """Render a redacted report whose fixed budgets remain below GitHub's comment limit."""
    build_logs = _read_jsonl(output_dir / "build-log.jsonl")
    runtime_logs = _read_jsonl(output_dir / "runtime-log.jsonl")
    root_cluster, _, phase = first_error_cluster(build_logs, runtime_logs)
    classification = _public_classification(manifest, root_cluster)
    status = str(manifest.get("deployment_status", "unknown")).upper()
    failed = status not in {"SUCCESS", "SUCCEEDED"}
    build_status = (
        "failed" if classification == "build" else ("completed" if build_logs else "not detected")
    )
    migration_seen = any(
        "alembic" in line.lower() for line in _message_lines(runtime_logs + build_logs)
    )
    migration_status = (
        "failed"
        if classification == "migration"
        else ("detected" if migration_seen else "not detected")
    )
    runtime_status = (
        "failed"
        if classification in {"startup", "import", "crash"}
        else ("collected" if runtime_logs else "not collected")
    )
    health_lines = [line for line in _message_lines(runtime_logs) if "health" in line.lower()]
    health_status = (
        "failed" if health_lines and failed else ("passed" if health_lines else "not detected")
    )
    root = root_cluster[:MAX_ROOT_CAUSE_LINES]
    root_excerpt = _bounded_code(root, MAX_ROOT_CAUSE_LINES, 4_000)
    build_excerpt = _bounded_code(_message_lines(build_logs), MAX_BUILD_LOG_LINES, 8_000)
    runtime_excerpt = _bounded_code(_message_lines(runtime_logs), MAX_RUNTIME_LOG_LINES, 12_000)
    health_excerpt = _bounded_code(health_lines, MAX_HEALTHCHECK_LOG_LINES, 8_000)
    report = f"""{COMMENT_MARKER}
## Railway Deployment Report

| Field | Result |
| --- | --- |
| Deployment | `{_safe_inline(manifest.get("deployment_id"))}` |
| Environment / service | `{_safe_inline(manifest.get("environment"))}` / `{_safe_inline(manifest.get("service"))}` |
| Commit | `{_safe_inline(manifest.get("source_commit_sha"))}` |
| Railway terminal status | **{_safe_inline(status)}** |
| Observer collection | `{_safe_inline(manifest.get("collection_status"))}` |
| Classification / phase | `{_safe_inline(classification)}` / `{_safe_inline(phase)}` |
| Build | `{build_status}` |
| Migration | `{migration_status}` |
| Runtime | `{runtime_status}` |
| Health check | `{health_status}` |

### Root cause

```text
{root_excerpt}
```

[Observer workflow run]({workflow_run_url}) · [Diagnostic artifact details]({artifact_url})

<details><summary>Bounded build logs (up to {MAX_BUILD_LOG_LINES} lines)</summary>

```text
{build_excerpt}
```
</details>

<details><summary>Bounded runtime logs (up to {MAX_RUNTIME_LOG_LINES} lines)</summary>

```text
{runtime_excerpt}
```
</details>

<details><summary>Bounded health-check logs (up to {MAX_HEALTHCHECK_LOG_LINES} lines)</summary>

```text
{health_excerpt}
```
</details>

<!--
ASA_RAILWAY_DEPLOYMENT_OBSERVER
deployment_id={_safe_inline(manifest.get("deployment_id"))}
deployment_status={_safe_inline(status)}
classification={_safe_inline(classification)}
commit_sha={_safe_inline(manifest.get("source_commit_sha"))}
service={_safe_inline(manifest.get("service"))}
environment={_safe_inline(manifest.get("environment"))}
workflow_run_id={_safe_inline(os.environ.get("GITHUB_RUN_ID"))}
-->
"""
    if len(report) > MAX_COMMENT_CHARACTERS:
        raise ValueError("Rendered observer comment exceeds its fixed size bound")
    if REDACTED not in report and any(
        secret in report.lower()
        for secret in ("authorization: bearer", "password=", "database_url=")
    ):
        raise ValueError("Rendered observer comment contains an unredacted secret form")
    return report


def _find_marked_comment(
    repository: str, number: int, api_call: ApiCall
) -> Mapping[str, Any] | None:
    page = 1
    while True:
        comments = api_call(
            "GET", f"/repos/{repository}/issues/{number}/comments?per_page=100&page={page}", None
        )
        if not isinstance(comments, list):
            raise GitHubApiError("GitHub comments response was invalid")
        for comment in comments:
            if isinstance(comment, Mapping) and COMMENT_MARKER in str(comment.get("body", "")):
                return comment
        if len(comments) < 100:
            return None
        page += 1


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    validate_manifest(manifest)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    temporary.replace(path)


def publish(output_dir: Path, repository: str, api_call: ApiCall) -> int:
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        print("No observer manifest exists; pull request publication was skipped.")
        return 0
    parsed = json.loads(manifest_path.read_text())
    if not isinstance(parsed, dict):
        print("Observer manifest is invalid; pull request publication failed.", file=sys.stderr)
        return 1
    manifest: dict[str, Any] = parsed
    sha = str(manifest.get("source_commit_sha", "")).strip()
    resolution = resolve_pull_request(repository, sha, api_call) if sha else Resolution("not_found")
    manifest.update(
        pull_request_resolution_status=resolution.status,
        pull_request_number=None,
        pull_request_url=None,
        pull_request_comment_status="skipped",
        pull_request_comment_url=None,
    )
    if resolution.pull_request is None:
        _write_manifest(manifest_path, manifest)
        print(f"Pull request publication skipped: resolution status is {resolution.status}.")
        return 0 if resolution.status != "error" else 1
    pull_request = resolution.pull_request
    manifest["pull_request_number"] = pull_request.number
    manifest["pull_request_url"] = pull_request.url
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    run_id = os.environ.get("GITHUB_RUN_ID", "unknown")
    run_url = f"{server}/{repository}/actions/runs/{run_id}"
    artifact_url = f"{run_url}#artifacts"
    try:
        body = render_comment(manifest, output_dir, run_url, artifact_url)
        existing = _find_marked_comment(repository, pull_request.number, api_call)
        if existing is None:
            response = api_call(
                "POST", f"/repos/{repository}/issues/{pull_request.number}/comments", {"body": body}
            )
            comment_status = "created"
        else:
            comment_id = existing.get("id")
            if not isinstance(comment_id, int):
                raise GitHubApiError("Marked comment has no valid ID")
            response = api_call(
                "PATCH", f"/repos/{repository}/issues/comments/{comment_id}", {"body": body}
            )
            comment_status = "updated"
        if not isinstance(response, Mapping) or not isinstance(response.get("html_url"), str):
            raise GitHubApiError("GitHub comment response was invalid")
        manifest["pull_request_comment_status"] = comment_status
        manifest["pull_request_comment_url"] = response["html_url"]
        _write_manifest(manifest_path, manifest)
        print(f"Pull request observer comment {comment_status}: {response['html_url']}")
        return 0
    except (GitHubApiError, ValueError, OSError, json.JSONDecodeError) as error:
        manifest["pull_request_comment_status"] = "failed"
        _write_manifest(manifest_path, manifest)
        print(
            f"Pull request comment publication failed safely: {type(error).__name__}",
            file=sys.stderr,
        )
        return 1


def main() -> int:
    output_dir = Path(os.environ.get("OBSERVER_OUTPUT_DIR", ".artifacts/railway-deployment"))
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not repository or not token:
        print(
            "GitHub repository context is incomplete; comment publication failed.", file=sys.stderr
        )
        return 1
    client = GitHubClient(
        repository, token, os.environ.get("GITHUB_API_URL", "https://api.github.com")
    )
    return publish(output_dir, repository, client.call)


if __name__ == "__main__":
    raise SystemExit(main())
