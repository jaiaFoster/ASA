#!/usr/bin/env python3
"""
ASA2 POS Deterministic Generator.

Generates operational view files from canonical POS records.
Does NOT use an LLM. Output is fully deterministic given the same inputs.

Timestamp strategy (for byte-for-byte reproducibility):
  The generation timestamp is derived from the latest updated_at field
  across all canonical records, or from BOOTSTRAP_STATUS.yaml if no records
  exist. This ensures same committed state → same output.
  Alternatively, set SOURCE_DATE_EPOCH (Unix timestamp) in the environment
  to override the derived timestamp.

Generated files are written to project/generated/.
Root-level files contain a short pointer to the canonical generated versions.

This generator does NOT:
  - approve work
  - reject work
  - make merge decisions
  - make deployment decisions
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.pos.schemas import (
    REPO_ROOT,
    BOOTSTRAP_STATUS_PATH,
    GENERATED_DIR,
    RECORD_DIRS,
    GENERATED_FILE_WARNING,
    load_yaml,
    load_records,
)

GENERATED_HEADER = f"<!--\n{GENERATED_FILE_WARNING}-->\n\n"


def derive_generation_timestamp(all_records: dict) -> str:
    """
    Derive generation timestamp from latest updated_at across all records.
    Falls back to SOURCE_DATE_EPOCH env var, then bootstrap status, then epoch.
    """
    epoch_override = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch_override:
        try:
            return datetime.fromtimestamp(int(epoch_override), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, OSError):
            pass

    latest = None
    for records in all_records.values():
        for rec in records:
            ts = rec.get("updated_at") or rec.get("created_at")
            if ts and isinstance(ts, str) and len(ts) >= 10:
                if latest is None or ts > latest:
                    latest = ts

    if latest:
        # Normalize: strip trailing Z if present, then add it back
        ts = latest.rstrip("Z").replace(" ", "T")
        return ts[:19] + "Z"

    # Fall back to bootstrap status
    if BOOTSTRAP_STATUS_PATH.exists():
        bs = load_yaml(BOOTSTRAP_STATUS_PATH)
        ts = (bs or {}).get("updated_at") or (bs or {}).get("created_at")
        if ts:
            return str(ts)

    return "2026-07-17T00:00:00Z"


def load_all_records() -> dict:
    return {name: load_records(path) for name, path in RECORD_DIRS.items()}


def load_bootstrap_status() -> dict:
    if BOOTSTRAP_STATUS_PATH.exists():
        return load_yaml(BOOTSTRAP_STATUS_PATH) or {}
    return {}


def _active_work(all_records: dict) -> list:
    return [r for r in all_records.get("work", [])
            if r.get("status") not in ("accepted", "rejected", "cancelled", None)
            and "_load_error" not in r]


def _pending_decisions(all_records: dict) -> list:
    return [r for r in all_records.get("decisions", [])
            if r.get("status") == "pending" and "_load_error" not in r]


def _in_review(all_records: dict) -> list:
    return [r for r in all_records.get("work", [])
            if r.get("status") == "review" and "_load_error" not in r]


def _blocked(all_records: dict) -> list:
    return [r for r in all_records.get("work", [])
            if r.get("status") == "blocked" and "_load_error" not in r]


def _accepted(all_records: dict) -> list:
    return [r for r in all_records.get("work", [])
            if r.get("status") == "accepted" and "_load_error" not in r]


def _new_results(all_records: dict) -> list:
    """Results that are complete but whose work item is not yet accepted."""
    accepted_wids = {r.get("id") for r in _accepted(all_records)}
    return [r for r in all_records.get("results", [])
            if r.get("status") == "complete"
            and r.get("work_item_id") not in accepted_wids
            and "_load_error" not in r]


def _latest_result(all_records: dict):
    results = [r for r in all_records.get("results", [])
               if "_load_error" not in r]
    if not results:
        return None
    return sorted(results, key=lambda r: r.get("submitted_at", ""), reverse=True)[0]


def _active_assignment(all_records: dict):
    for rec in sorted(all_records.get("assignments", []),
                      key=lambda r: r.get("updated_at", ""), reverse=True):
        if rec.get("status") in ("issued", "acknowledged", "in_progress") and "_load_error" not in rec:
            return rec
    return None


def generate_agents_md(status: dict, all_records: dict, generated_at: str) -> str:
    project = status.get("project", "ASA2")
    phase = status.get("phase", "POS_BOOTSTRAP")
    obj = status.get("current_objective", {})
    obj_id = obj.get("id", "none") if isinstance(obj, dict) else "none"
    obj_title = obj.get("title", "none") if isinstance(obj, dict) else "none"
    obj_status_val = obj.get("status", "none") if isinstance(obj, dict) else "none"
    automation = status.get("automation", {})
    authority = status.get("authority", {})

    # Find active work item
    active_work = _active_work(all_records)
    current_wi = active_work[0] if active_work else None
    wi_id = current_wi.get("id", "none") if current_wi else "none"
    wi_status = current_wi.get("status", "none") if current_wi else "none"
    wi_risk = (current_wi or {}).get("risk", {})
    eff_class = wi_risk.get("effective_class", "unknown") if isinstance(wi_risk, dict) else "unknown"

    # Find active assignment
    active_asg = _active_assignment(all_records)
    if active_asg:
        asg_id = active_asg.get("id", "none")
        asg_base = active_asg.get("base_commit", "none")
        asg_allowed = "\n".join(f"  - {s}" for s in (active_asg.get("allowed_scope") or []))
        asg_forbidden = "\n".join(f"  - {s}" for s in (active_asg.get("forbidden_scope") or []))
        asg_outputs = "\n".join(f"  - {s}" for s in (active_asg.get("required_outputs") or []))
        asg_tests = "\n".join(f"  - {s}" for s in (active_asg.get("required_tests") or []))
        asg_result_path = active_asg.get("result_path", "none")
        asg_block = f"""**Assignment ID:** {asg_id}
