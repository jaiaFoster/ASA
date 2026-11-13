"""Per-brief review ledger, derived from GitHub issues + structured comments.

GitHub is canonical. A brief's *identity* is its id (filename stem); its content hash only
detects revisions. State machine (derived, never stored separately):

    discovered -> queued -> reviewing -> reviewed -> completed
                     ^          |
                     +----------+  (stale `reviewing` record = crashed run -> queued again)

``reviewed`` requires a validated ledger record whose sha256 matches the *current* file
content and that disposes of every observation. A changed file drops back to ``queued``.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from .briefs import Brief

TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
STALE_REVIEW = timedelta(hours=12)
LEDGER_MARK = "<!-- asa-brief-ledger:v1 -->"
LEDGER_RE = re.compile(r"<!-- asa-brief-ledger:v1 -->\s*```json\s*(\{.*?\})\s*```", re.S)
INTAKE_V1 = re.compile(
    r"<!-- asa-brief-intake:(\d{4}-\d{2}-\d{2}(?:-[A-Za-z0-9]+)?)\.md sha256:([0-9a-f]{64}) -->"
)
INTAKE_V2 = re.compile(r"<!-- asa-brief-intake:v2 id=(\S+) sha256=([0-9a-f]{64}) -->")
REVISION_RE = re.compile(r"<!-- asa-brief-revision id=(\S+) sha256=([0-9a-f]{64}) -->")

SCHEMA = "asa.brief_ledger.v1"
DISPOSITIONS = {
    "EXISTING_ISSUE",
    "NEW_ISSUE",
    "EXPECTED_BEHAVIOR",
    "STALE_BRIEF_INTERPRETATION",
    "INSUFFICIENT_EVIDENCE",
    "ARCHITECTURE_ROUTED",
}
NEEDS_ISSUE = {"EXISTING_ISSUE", "NEW_ISSUE", "ARCHITECTURE_ROUTED"}


def intake_marker(brief: Brief) -> str:
    return f"<!-- asa-brief-intake:v2 id={brief.brief_id} sha256={brief.sha256} -->"


def revision_marker(brief: Brief) -> str:
    return f"<!-- asa-brief-revision id={brief.brief_id} sha256={brief.sha256} -->"


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def parse_intake(body: str | None) -> tuple[str, str] | None:
    """Return (brief_id, sha256) for a v1 or v2 intake marker, else None."""
    text = body or ""
    for pattern in (INTAKE_V2, INTAKE_V1):
        match = pattern.search(text)
        if match:
            return match.group(1), match.group(2)
    return None


def trusted(comment: dict[str, Any]) -> bool:
    return comment.get("author_association") in TRUSTED_ASSOCIATIONS


def validate_record(
    rec: dict[str, Any],
    current_sha: str,
    issue_exists: Any = None,
) -> None:
    """Raise ValueError unless ``rec`` is a complete, current ledger record."""
    if rec.get("schema") != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    for key in ("brief_id", "sha256", "state", "run_id"):
        if not rec.get(key):
            raise ValueError(f"missing {key}")
    if rec["state"] not in {"reviewing", "reviewed"}:
        raise ValueError("state must be reviewing or reviewed")
    if rec["sha256"] != current_sha:
        raise ValueError("record sha256 does not match current brief content (revised?)")
    if rec["state"] == "reviewing":
        return
    if rec.get("full_brief_read") is not True:
        raise ValueError("reviewed record requires full_brief_read: true")
    observations = rec.get("observations")
    if not isinstance(observations, list) or not observations:
        raise ValueError("reviewed record requires at least one observation")
    seen: set[str] = set()
    for obs in observations:
        oid = str(obs.get("id") or "")
        if not oid or oid in seen:
            raise ValueError(f"observation id missing or duplicated: {oid!r}")
        seen.add(oid)
        if not str(obs.get("summary") or "").strip():
            raise ValueError(f"{oid}: summary required")
        disposition = obs.get("disposition")
        if disposition not in DISPOSITIONS:
            raise ValueError(f"{oid}: invalid disposition {disposition!r}")
        if not str(obs.get("evidence") or "").strip():
            raise ValueError(f"{oid}: evidence required")
        if disposition in NEEDS_ISSUE:
            ref = obs.get("issue")
            if not isinstance(ref, int) or ref <= 0:
                raise ValueError(f"{oid}: {disposition} requires integer issue reference")
            if issue_exists is not None and not issue_exists(ref):
                raise ValueError(f"{oid}: issue #{ref} not found")


def render_record(rec: dict[str, Any]) -> str:
    return f"{LEDGER_MARK}\n```json\n{json.dumps(rec, indent=2, sort_keys=True)}\n```\n"


@dataclass
class BriefStatus:
    brief: Brief
    state: str  # discovered|queued|reviewing|reviewed|completed
    issue: int | None = None
    needs_revision_notice: bool = False
    reviewed_at: str | None = None
    observations: list[dict[str, Any]] = field(default_factory=list)


def latest_record(comments: list[dict[str, Any]]) -> tuple[dict[str, Any], datetime] | None:
    found = None
    for comment in sorted(comments, key=lambda c: c["id"]):
        if not trusted(comment):
            continue
        match = LEDGER_RE.search(comment.get("body") or "")
        if not match:
            continue
        try:
            rec = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if rec.get("schema") == SCHEMA:
            found = (rec, parse_ts(comment["created_at"]))
    return found


def known_shas(issue: dict[str, Any], comments: list[dict[str, Any]]) -> set[str]:
    shas: set[str] = set()
    intake = parse_intake(issue.get("body"))
    if intake:
        shas.add(intake[1])
    for comment in comments:
        for match in REVISION_RE.finditer(comment.get("body") or ""):
            shas.add(match.group(2))
    return shas


def derive_status(
    brief: Brief,
    issue: dict[str, Any] | None,
    comments: list[dict[str, Any]],
    now: datetime,
) -> BriefStatus:
    if issue is None:
        return BriefStatus(brief, "discovered")
    status = BriefStatus(brief, "queued", issue=issue["number"])
    if brief.sha256 not in known_shas(issue, comments):
        status.needs_revision_notice = True
    found = latest_record(comments)
    if not found:
        return status
    rec, at = found
    if rec.get("sha256") != brief.sha256:
        return status  # record is for an older revision: re-review required
    if rec["state"] == "reviewing":
        if now - at <= STALE_REVIEW:
            status.state = "reviewing"
        return status  # stale `reviewing` => crashed run => queued again
    status.state = "completed" if issue.get("state") == "closed" else "reviewed"
    status.reviewed_at = at.isoformat()
    status.observations = rec.get("observations", [])
    return status
