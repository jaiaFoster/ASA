"""Durable, crash-safe engineering-issue claims stored as GitHub issue comments.

Arbitration is by comment order (ids are monotonic): the first valid claim wins; later
claims while a claim is live lose. A claim is live while its last claim/heartbeat is
younger than its TTL, measured with GitHub's ``created_at`` (not the payload), so a crashed
worker's claim expires on its own (stale-claim recovery) without any cleanup job.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .github_api import GitHubClient
from .ledger import parse_ts, trusted

CLAIM_RE = re.compile(r"<!-- asa-claim:v1 (\{.*?\}) -->")
DEFAULT_TTL_MINUTES = 240
MAX_TTL_MINUTES = 720


@dataclass
class ClaimStatus:
    state: str  # free | held | stale
    owner: str | None = None
    run_id: str | None = None
    last_activity: datetime | None = None


def render_claim(action: str, owner: str, run_id: str, ttl: int, **extra: Any) -> str:
    payload = {"action": action, "owner": owner, "run_id": run_id, "ttl_minutes": ttl, **extra}
    human = {
        "claim": f"Claimed by `{owner}` (run `{run_id}`); expires {ttl} min after last activity.",
        "heartbeat": f"Heartbeat from `{owner}` (run `{run_id}`).",
        "release": f"Released by `{owner}` (run `{run_id}`): {extra.get('outcome', 'released')}.",
    }[action]
    return f"{human}\n\n<!-- asa-claim:v1 {json.dumps(payload, sort_keys=True)} -->"


def claim_status(comments: list[dict[str, Any]], now: datetime) -> ClaimStatus:
    holder: dict[str, Any] | None = None
    for comment in sorted(comments, key=lambda c: c["id"]):
        if not trusted(comment):
            continue
        match = CLAIM_RE.search(comment.get("body") or "")
        if not match:
            continue
        try:
            rec = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        at = parse_ts(comment["created_at"])
        if holder and at - holder["last"] > holder["ttl"]:
            holder = None  # previous holder expired before this event
        ident = (rec.get("owner"), rec.get("run_id"))
        action = rec.get("action")
        if action == "claim":
            if holder is None:
                ttl = min(int(rec.get("ttl_minutes", DEFAULT_TTL_MINUTES)), MAX_TTL_MINUTES)
                holder = {"ident": ident, "last": at, "ttl": timedelta(minutes=ttl)}
        elif holder and holder["ident"] == ident:
            if action == "heartbeat":
                holder["last"] = at
            elif action == "release":
                holder = None
    if holder is None:
        return ClaimStatus("free")
    state = "stale" if now - holder["last"] > holder["ttl"] else "held"
    return ClaimStatus(state, *holder["ident"], holder["last"])


def owning_prs(pulls: list[dict[str, Any]], number: int) -> list[int]:
    """Open PRs that appear to own ``number``: branch name or any ``#N`` mention."""
    mention = re.compile(rf"(?<![\w/]){re.escape(f'#{number}')}(?!\d)")
    branch = re.compile(rf"(?:^|[/-])issue-{number}(?:$|[/-])")
    owned = []
    for pr in pulls:
        text = f"{pr.get('title') or ''}\n{pr.get('body') or ''}"
        if mention.search(text) or branch.search(pr.get("head", {}).get("ref", "")):
            owned.append(pr["number"])
    return owned


def acquire(
    client: GitHubClient,
    number: int,
    owner: str,
    run_id: str,
    ttl: int = DEFAULT_TTL_MINUTES,
    now: datetime | None = None,
) -> tuple[bool, str]:
    now = now or datetime.now(UTC)
    ttl = min(ttl, MAX_TTL_MINUTES)
    status = claim_status(client.list_comments(number), now)
    if status.state == "held":
        return False, f"held by {status.owner} (run {status.run_id})"
    prs = owning_prs(client.list_pulls("open"), number)
    if prs:
        return False, f"open PR(s) already reference this issue: {prs}"
    posted = client.create_comment(number, render_claim("claim", owner, run_id, ttl))
    after = claim_status(client.list_comments(number), datetime.now(UTC))
    if after.state == "held" and (after.owner, after.run_id) == (owner, run_id):
        note = "recovered stale claim" if status.state == "stale" else "acquired"
        return True, note
    try:
        client.delete_comment(posted["id"])
    except Exception:  # noqa: BLE001 - losing claim comment is inert; cleanup is best-effort
        pass
    return False, f"lost race to {after.owner} (run {after.run_id})"


def release(client: GitHubClient, number: int, owner: str, run_id: str, outcome: str,
            pr: int | None = None) -> None:
    extra: dict[str, Any] = {"outcome": outcome}
    if pr is not None:
        extra["pr"] = pr
    client.create_comment(number, render_claim("release", owner, run_id, 0, **extra))


def heartbeat(client: GitHubClient, number: int, owner: str, run_id: str, ttl: int) -> None:
    client.create_comment(number, render_claim("heartbeat", owner, run_id, ttl))