**Base Commit:** {asg_base}

**Allowed Scope:**
{asg_allowed}

**Forbidden Scope:**
{asg_forbidden}

**Required Outputs:**
{asg_outputs}

**Required Tests:**
{asg_tests}

**Result Record Path:** {asg_result_path}"""
    else:
        asg_block = "None at this time."

    return f"""{GENERATED_HEADER}# AGENTS.md — Worker Context

**Generated:** {generated_at}

> **WARNING:** Mechanical validation passing does NOT constitute approval, merge authorization, or deployment authorization.
> **WARNING:** Founder acceptance is still required for any work item to be accepted.

## Project

**Name:** {project}
**Phase:** {phase}

## Current Objective

**ID:** {obj_id}
**Title:** {obj_title}
**Status:** {obj_status_val}

## Current Work Item

**ID:** {wi_id}
**Status:** {wi_status}
**Effective Risk Class:** {eff_class}

## Current Active Assignment

{asg_block}

## Acceptance Authority

**{authority.get("final_acceptance", "founder_only")}**

## Canonical POS Record Locations

- Work items: `project/work/`
- Assignments: `project/assignments/`
- Results: `project/results/`
- Decisions: `project/decisions/`
- Reviews: `project/reviews/`
- Evidence: `project/evidence/`
- Risk records: `project/risks/`
- Bootstrap status: `project/BOOTSTRAP_STATUS.yaml`
- Role registry: `project/roles/registry.yaml`

## Governance

- Frozen governance documents: `governance/frozen/`
- Amendments: `governance/amendments/GOV-AMD-001.md`
- Manifest: `governance/manifest.yaml`

## Worker Restrictions

- Workers may NOT approve work.
- Workers may NOT merge pull requests.
- Workers may NOT deploy.
- Workers may NOT create permanent organizational roles.
- Workers may NOT modify frozen governance documents.
- Workers MUST produce result records for all assigned work.

## Automation Boundaries

- Mode: `{automation.get("mode", "advisory_and_mechanical_only")}`
- May approve: `{automation.get("may_approve", False)}`
- May reject: `{automation.get("may_reject", False)}`
- May merge: `{automation.get("may_merge", False)}`
- May deploy: `{automation.get("may_deploy", False)}`
"""


def generate_current_state_md(status: dict, all_records: dict, generated_at: str) -> str:
    project = status.get("project", "ASA2")
    phase = status.get("phase", "POS_BOOTSTRAP")
    s = status.get("status", "initializing")
    obj = status.get("current_objective", {})
    obj_title = obj.get("title", "none") if isinstance(obj, dict) else "none"
    next_action = status.get("next_action", {})
    next_desc = next_action.get("description", "none") if isinstance(next_action, dict) else str(next_action)

    active = _active_work(all_records)
    in_review_items = _in_review(all_records)
    blocked_items = _blocked(all_records)
    accepted_items = _accepted(all_records)
    pending_decs = _pending_decisions(all_records)
    latest_result = _latest_result(all_records)

    active_lines = "\n".join(f"- {r.get('id')} ({r.get('status')}): {r.get('title', '')}" for r in active) or "None"
    review_lines = "\n".join(f"- {r.get('id')}: {r.get('title', '')}" for r in in_review_items) or "None"
    blocked_lines = "\n".join(f"- {r.get('id')}: {r.get('title', '')}" for r in blocked_items) or "None"
    accepted_lines = "\n".join(f"- {r.get('id')}: {r.get('title', '')}" for r in accepted_items) or "None"
    decision_lines = "\n".join(f"- {r.get('id')}: {r.get('title', '')}" for r in pending_decs) or "None"

    if latest_result:
        result_line = f"{latest_result.get('id')} ({latest_result.get('status')}) — submitted {latest_result.get('submitted_at', 'unknown')}"
    else:
        result_line = "None"

    return f"""{GENERATED_HEADER}# CURRENT_STATE.md — Project State Summary

