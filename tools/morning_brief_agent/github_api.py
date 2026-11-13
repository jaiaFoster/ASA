"""Minimal GitHub REST client over ``gh api``.

REST only: GraphQL is blocked in Claude Code sandboxes, and ``gh issue list``/
``gh pr view`` use it. Every list call paginates explicitly; transient 5xx/429
responses are retried with backoff.
"""
from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable
from typing import Any

PER_PAGE = 100
MAX_PAGES = 200
RETRYABLE = ("HTTP 502", "HTTP 503", "HTTP 504", "HTTP 429", "temporarily unavailable")

Runner = Callable[[list[str], str | None], str]


class GitHubError(RuntimeError):
    pass


def _gh_runner(args: list[str], stdin: str | None) -> str:
    proc = subprocess.run(["gh", *args], input=stdin, text=True, capture_output=True)
    if proc.returncode != 0:
        raise GitHubError((proc.stderr or proc.stdout).strip())
    return proc.stdout


class GitHubClient:
    def __init__(
        self,
        repo: str,
        runner: Runner = _gh_runner,
        sleep: Callable[[float], None] = time.sleep,
        retries: int = 4,
    ) -> None:
        self.repo = repo
        self._runner = runner
        self._sleep = sleep
        self._retries = retries

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        args = ["api", "-X", method, f"repos/{self.repo}/{path}"]
        stdin = None
        if body is not None:
            args += ["--input", "-"]
            stdin = json.dumps(body)
        for attempt in range(self._retries + 1):
            try:
                out = self._runner(args, stdin)
                return json.loads(out) if out.strip() else None
            except GitHubError as exc:
                if attempt < self._retries and any(tok in str(exc) for tok in RETRYABLE):
                    self._sleep(min(2**attempt, 30))
                    continue
                raise
        raise GitHubError("unreachable")

    def _paged(self, path: str) -> list[dict[str, Any]]:
        sep = "&" if "?" in path else "?"
        items: list[dict[str, Any]] = []
        for page in range(1, MAX_PAGES + 1):
            batch = self._call("GET", f"{path}{sep}per_page={PER_PAGE}&page={page}")
            items.extend(batch)
            if len(batch) < PER_PAGE:
                return items
        raise GitHubError(f"pagination exceeded {MAX_PAGES} pages for {path}")

    # --- issues -------------------------------------------------------------
    def list_issues(self, labels: str | None = None, state: str = "all") -> list[dict[str, Any]]:
        query = f"issues?state={state}&sort=created&direction=asc"
        if labels:
            query += f"&labels={labels}"
        return [i for i in self._paged(query) if "pull_request" not in i]

    def get_issue(self, number: int) -> dict[str, Any]:
        return self._call("GET", f"issues/{number}")

    def create_issue(self, title: str, body: str, labels: list[str]) -> dict[str, Any]:
        return self._call("POST", "issues", {"title": title, "body": body, "labels": labels})

    def set_issue_state(self, number: int, state: str, reason: str | None = None) -> None:
        body: dict[str, Any] = {"state": state}
        if reason:
            body["state_reason"] = reason
        self._call("PATCH", f"issues/{number}", body)

    def list_comments(self, number: int) -> list[dict[str, Any]]:
        return self._paged(f"issues/{number}/comments")

    def create_comment(self, number: int, body: str) -> dict[str, Any]:
        return self._call("POST", f"issues/{number}/comments", {"body": body})

    def delete_comment(self, comment_id: int) -> None:
        self._call("DELETE", f"issues/comments/{comment_id}")

    def ensure_label(self, name: str, color: str, description: str) -> None:
        try:
            self._call("POST", "labels", {"name": name, "color": color, "description": description})
        except GitHubError as exc:
            if "already_exists" not in str(exc) and "HTTP 422" not in str(exc):
                raise

    # --- pull requests ------------------------------------------------------
    def list_pulls(self, state: str = "open") -> list[dict[str, Any]]:
        return self._paged(f"pulls?state={state}&sort=created&direction=asc")
