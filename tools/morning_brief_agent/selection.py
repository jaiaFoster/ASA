"""Deterministic selection of the next engineering issue for the worker routine.

Eligibility is label-gated: only issues a human (or the triage routine, for bounded fixes
inside existing authority) marked ``engineering-ready`` are candidates. Anything needing
architecture/Founder input, or blocked, is never auto-selected.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .claims import claim_status, owning_prs

READY = "engineering-ready"
EXCLUDE = {"needs-architect", "needs-founder", "blocked", "claude-pilot", "wontfix", "duplicate"}
DEP_RE = re.compile(r"(?i)\b(?:depends on|blocked by|requires)\s+#(\d+)")
PRIORITY = {"p0": 0, "p1": 1, "p2": 2}


def label_names(issue: dict[str, Any]) -> set[str]:
    return {(lbl["name"] if isinstance(lbl, dict) else lbl).lower() for lbl in issue.get("labels", [])}


def dependencies(issue: dict[str, Any]) -> set[int]:
    return {int(n) for n in DEP_RE.findall(issue.get("body") or "")}


def rank_candidates(
    issues: list[dict[str, Any]],
    pulls: list[dict[str, Any]],
    comments_for: Any,
    now: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (ranked eligible, skipped-with-reason) for open ready issues."""
    open_numbers = {i["number"] for i in issues if i.get("state") == "open"}
    unlocks: dict[int, int] = {}
    for issue in issues:
        if issue.get("state") == "open":
            for dep in dependencies(issue):
                unlocks[dep] = unlocks.get(dep, 0) + 1
    eligible, skipped = [], []
    for issue in issues:
        labels = label_names(issue)
        if issue.get("state") != "open" or READY not in labels:
            continue
        number = issue["number"]
        reason = None
        if labels & EXCLUDE:
            reason = f"excluded label: {sorted(labels & EXCLUDE)}"
        elif dependencies(issue) & open_numbers:
            reason = f"open dependencies: {sorted(dependencies(issue) & open_numbers)}"
        elif owning_prs(pulls, number):
            reason = f"open PR(s): {owning_prs(pulls, number)}"
        else:
            status = claim_status(comments_for(number), now)
            if status.state == "held":
                reason = f"claimed by {status.owner}"
        if reason:
            skipped.append({"issue": number, "reason": reason})
            continue
        title = (issue.get("title") or "").upper()
        priority = min((PRIORITY[p] for p in labels if p in PRIORITY), default=3)
        if "HOLD" in title or "CORRECTION" in title:
            tier = 0
        elif "bug" in labels or (priority == 0 and unlocks.get(number, 0) > 0):
            tier = 1
        else:
            tier = 2
        eligible.append({"issue": number, "title": issue.get("title"), "tier": tier,
                         "priority": priority, "unlocks": unlocks.get(number, 0)})
    eligible.sort(key=lambda c: (c["tier"], c["priority"], -c["unlocks"], c["issue"]))
    return eligible, skipped