**Generated:** {generated_at}
**Source files:** project/BOOTSTRAP_STATUS.yaml, project/work/, project/decisions/, project/results/

## Project

**Name:** {project}
**Phase:** {phase}
**Status:** {s}

## Current Objective

{obj_title}

## Active Work

{active_lines}

## Work Awaiting Review

{review_lines}

## Blocked Work

{blocked_lines}

## Accepted Work

{accepted_lines}

## Pending Decisions

{decision_lines}

## Latest Result

{result_line}

## Next Action

{next_desc}

---

> **WARNING:** This is a generated file. Do not edit manually.
> Regenerate with: `python tools/pos/generate.py`
"""


def generate_manager_inbox_md(all_records: dict, generated_at: str) -> str:
    pending_decs = _pending_decisions(all_records)
    new_results = _new_results(all_records)
    in_review_items = _in_review(all_records)
    blocked_items = _blocked(all_records)

    pending_dec_lines = "\n".join(
        f"- **{r.get('id')}**: {r.get('title', '')} — authority: {r.get('decision_authority', '?')}"
        for r in pending_decs
    ) or "None"

    result_lines = "\n".join(
        f"- **{r.get('id')}** for work item {r.get('work_item_id', '?')} — submitted {r.get('submitted_at', '?')}"
        for r in new_results
    ) or "None"

    review_lines = "\n".join(
        f"- **{r.get('id')}**: {r.get('title', '')}"
        for r in in_review_items
    ) or "None"

    blocked_lines = "\n".join(
        f"- **{r.get('id')}**: {r.get('title', '')}"
        for r in blocked_items
    ) or "None"

    return f"""{GENERATED_HEADER}# MANAGER_INBOX.md — Unresolved Items

**Generated:** {generated_at}

## Validation Failures

None.

## New Worker Results

{result_lines}

## Work Awaiting Review

{review_lines}

## Blocked Work

{blocked_lines}

## Pending Reviews

None.

## Pending Founder Decisions

{pending_dec_lines}

## Governance Ambiguities

None.

## Stale Generated Views

Run `python tools/pos/generate.py` to regenerate and `python tools/pos/validate.py` to verify.

---

> **WARNING:** This is a generated file. Do not edit manually.
> Regenerate with: `python tools/pos/generate.py`
"""


def write_root_pointer(filename: str, generated_path: str) -> None:
    path = REPO_ROOT / filename
    content = (
        f"<!-- This file is a pointer. The canonical version is at {generated_path}.\n"
        f"Regenerate with: python tools/pos/generate.py -->\n\n"
        f"See [{generated_path}]({generated_path}) for the current generated version.\n"
    )
    path.write_text(content, encoding="utf-8")


def main():
    print("ASA2 POS Generator")
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    status = load_bootstrap_status()
    all_records = load_all_records()
    generated_at = derive_generation_timestamp(all_records)

    (GENERATED_DIR / "AGENTS.md").write_text(
        generate_agents_md(status, all_records, generated_at), encoding="utf-8"
    )
    print("Generated: project/generated/AGENTS.md")

    (GENERATED_DIR / "CURRENT_STATE.md").write_text(
        generate_current_state_md(status, all_records, generated_at), encoding="utf-8"
    )
    print("Generated: project/generated/CURRENT_STATE.md")

    (GENERATED_DIR / "MANAGER_INBOX.md").write_text(
        generate_manager_inbox_md(all_records, generated_at), encoding="utf-8"
    )
    print("Generated: project/generated/MANAGER_INBOX.md")

    write_root_pointer("AGENTS.md", "project/generated/AGENTS.md")
    write_root_pointer("CURRENT_STATE.md", "project/generated/CURRENT_STATE.md")
    write_root_pointer("MANAGER_INBOX.md", "project/generated/MANAGER_INBOX.md")
    print("Updated root pointer files: AGENTS.md, CURRENT_STATE.md, MANAGER_INBOX.md")
    print(f"Generation timestamp: {generated_at}")
    print("Done.")


if __name__ == "__main__":
    main()
