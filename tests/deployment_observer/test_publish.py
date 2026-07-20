from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from tools.deployment_observer.publish import (
    COMMENT_MARKER,
    MAX_COMMENT_CHARACTERS,
    GitHubApiError,
    publish,
    render_comment,
    resolve_pull_request,
)


def pr(
    number: int, *, merge_sha: str = "sha", base: str = "main", merged: bool = True
) -> dict[str, Any]:
    return {
        "number": number,
        "html_url": f"https://github.test/owner/repo/pull/{number}",
        "merge_commit_sha": merge_sha,
        "merged_at": "2026-07-20T00:00:00Z" if merged else None,
        "base": {"ref": base},
    }


def resolver_api(candidates: list[dict[str, Any]]):
    def call(method: str, path: str, payload: Mapping[str, Any] | None) -> Any:
        assert method == "GET"
        assert payload is None
        if path == "/repos/owner/repo":
            return {"default_branch": "main"}
        assert path.startswith("/repos/owner/repo/commits/")
        return candidates

    return call


def manifest() -> dict[str, Any]:
    return {
        "version": 1,
        "collected_at": "2026-07-20T00:00:00+00:00",
        "deployment_id": "deployment-id",
        "service": "ASA",
        "environment": "production",
        "deployment_status": "FAILED",
        "collection_status": "complete",
        "classification": "startup_or_packaging",
        "phase": "startup",
        "source_commit_sha": "sha",
        "build_log_line_count": 1,
        "runtime_log_line_count": 2,
        "redaction_count": 0,
        "pull_request_resolution_status": "not_found",
        "pull_request_number": None,
        "pull_request_url": None,
        "pull_request_comment_status": "skipped",
        "pull_request_comment_url": None,
    }


def write_artifacts(output: Path, data: dict[str, Any] | None = None) -> None:
    output.mkdir()
    (output / "manifest.json").write_text(json.dumps(data or manifest()))
    (output / "build-log.jsonl").write_text('{"message":"build complete"}\n')
    (output / "runtime-log.jsonl").write_text(
        '{"message":"No module named asa"}\n{"message":"healthcheck failed"}\n'
    )


def test_exact_merge_commit_resolves_merged_default_branch_pull_request() -> None:
    result = resolve_pull_request(
        "owner/repo",
        "sha",
        resolver_api([pr(10, merge_sha="other"), pr(11, merge_sha="sha")]),
    )
    assert result.status == "resolved"
    assert result.pull_request is not None
    assert result.pull_request.number == 11


def test_single_associated_pull_request_is_selected() -> None:
    result = resolve_pull_request(
        "owner/repo", "sha", resolver_api([pr(12, merge_sha="other", merged=False)])
    )
    assert result.status == "resolved"
    assert result.pull_request is not None
    assert result.pull_request.number == 12


def test_no_associated_pull_request_is_not_found() -> None:
    assert resolve_pull_request("owner/repo", "sha", resolver_api([])).status == "not_found"


def test_multiple_associated_pull_requests_are_ambiguous() -> None:
    candidates = [
        pr(12, merge_sha="other", merged=False),
        pr(13, merge_sha="another", merged=False),
    ]
    assert resolve_pull_request("owner/repo", "sha", resolver_api(candidates)).status == "ambiguous"


class FakeApi:
    def __init__(
        self, comments: list[dict[str, Any]] | None = None, *, fail_comment: bool = False
    ) -> None:
        self.comments = comments or []
        self.fail_comment = fail_comment
        self.calls: list[tuple[str, str, Mapping[str, Any] | None]] = []

    def __call__(self, method: str, path: str, payload: Mapping[str, Any] | None) -> Any:
        self.calls.append((method, path, payload))
        if path == "/repos/owner/repo":
            return {"default_branch": "main"}
        if "/commits/" in path:
            return [pr(21)]
        if path.endswith("/comments?per_page=100&page=1"):
            return self.comments
        if self.fail_comment:
            raise GitHubApiError("seeded failure")
        if method == "POST":
            self.comments.append({"id": 91, "body": payload["body"] if payload else ""})
            return {"html_url": "https://github.test/comment/91"}
        if method == "PATCH":
            assert payload is not None
            self.comments[0]["body"] = payload["body"]
            return {"html_url": "https://github.test/comment/91"}
        raise AssertionError((method, path))


