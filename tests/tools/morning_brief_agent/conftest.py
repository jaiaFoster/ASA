"""In-memory GitHub fake implementing the GitHubClient surface used by the tooling."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

BASE = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)


class FakeGitHub:
    def __init__(self) -> None:
        self.issues: dict[int, dict[str, Any]] = {}
        self.comments: dict[int, list[dict[str, Any]]] = {}
        self.pulls: list[dict[str, Any]] = []
        self._next_comment = 1
        self._next_issue = 1
        self.clock = BASE
        self.fail_next_create = False

    def advance(self, **kw: float) -> None:
        self.clock += timedelta(**kw)

    def _iso(self) -> str:
        return self.clock.strftime("%Y-%m-%dT%H:%M:%SZ")

    # GitHubClient surface
    def list_issues(self, labels: str | None = None, state: str = "all") -> list[dict[str, Any]]:
        return [dict(i) for i in sorted(self.issues.values(), key=lambda i: i["number"])]

    def get_issue(self, number: int) -> dict[str, Any]:
        if number not in self.issues:
            raise RuntimeError("HTTP 404")
        return dict(self.issues[number])

    def create_issue(self, title: str, body: str, labels: list[str]) -> dict[str, Any]:
        number = self._next_issue
        self._next_issue += 1
        self.issues[number] = {"number": number, "title": title, "body": body,
                               "state": "open", "labels": labels}
        self.comments[number] = []
        return dict(self.issues[number])

    def seed_issue(self, number: int, title: str, body: str, state: str = "open") -> None:
        self.issues[number] = {"number": number, "title": title, "body": body, "state": state}
        self.comments.setdefault(number, [])
        self._next_issue = max(self._next_issue, number + 1)

    def set_issue_state(self, number: int, state: str, reason: str | None = None) -> None:
        self.issues[number]["state"] = state

    def list_comments(self, number: int) -> list[dict[str, Any]]:
        return [dict(c) for c in self.comments.get(number, [])]

    def create_comment(self, number: int, body: str, assoc: str = "OWNER") -> dict[str, Any]:
        comment = {"id": self._next_comment, "body": body, "created_at": self._iso(),
                   "author_association": assoc}
        self._next_comment += 1
        self.comments.setdefault(number, []).append(comment)
        return dict(comment)

    def delete_comment(self, comment_id: int) -> None:
        for items in self.comments.values():
            items[:] = [c for c in items if c["id"] != comment_id]

    def ensure_label(self, name: str, color: str, description: str) -> None:
        return None

    def list_pulls(self, state: str = "open") -> list[dict[str, Any]]:
        return list(self.pulls)


@pytest.fixture()
def gh() -> FakeGitHub:
    return FakeGitHub()


@pytest.fixture()
def brief_root(tmp_path):
    canon = tmp_path / "claude-morning-briefs"
    canon.mkdir()
    (canon / "2026-10-08.md").write_text("brief one")
    (canon / "2026-10-09.md").write_text("brief two")
    (canon / "2026-10-12.md").write_text("brief three")
    (canon / "2026-10-13.md").write_text("brief four")
    (canon / "README.md").write_text("not a brief")
    (canon / "ENGINEERING_CASE_INDEX.md").write_text("not a brief")
    return tmp_path
