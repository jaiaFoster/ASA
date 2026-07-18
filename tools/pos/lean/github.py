"""
GitHub adapter for the Lean POS reconciliation layer.

Two implementations share a common interface:
  FixtureAdapter  — loads a pre-normalized YAML snapshot (no network)
  LiveAdapter     — fetches from the GitHub REST API (network required)

The interface is read-only by design. No write endpoints exist.

Normalized snapshot format (used by both adapters):

  repository: owner/repo
  observed_at: ISO-8601          # injected for determinism in tests
  authority:
    authorized_mergers: [login, ...]
  issue:                         # null if not provided
    number: int
    state: open|closed
    labels: [str, ...]
    state_reason: null|completed|not_planned
  pull_request:                  # null if not provided
    number: int
    state: open|closed
    merged: bool
    draft: bool
    merged_by: str|null
    merged_at: ISO-8601|null
    merge_commit_sha: str|null
    head_ref: str|null
    base_ref: str|null
    reviews:
      - login: str
        state: APPROVED|CHANGES_REQUESTED|COMMENTED|DISMISSED
    checks:
      required: [context_name, ...]
      statuses:
        - context: str
          state: success|failure|error|pending|neutral|skipped
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import yaml

from tools.pos.lean.schemas import (
    RECON_WRITE_ATTEMPT_PROHIBITED,
    RECON_UNSUPPORTED_RESPONSE,
    RECON_REMOTE_UNAVAILABLE,
    load_yaml,
)


class WriteAttemptError(RuntimeError):
    """Raised if any code path attempts a GitHub write operation."""

    def __init__(self) -> None:
        super().__init__(f"[{RECON_WRITE_ATTEMPT_PROHIBITED}] GitHub write operations are prohibited")


class GitHubSnapshot:
    """Immutable normalized view of GitHub state for one work item."""

    def __init__(self, raw: dict) -> None:
        self._raw = raw

    @property
    def repository(self) -> str:
        return self._raw.get("repository", "")

    @property
    def observed_at(self) -> str:
        return self._raw.get("observed_at", "")

    @property
    def authority(self) -> dict:
        return self._raw.get("authority") or {}

    @property
    def issue(self) -> dict | None:
        return self._raw.get("issue")

    @property
    def pull_request(self) -> dict | None:
        return self._raw.get("pull_request")

    def raw(self) -> dict:
        return dict(self._raw)


class FixtureAdapter:
    """Load a pre-normalized YAML fixture; no network access."""

    def __init__(self, fixture_path: Path) -> None:
        self._path = fixture_path

    def fetch(self) -> GitHubSnapshot:
        try:
            raw = load_yaml(self._path)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"[{RECON_REMOTE_UNAVAILABLE}] fixture not found: {self._path}"
            )
        except yaml.YAMLError as exc:
            raise ValueError(
                f"[{RECON_UNSUPPORTED_RESPONSE}] fixture YAML parse error: {exc}"
            )
        if not isinstance(raw, dict):
            raise ValueError(
                f"[{RECON_UNSUPPORTED_RESPONSE}] fixture must be a YAML mapping"
            )
        # Allow observed_at override for test determinism
        return GitHubSnapshot(raw)

    # Write guard — this adapter must never be extended with write methods.
    def _write(self, *args: Any, **kwargs: Any) -> None:
        raise WriteAttemptError()


class LiveAdapter:
    """Fetch from the GitHub REST API. Requires network and a token."""

    def __init__(self, repo: str, token: str | None = None) -> None:
        self._repo = repo
        self._token = token

    def fetch(
        self,
        issue_number: int | None = None,
        pr_number: int | None = None,
        observed_at: str | None = None,
    ) -> GitHubSnapshot:
        """Fetch and normalize GitHub state.

        Requires the `requests` library at runtime. Not imported at module
        level so the offline validator never transitively depends on it.
        """
        try:
            import requests  # local import — keeps offline path clean
        except ImportError as exc:
            raise ImportError(
                f"[{RECON_REMOTE_UNAVAILABLE}] 'requests' is required for live GitHub access: {exc}"
            ) from exc

        headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        base = f"https://api.github.com/repos/{self._repo}"
        raw: dict[str, Any] = {
            "repository": self._repo,
            "observed_at": observed_at or datetime.datetime.utcnow().isoformat() + "Z",
            "authority": {},
            "issue": None,
            "pull_request": None,
        }

        if issue_number is not None:
            resp = requests.get(f"{base}/issues/{issue_number}", headers=headers, timeout=15)
            self._check_response(resp, f"issue #{issue_number}")
            data = resp.json()
            raw["issue"] = {
                "number": data["number"],
                "state": data["state"],
                "labels": [lb["name"] for lb in data.get("labels", [])],
                "state_reason": data.get("state_reason"),
            }

        if pr_number is not None:
            resp = requests.get(f"{base}/pulls/{pr_number}", headers=headers, timeout=15)
            self._check_response(resp, f"PR #{pr_number}")
            data = resp.json()
            merged_by = None
            if data.get("merged_by"):
                merged_by = data["merged_by"].get("login")

            # Fetch reviews
            rev_resp = requests.get(
                f"{base}/pulls/{pr_number}/reviews", headers=headers, timeout=15
            )
            self._check_response(rev_resp, f"PR #{pr_number} reviews")
            reviews = [
                {"login": r["user"]["login"], "state": r["state"]}
                for r in rev_resp.json()
            ]

            # Fetch check runs
            head_sha = data.get("head", {}).get("sha", "")
            check_statuses: list[dict] = []
            if head_sha:
                chk_resp = requests.get(
                    f"{base}/commits/{head_sha}/check-runs",
                    headers=headers,
                    timeout=15,
                )
                self._check_response(chk_resp, f"check-runs for {head_sha}")
                for run in chk_resp.json().get("check_runs", []):
                    check_statuses.append(
                        {"context": run["name"], "state": run.get("conclusion") or run.get("status", "pending")}
                    )

            raw["pull_request"] = {
                "number": data["number"],
                "state": data["state"],
                "merged": bool(data.get("merged")),
                "draft": bool(data.get("draft")),
                "merged_by": merged_by,
                "merged_at": data.get("merged_at"),
                "merge_commit_sha": data.get("merge_commit_sha"),
                "head_ref": data.get("head", {}).get("ref"),
                "base_ref": data.get("base", {}).get("ref"),
                "reviews": reviews,
                "checks": {"required": [], "statuses": check_statuses},
            }

        return GitHubSnapshot(raw)

    def _check_response(self, resp: Any, label: str) -> None:
        if resp.status_code == 429:
            raise RuntimeError(
                f"[{RECON_REMOTE_UNAVAILABLE}] GitHub rate limit reached fetching {label}"
            )
        if resp.status_code == 404:
            raise RuntimeError(
                f"[{RECON_REMOTE_UNAVAILABLE}] GitHub returned 404 for {label}"
            )
        if not resp.ok:
            raise RuntimeError(
                f"[{RECON_REMOTE_UNAVAILABLE}] GitHub returned {resp.status_code} for {label}"
            )

    # Write guard
    def _write(self, *args: Any, **kwargs: Any) -> None:
        raise WriteAttemptError()
