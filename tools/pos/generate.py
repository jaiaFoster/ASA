#!/usr/bin/env python3
"""
ASA2 POS Deterministic Generator.

Generates operational view files from POS record state.
Does NOT use an LLM. Output is fully deterministic given the same inputs.

Generated files are written to project/generated/.
Root-level files (AGENTS.md, CURRENT_STATE.md, MANAGER_INBOX.md) contain
a short pointer to their canonical generated counterparts.

This generator does NOT:
  - approve work
  - reject work
  - make merge decisions
  - make deployment decisions
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.pos.schemas import (
    REPO_ROOT,
    BOOTSTRAP_STATUS_PATH,
    GENERATED_DIR,
    GENERATED_FILE_WARNING,
    load_yaml,
)

GENERATED_HEADER = f"<!--\n{GENERATED_FILE_WARNING}-->\n\n"


def load_bootstrap_status():
    if BOOTSTRAP_STATUS_PATH.exists():
        return load_yaml(BOOTSTRAP_STATUS_PATH) or {}
    return {}


def count_records(directory: str) -> int:
    d = REPO_ROOT / directory
    if not d.is_dir():
        return 0
    return len([f for f in d.iterdir() if f.suffix in (".yaml", ".yml") and f.name != ".gitkeep"])


def generate_agents_md(status: dict) -> str:
    project = status.get("project", "ASA2")
    phase = status.get("phase", "POS_BOOTSTRAP")
    obj = status.get("current_objective", {})
    obj_id = obj.get("id", "none") if isinstance(obj, dict) else "none"
    obj_title = obj.get("title", "none") if isinstance(obj, dict) else "none"
    obj_status = obj.get("status", "none") if isinstance(obj, dict) else "none"
    automation = status.get("automation", {})
    authority = status.get("authority", {})

    return f"""{GENERATED_HEADER}# AGENTS.md — Worker Context

## Project

**Name:** {project}
**Phase:** {phase}

## Current Objective

**ID:** {obj_id}
**Title:** {obj_title}
**Status:** {obj_status}

## Current Active Assignment

None at this time.

## Canonical State Locations

- POS records: `project/work/`, `project/assignments/`, `project/results/`, `project/decisions/`, `project/reviews/`, `project/evidence/`
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

## Acceptance Authority

**{authority.get("final_acceptance", "founder_only")}**

## Automation Boundaries

- Mode: `{automation.get("mode", "advisory_and_mechanical_only")}`
- May approve: `{automation.get("may_approve", False)}`
- May reject: `{automation.get("may_reject", False)}`
- May merge: `{automation.get("may_merge", False)}`
- May deploy: `{automation.get("may_deploy", False)}`

---

> **WARNING:** This is a generated file. Do not edit manually.
> Regenerate with: `python tools/pos/generate.py`
>
> **WARNING:** Mechanical validation passing does NOT constitute approval, merge authorization, or deployment authorization.
"""


def generate_current_state_md(status: dict) -> str:
    project = status.get("project", "ASA2")
    phase = status.get("phase", "POS_BOOTSTRAP")
    s = status.get("status", "initializing")
    obj = status.get("current_objective", {})
    obj_title = obj.get("title", "none") if isinstance(obj, dict) else "none"
    next_action = status.get("next_action", {})
    next_desc = next_action.get("description", "none") if isinstance(next_action, dict) else str(next_action)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    work_count = count_records("project/work")
    blocked_count = 0  # requires status field parsing; deferred to POS-BOOTSTRAP-02
    decision_count = count_records("project/decisions")

    return f"""{GENERATED_HEADER}# CURRENT_STATE.md — Project State Summary

**Generated:** {generated_at}
**Source files:** project/BOOTSTRAP_STATUS.yaml, project/work/, project/decisions/

## Project

**Name:** {project}
**Phase:** {phase}
**Status:** {s}

## Current Objective

{obj_title}

## Work Counts

- Active work items: {work_count}
- Blocked work items: {blocked_count} *(requires POS-BOOTSTRAP-02 for accurate count)*
- Pending decisions: {decision_count}

## Last Accepted Result

None.

## Next Action

{next_desc}

---

> **WARNING:** This is a generated file. Do not edit manually.
> Regenerate with: `python tools/pos/generate.py`
"""


def generate_manager_inbox_md() -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return f"""{GENERATED_HEADER}# MANAGER_INBOX.md — Unresolved Items

**Generated:** {generated_at}

## Validation Failures

None.

## New Worker Results

None.

## Blocked Work

None.

## Pending Reviews

None.

## Pending Founder Decisions

None.

## Governance Ambiguities

None.

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

    agents_content = generate_agents_md(status)
    current_state_content = generate_current_state_md(status)
    manager_inbox_content = generate_manager_inbox_md()

    (GENERATED_DIR / "AGENTS.md").write_text(agents_content, encoding="utf-8")
    print("Generated: project/generated/AGENTS.md")

    (GENERATED_DIR / "CURRENT_STATE.md").write_text(current_state_content, encoding="utf-8")
    print("Generated: project/generated/CURRENT_STATE.md")

    (GENERATED_DIR / "MANAGER_INBOX.md").write_text(manager_inbox_content, encoding="utf-8")
    print("Generated: project/generated/MANAGER_INBOX.md")

    # Root pointers
    write_root_pointer("AGENTS.md", "project/generated/AGENTS.md")
    write_root_pointer("CURRENT_STATE.md", "project/generated/CURRENT_STATE.md")
    write_root_pointer("MANAGER_INBOX.md", "project/generated/MANAGER_INBOX.md")
    print("Updated root pointer files: AGENTS.md, CURRENT_STATE.md, MANAGER_INBOX.md")

    print("Done.")


if __name__ == "__main__":
    main()