def test_rerun_updates_one_marked_comment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "artifacts"
    write_artifacts(output)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    api = FakeApi()
    assert publish(output, "owner/repo", api) == 0
    assert publish(output, "owner/repo", api) == 0
    assert len(api.comments) == 1
    assert [method for method, _, _ in api.calls].count("POST") == 1
    assert [method for method, _, _ in api.calls].count("PATCH") == 1
    saved = json.loads((output / "manifest.json").read_text())
    assert saved["pull_request_resolution_status"] == "resolved"
    assert saved["pull_request_comment_status"] == "updated"
    assert saved["pull_request_comment_url"] == "https://github.test/comment/91"


@pytest.mark.parametrize(
    ("candidates", "expected"),
    [
        ([], "not_found"),
        ([pr(1, merge_sha="a", merged=False), pr(2, merge_sha="b", merged=False)], "ambiguous"),
    ],
)
def test_unresolved_pull_request_skips_comment_and_preserves_artifact(
    tmp_path: Path, candidates: list[dict[str, Any]], expected: str
) -> None:
    output = tmp_path / expected
    write_artifacts(output)
    calls: list[str] = []

    def api(method: str, path: str, payload: Mapping[str, Any] | None) -> Any:
        calls.append(path)
        return {"default_branch": "main"} if path == "/repos/owner/repo" else candidates

    assert publish(output, "owner/repo", api) == 0
    saved = json.loads((output / "manifest.json").read_text())
    assert saved["pull_request_resolution_status"] == expected
    assert saved["pull_request_comment_status"] == "skipped"
    assert (output / "build-log.jsonl").exists()
    assert not any("/comments" in path for path in calls)


def test_decisive_runtime_error_precedes_healthcheck_symptom_in_report(tmp_path: Path) -> None:
    output = tmp_path / "report"
    write_artifacts(output)
    report = render_comment(
        manifest(), output, "https://github.test/run", "https://github.test/artifact"
    )
    assert "`import` / `startup`" in report
    assert "No module named asa" in report
    assert "Health check | `failed`" in report


def test_secrets_are_redacted_and_oversized_logs_remain_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "bounded"
    write_artifacts(output)
    monkeypatch.setenv("RAILWAY_TOKEN", "bare-railway-secret")
    secret_line = json.dumps(
        {
            "message": (
                "Authorization: Bearer token password=hunter2 bare-railway-secret " + ("x" * 20_000)
            )
        }
    )
    (output / "runtime-log.jsonl").write_text((secret_line + "\n") * 500)
    report = render_comment(
        manifest(), output, "https://github.test/run", "https://github.test/artifact"
    )
    assert "token" not in report
    assert "hunter2" not in report
    assert "bare-railway-secret" not in report
    assert "[REDACTED]" in report
    assert len(report) <= MAX_COMMENT_CHARACTERS


def test_comment_api_failure_records_failure_without_removing_artifact(tmp_path: Path) -> None:
    output = tmp_path / "failed"
    write_artifacts(output)
    api = FakeApi(fail_comment=True)
    assert publish(output, "owner/repo", api) == 1
    saved = json.loads((output / "manifest.json").read_text())
    assert saved["pull_request_resolution_status"] == "resolved"
    assert saved["pull_request_comment_status"] == "failed"
    assert (output / "runtime-log.jsonl").exists()


def test_comment_marker_and_hidden_metadata_are_stable(tmp_path: Path) -> None:
    output = tmp_path / "metadata"
    write_artifacts(output)
    report = render_comment(
        manifest(), output, "https://github.test/run", "https://github.test/artifact"
    )
    assert report.startswith(COMMENT_MARKER)
    assert report.count(COMMENT_MARKER) == 1
    assert "\nASA_RAILWAY_DEPLOYMENT_OBSERVER\n" in report
    assert "deployment_id=deployment-id" in report
    assert "workflow_run_id=" in report
