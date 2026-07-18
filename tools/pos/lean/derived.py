"""
Pure derived-state functions for the Lean POS reconciliation layer.

These functions take a GitHubSnapshot and produce a ReconciliationResult.
No network calls. No mutations. Fully deterministic given identical input.

Derived states are ephemeral — they are never stored as canonical records.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from tools.pos.lean.schemas import (
    DERIVED_STATES,
    RECON_AUTHORITY_UNKNOWN,
    RECON_CONFLICTING_STATE,
    RECON_INCOMPLETE_DATA,
    RECON_UNAUTHORIZED_MERGE,
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Fact:
    code: str
    source: str
    detail: str

    def to_dict(self) -> dict:
        return {"code": self.code, "source": self.source, "detail": self.detail}


@dataclasses.dataclass(frozen=True)
class Conflict:
    code: str
    source: str
    detail: str

    def to_dict(self) -> dict:
        return {"code": self.code, "source": self.source, "detail": self.detail}


@dataclasses.dataclass(frozen=True)
class Undetermined:
    code: str
    source: str
    detail: str

    def to_dict(self) -> dict:
        return {"code": self.code, "source": self.source, "detail": self.detail}


@dataclasses.dataclass
class ReconciliationResult:
    repository: str
    observed_at: str
    sources: list[str]
    derived_state: str
    facts: list[Fact]
    conflicts: list[Conflict]
    undetermined: list[Undetermined]

    def __post_init__(self) -> None:
        assert self.derived_state in DERIVED_STATES, f"Invalid derived state: {self.derived_state}"

    def to_dict(self) -> dict:
        return {
            "repository": self.repository,
            "observed_at": self.observed_at,
            "sources": sorted(self.sources),
            "derived_state": self.derived_state,
            "facts": [f.to_dict() for f in sorted(self.facts, key=lambda x: (x.code, x.source))],
            "conflicts": [c.to_dict() for c in sorted(self.conflicts, key=lambda x: (x.code, x.source))],
            "undetermined": [u.to_dict() for u in sorted(self.undetermined, key=lambda x: (x.code, x.source))],
        }


# ---------------------------------------------------------------------------
# Fact codes (stable, machine-readable)
# ---------------------------------------------------------------------------

F_ISSUE_OPEN = "F001"
F_ISSUE_CLOSED = "F002"
F_PR_DRAFT = "F003"
F_PR_OPEN = "F004"
F_PR_MERGED = "F005"
F_PR_CLOSED_UNMERGED = "F006"
F_REVIEW_APPROVED = "F007"
F_REVIEW_CHANGES_REQUESTED = "F008"
F_CHECKS_PASSING = "F009"
F_CHECKS_FAILING = "F010"
F_BLOCKER_LABEL = "F011"
F_AUTHORIZED_MERGER = "F012"

BLOCKER_LABELS = {"blocked", "do-not-merge", "needs-revision"}


# ---------------------------------------------------------------------------
# Core derivation
# ---------------------------------------------------------------------------

def derive(snapshot: "GitHubSnapshot") -> ReconciliationResult:  # type: ignore[name-defined]
    """Derive operational state from a GitHubSnapshot. Pure and deterministic."""
    facts: list[Fact] = []
    conflicts: list[Conflict] = []
    undetermined: list[Undetermined] = []
    sources: list[str] = [snapshot.repository]

    issue = snapshot.issue
    pr = snapshot.pull_request
    authority = snapshot.authority
    authorized_mergers: list[str] = authority.get("authorized_mergers") or []

    # -----------------------------------------------------------------------
    # Gather facts
    # -----------------------------------------------------------------------

    if issue is not None:
        issue_src = f"issue#{issue['number']}"
        if issue["state"] == "open":
            facts.append(Fact(F_ISSUE_OPEN, issue_src, "issue is open"))
        else:
            reason = issue.get("state_reason") or "closed"
            facts.append(Fact(F_ISSUE_CLOSED, issue_src, f"issue is closed ({reason})"))

        for label in sorted(issue.get("labels") or []):
            if label.lower() in BLOCKER_LABELS:
                facts.append(Fact(F_BLOCKER_LABEL, issue_src, f"blocker label present: {label}"))

    if pr is not None:
        pr_src = f"pr#{pr['number']}"

        if pr.get("merged"):
            merged_by = pr.get("merged_by") or ""
            merged_at = pr.get("merged_at") or ""
            facts.append(
                Fact(F_PR_MERGED, pr_src, f"merged by {merged_by} at {merged_at}")
            )
        elif pr["state"] == "closed":
            facts.append(Fact(F_PR_CLOSED_UNMERGED, pr_src, "PR closed without merge"))
        elif pr.get("draft"):
            facts.append(Fact(F_PR_DRAFT, pr_src, "PR is a draft"))
        else:
            facts.append(Fact(F_PR_OPEN, pr_src, "PR is open and not draft"))

        for review in pr.get("reviews") or []:
            rev_src = f"pr#{pr['number']}/review/{review['login']}"
            state = review["state"]
            if state == "APPROVED":
                facts.append(Fact(F_REVIEW_APPROVED, rev_src, f"{review['login']} approved"))
            elif state == "CHANGES_REQUESTED":
                facts.append(Fact(F_REVIEW_CHANGES_REQUESTED, rev_src, f"{review['login']} requested changes"))

        checks = pr.get("checks") or {}
        required = checks.get("required") or []
        statuses = checks.get("statuses") or []
        status_map = {s["context"]: s["state"] for s in statuses}

        for ctx in sorted(set(required)):
            state = status_map.get(ctx, "missing")
            if state in ("success", "neutral", "skipped"):
                facts.append(Fact(F_CHECKS_PASSING, f"pr#{pr['number']}/check/{ctx}", f"check '{ctx}' passed ({state})"))
            else:
                facts.append(Fact(F_CHECKS_FAILING, f"pr#{pr['number']}/check/{ctx}", f"check '{ctx}' failed ({state})"))

        for label in sorted(pr.get("labels") or []):
            if label.lower() in BLOCKER_LABELS:
                facts.append(Fact(F_BLOCKER_LABEL, pr_src, f"blocker label present: {label}"))

    # -----------------------------------------------------------------------
    # Derive state
    # -----------------------------------------------------------------------

    derived = _derive_state(
        issue=issue,
        pr=pr,
        facts=facts,
        authorized_mergers=authorized_mergers,
        conflicts=conflicts,
        undetermined=undetermined,
    )

    return ReconciliationResult(
        repository=snapshot.repository,
        observed_at=snapshot.observed_at,
        sources=sources,
        derived_state=derived,
        facts=facts,
        conflicts=conflicts,
        undetermined=undetermined,
    )


def _has_fact(facts: list[Fact], code: str) -> bool:
    return any(f.code == code for f in facts)


def _derive_state(
    issue: dict | None,
    pr: dict | None,
    facts: list[Fact],
    authorized_mergers: list[str],
    conflicts: list[Conflict],
    undetermined: list[Undetermined],
) -> str:
    # --- merged PR: accepted or conflict ---
    if pr is not None and pr.get("merged"):
        return _derive_from_merge(pr, authorized_mergers, conflicts, undetermined)

    # --- closed PR without merge: cancelled ---
    if pr is not None and pr["state"] == "closed" and not pr.get("merged"):
        return "cancelled"

    # --- closed issue, no active PR: cancelled ---
    if issue is not None and issue["state"] != "open" and pr is None:
        return "cancelled"

    # --- blocker label present: blocked (before other open-PR checks) ---
    if _has_fact(facts, F_BLOCKER_LABEL):
        return "blocked"

    # --- changes requested: blocked ---
    if _has_fact(facts, F_REVIEW_CHANGES_REQUESTED):
        return "blocked"

    # --- failing required checks: blocked ---
    if _has_fact(facts, F_CHECKS_FAILING):
        return "blocked"

    # --- open PR, draft: active ---
    if pr is not None and pr.get("draft") and pr["state"] == "open":
        return "active"

    # --- open PR, not draft: review ---
    if pr is not None and not pr.get("merged") and pr["state"] == "open" and not pr.get("draft"):
        return "review"

    # --- open issue, no PR: planned ---
    if issue is not None and issue["state"] == "open" and pr is None:
        return "planned"

    # --- no issue and no PR: undetermined ---
    if issue is None and pr is None:
        undetermined.append(
            Undetermined(
                RECON_INCOMPLETE_DATA,
                "snapshot",
                "neither issue nor pull_request data was provided",
            )
        )
        return "undetermined"

    # --- fallback: undetermined ---
    undetermined.append(
        Undetermined(
            RECON_INCOMPLETE_DATA,
            "snapshot",
            "insufficient data to derive a state",
        )
    )
    return "undetermined"


def _derive_from_merge(
    pr: dict,
    authorized_mergers: list[str],
    conflicts: list[Conflict],
    undetermined: list[Undetermined],
) -> str:
    merged_by = pr.get("merged_by") or ""
    pr_src = f"pr#{pr['number']}"

    if not authorized_mergers:
        # No authority configuration available
        undetermined.append(
            Undetermined(
                RECON_AUTHORITY_UNKNOWN,
                pr_src,
                f"PR merged by '{merged_by}' but no authority configuration was provided; "
                "cannot determine whether merger was authorized",
            )
        )
        return "undetermined"

    if not merged_by:
        undetermined.append(
            Undetermined(
                RECON_INCOMPLETE_DATA,
                pr_src,
                "PR is merged but merged_by is missing; cannot determine merger authority",
            )
        )
        return "undetermined"

    if merged_by in authorized_mergers:
        return "accepted"

    conflicts.append(
        Conflict(
            RECON_UNAUTHORIZED_MERGE,
            pr_src,
            f"PR merged by '{merged_by}' who is not in authorized_mergers {authorized_mergers}",
        )
    )
    return "conflict"
