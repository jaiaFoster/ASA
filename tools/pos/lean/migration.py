"""
Lean POS migration assessment — pure analysis functions.

No I/O beyond reading the repository. No network. No file writes.
All public functions are deterministic given identical repository state.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import NamedTuple

from tools.pos.lean.schemas import (
    REPO_ROOT,
    MIGR_GOVERNANCE_CONFLICT,
    MIGR_CANONICAL_DATA_GAP,
    MIGR_CI_DEPENDENCY,
    MIGR_TEST_DEPENDENCY,
    MIGR_AUTHORITY_UNDETERMINED,
    LEAN_MIGRATION_DIR,
    load_yaml,
)

# ---------------------------------------------------------------------------
# Stable path definitions
# ---------------------------------------------------------------------------

LEGACY_SCHEMA_DIR = REPO_ROOT / "project" / "schemas"
LEGACY_GENERATED_DIR = REPO_ROOT / "project" / "generated"
LEGACY_ARCHIVE_ROOT = REPO_ROOT / "project" / "lean" / "archive" / "legacy"
LEGACY_RECORD_DIRS = {
    "work": LEGACY_ARCHIVE_ROOT / "work",
    "assignments": LEGACY_ARCHIVE_ROOT / "assignments",
    "results": LEGACY_ARCHIVE_ROOT / "results",
    "decisions": LEGACY_ARCHIVE_ROOT / "decisions",
    "reviews": LEGACY_ARCHIVE_ROOT / "reviews",
    "evidence": LEGACY_ARCHIVE_ROOT / "evidence",
    "risks": LEGACY_ARCHIVE_ROOT / "risks",
}
LEGACY_TOOL_FILES = [
    "tools/pos/validate.py",
    "tools/pos/generate.py",
    "tools/pos/schemas.py",
    "tools/pos/transitions.py",
    "tools/pos/requirements.txt",
    "tools/pos/README.md",
]
LEGACY_GENERATED_FILES = [
    "project/generated/AGENTS.md",
    "project/generated/CURRENT_STATE.md",
    "project/generated/MANAGER_INBOX.md",
]
ROOT_POINTER_FILES = ["AGENTS.md", "CURRENT_STATE.md"]
LEGACY_TEST_FILES = [
    "tests/pos/test_repository_bootstrap.py",
    "tests/pos/test_role_bootstrap.py",
]
LEAN_PATHS = {
    "project/schemas/lean",
    "project/lean",
    "tools/pos/lean",
    "tests/pos/lean",
}

# ---------------------------------------------------------------------------
# Required capabilities (ordered, stable)
# ---------------------------------------------------------------------------

REQUIRED_CAPABILITIES = [
    "structural_validation",
    "deterministic_validation",
    "github_reconciliation",
    "work_bounding",
    "scope_protection",
    "risk_class_recording",
    "risk_floor_enforcement",
    "authority_awareness",
    "acceptance_detection",
    "governance_conflict_reporting",
    "generated_project_orientation",
    "generated_worker_context",
    "exceptional_coordination",
    "trial_rule_tracking",
    "audit_traceability",
    "migration_reversibility",
    "offline_operation",
    "ci_validation",
    "historical_record_preservation",
    "frozen_governance_integrity",
    "entrypoint_integrity",
    "branch_freshness_and_conflict_preflight",
]


# ---------------------------------------------------------------------------
# Inventory building
# ---------------------------------------------------------------------------

def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _is_lean(rel_path: str) -> bool:
    for prefix in LEAN_PATHS:
        if rel_path.startswith(prefix):
            return True
    return False


def _list_records(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(f for f in directory.iterdir()
                  if f.suffix in (".yaml", ".yml") and f.name != ".gitkeep")


def _try_load(path: Path) -> dict | None:
    try:
        return load_yaml(path) or {}
    except Exception:
        return None


def _canonical_data_classification(category: str, path_rel: str) -> str:
    """Return 'unique' or 'github_derivable' or 'generated'."""
    if category == "generated_view" or category == "root_pointer":
        return "generated"
    if category == "schema":
        return "unique"
    if category == "tool":
        return "unique"
    if category == "test":
        return "unique"
    if category == "workflow":
        return "unique"
    if category in ("work_record", "assignment_record", "risk_record"):
        # Contains scope, acceptance criteria, risk properties not in GitHub
        return "unique"
    if category in ("result_record", "review_record", "evidence_record"):
        # Content largely duplicates PR discussion and commit records
        return "github_derivable"
    if category == "decision_record":
        # Pending decisions (null decision field) are unique; decided ones duplicate PR/GitHub
        return "unique"
    if category == "root_config":
        return "unique"
    return "unique"


def _github_derivable(category: str, rec: dict | None) -> str:
    if category == "generated_view":
        return "yes — content derived from POS records and GitHub state"
    if category == "root_pointer":
        return "yes — pointer content derivable from generated view path"
    if category == "result_record" and rec:
        return "partial — test counts and file lists are GitHub-visible; free-text summaries are not"
    if category == "review_record" and rec:
        return "partial — findings may duplicate PR review comments"
    if category == "evidence_record":
        return "partial — test output reproducible from git; manual observations are unique"
    return "no"


def _proposed_disposition(category: str, path_rel: str, rec: dict | None) -> str:
    if category in ("schema", "tool", "test", "workflow", "root_config", "work_record",
                    "assignment_record", "risk_record", "decision_record"):
        return "archive"
    if category in ("generated_view", "root_pointer"):
        return "delete_after_cutover"
    if category in ("result_record", "review_record", "evidence_record"):
        return "archive"
    return "unresolved"


def build_legacy_inventory(repo_root: Path, generated_at: str) -> dict:
    """Scan legacy POS paths and build the machine-readable inventory."""

    artifacts: list[dict] = []
    schemas_list: list[dict] = []
    tools_list: list[dict] = []
    generated_views: list[dict] = []
    tests_list: list[dict] = []
    workflows_list: list[dict] = []
    root_pointers: list[dict] = []

    # ---- Schemas (legacy only) ----
    _legacy_schema_names = [
        "assignment.schema.yaml", "decision.schema.yaml", "evidence.schema.yaml",
        "review.schema.yaml", "risk-record.schema.yaml", "work-item.schema.yaml",
        "worker-result.schema.yaml",
    ]
    for sname in _legacy_schema_names:
        sf = repo_root / "project" / "schemas" / sname
        rel = f"project/schemas/{sname}"
        status = "active" if sf.exists() else "deleted"
        entry = {
            "path": rel,
            "category": "schema",
            "status": status,
            "referenced_by": ["tools/pos/validate.py", "tools/pos/schemas.py",
                              "tests/pos/test_repository_bootstrap.py"],
            "references": [],
            "canonical_data": "yes — schema definitions are not in GitHub",
            "github_derivable_data": "no",
            "lean_replacement": _lean_schema_replacement(sname),
            "proposed_disposition": "deleted" if status == "deleted" else "archive",
            "removal_blockers": [] if status == "deleted" else ["BLKR-003"],
        }
        schemas_list.append(entry)
        artifacts.append(entry)

    # ---- Canonical record directories ----
    for dir_key, dir_path in sorted(LEGACY_RECORD_DIRS.items()):
        records = _list_records(dir_path)
        for rp in records:
            rel = _rel(rp)
            rec = _try_load(rp)
            cat = _category_for_dir(dir_key)
            entry = _build_record_entry(rel, cat, rec, dir_key)
            artifacts.append(entry)

    # ---- Tools ----
    for tool_rel in LEGACY_TOOL_FILES:
        tp = repo_root / tool_rel
        status = "active" if tp.exists() else "deleted"
        entry = {
            "path": tool_rel,
            "category": "tool",
            "status": status,
            "referenced_by": [".github/workflows/validate-pos.yml",
                              "tests/pos/test_repository_bootstrap.py"],
            "references": _tool_references(tool_rel),
            "canonical_data": "yes — tool logic not stored in GitHub",
            "github_derivable_data": "no",
            "lean_replacement": _lean_tool_replacement(tool_rel),
            "proposed_disposition": "deleted" if status == "deleted" else "delete_after_cutover",
            "removal_blockers": [] if status == "deleted" else _tool_blockers(tool_rel),
        }
        tools_list.append(entry)
        artifacts.append(entry)

    # ---- Generated views ----
    for gf_rel in LEGACY_GENERATED_FILES:
        gp = repo_root / gf_rel
        status = "stale_or_current" if gp.exists() else "deleted"
        entry = {
            "path": gf_rel,
            "category": "generated_view",
            "status": status,
            "referenced_by": ROOT_POINTER_FILES + [".github/workflows/validate-pos.yml"],
            "references": ["project/BOOTSTRAP_STATUS.yaml", "project/work/",
                           "project/assignments/", "project/results/", "project/decisions/"],
            "canonical_data": "no — generated from canonical records",
            "github_derivable_data": "yes — content derived from POS records and GitHub state",
            "lean_replacement": _lean_generated_replacement(gf_rel),
            "proposed_disposition": "deleted" if status == "deleted" else "delete_after_cutover",
            "removal_blockers": [] if status == "deleted" else ["BLKR-003", "BLKR-005"],
        }
        generated_views.append(entry)
        artifacts.append(entry)

    # ---- Tests ----
    for tf_rel in LEGACY_TEST_FILES:
        tp = repo_root / tf_rel
        status = "active" if tp.exists() else "deleted"
        entry = {
            "path": tf_rel,
            "category": "test",
            "status": status,
            "referenced_by": [".github/workflows/validate-pos.yml"],
            "references": ["tools/pos/validate.py", "tools/pos/generate.py",
                          "tools/pos/schemas.py", "governance/manifest.yaml"],
            "canonical_data": "yes — test logic encoding governance requirements",
            "github_derivable_data": "no",
            "lean_replacement": _lean_test_replacement(tf_rel),
            "proposed_disposition": "deleted" if status == "deleted" else "archive",
            "removal_blockers": [] if status == "deleted" else ["BLKR-005"],
        }
        tests_list.append(entry)
        artifacts.append(entry)

    # ---- CI Workflows ----
    wf_rel = ".github/workflows/validate-pos.yml"
    wp = repo_root / wf_rel
    if wp.exists():
        entry = {
            "path": wf_rel,
            "category": "workflow",
            "status": "active",
            "referenced_by": ["GitHub Actions"],
            "references": ["tools/pos/validate.py", "tools/pos/generate.py",
                           "tests/pos/", "project/generated/", "AGENTS.md",
                           "CURRENT_STATE.md", "MANAGER_INBOX.md"],
            "canonical_data": "yes — CI behavior definition",
            "github_derivable_data": "no",
            "lean_replacement": "new_workflow_step — lean validator + lean tests (CUTOVER-03)",
            "proposed_disposition": "retain",
            "removal_blockers": ["BLKR-003"],
        }
        workflows_list.append(entry)
        artifacts.append(entry)

    # ---- Root pointers ----
    for rp_name in ROOT_POINTER_FILES:
        rp = repo_root / rp_name
        if not rp.exists():
            continue
        entry = {
            "path": rp_name,
            "category": "root_pointer",
            "status": "active",
            "referenced_by": ["GitHub UI", "AI worker initial context"],
            "references": [f"project/generated/{rp_name}"],
            "canonical_data": "no — pointer only",
            "github_derivable_data": "yes — pointer content derivable from generated view path",
            "lean_replacement": _lean_root_pointer_replacement(rp_name),
            "proposed_disposition": "replace_with_pointer",
            "removal_blockers": ["BLKR-003"],
        }
        root_pointers.append(entry)
        artifacts.append(entry)

    # ---- Root config files ----
    for rc_name in ["project/lean/archive/legacy/BOOTSTRAP_STATUS.yaml",
                    "project/roles/registry.yaml", "project/README.md"]:
        rcp = repo_root / rc_name
        if not rcp.exists():
            continue
        entry = {
            "path": rc_name,
            "category": "root_config",
            "status": "active",
            "referenced_by": ["tools/pos/schemas.py", "tools/pos/validate.py",
                              "tools/pos/generate.py"],
            "references": [],
            "canonical_data": "yes — project operational state and role registry",
            "github_derivable_data": "partial — phase/status derivable from git; role definitions are unique",
            "lean_replacement": _lean_root_config_replacement(rc_name),
            "proposed_disposition": "retain",
            "removal_blockers": [],
        }
        artifacts.append(entry)

    directories: list[dict] = [
        {
            "path": "project/schemas/",
            "contents": [s["path"] for s in schemas_list],
            "consumer": "tools/pos/validate.py",
            "lean_equivalent": "project/schemas/lean/",
            "proposed_disposition": "archive",
        },
        {
            "path": "project/lean/archive/legacy/work/",
            "contents": [a["path"] for a in artifacts if a.get("category") == "work_record"],
            "consumer": "historical — no active consumers (CUTOVER-04 complete)",
            "lean_equivalent": "project/lean/handoffs/ (worker-handoff records)",
            "proposed_disposition": "archived",
        },
        {
            "path": "project/generated/",
            "contents": [g["path"] for g in generated_views],
            "consumer": ".github/workflows/validate-pos.yml, root pointer files",
            "lean_equivalent": "project/lean/generated/",
            "proposed_disposition": "delete_after_cutover",
        },
    ]

    return {
        "generated_at": generated_at,
        "artifacts": artifacts,
        "directories": directories,
        "schemas": schemas_list,
        "tools": tools_list,
        "generated_views": generated_views,
        "tests": tests_list,
        "workflows": workflows_list,
        "root_pointers": root_pointers,
    }


def _category_for_dir(dir_key: str) -> str:
    return {
        "work": "work_record",
        "assignments": "assignment_record",
        "results": "result_record",
        "decisions": "decision_record",
        "reviews": "review_record",
        "evidence": "evidence_record",
        "risks": "risk_record",
    }.get(dir_key, "unknown_record")


def _build_record_entry(rel: str, category: str, rec: dict | None, dir_key: str) -> dict:
    rec = rec or {}
    rec_id = rec.get("id", "")
    status = rec.get("status", "unknown")
    canonical = _canonical_data_classification(category, rel)
    gh_deriv = _github_derivable(category, rec)
    disposition = _proposed_disposition(category, rel, rec)
    # Active records (not accepted/cancelled/superseded) with no GitHub mapping are blockers
    active_statuses = {"review", "pending", "in_progress", "assigned", "blocked",
                       "proposed", "ready", "requested", "draft", "issued",
                       "acknowledged", "complete", "confirmed", "classified"}
    is_active = status in active_statuses
    blockers = []
    if is_active and category in ("work_record", "decision_record"):
        blockers.append("BLKR-004")
    return {
        "path": rel,
        "category": category,
        "status": status,
        "record_id": rec_id,
        "referenced_by": _record_referenced_by(category, rec_id),
        "references": _record_references(rec),
        "canonical_data": canonical,
        "github_derivable_data": gh_deriv,
        "lean_replacement": _lean_record_replacement(category, rec, dir_key),
        "proposed_disposition": disposition,
        "removal_blockers": blockers,
    }


def _record_referenced_by(category: str, rec_id: str) -> list[str]:
    refs = {
        "work_record": ["tools/pos/generate.py", "tools/pos/validate.py"],
        "assignment_record": ["project/work/", "tools/pos/validate.py"],
        "result_record": ["project/assignments/", "tools/pos/validate.py",
                         "tools/pos/generate.py"],
        "decision_record": ["project/work/", "tools/pos/generate.py"],
        "review_record": ["project/work/", "tools/pos/validate.py"],
        "evidence_record": ["project/reviews/", "tools/pos/validate.py"],
        "risk_record": ["project/work/", "project/assignments/",
                        "tools/pos/validate.py"],
    }
    return refs.get(category, [])


def _record_references(rec: dict) -> list[str]:
    refs: set[str] = set()
    for key in ("work_item_id", "assignment_id", "risk_record", "subject_id"):
        v = rec.get(key)
        if v:
            refs.add(str(v))
    for key in ("assignments", "results", "reviews", "evidence", "decisions",
                "evidence_reviewed", "affected_records"):
        for v in (rec.get(key) or []):
            refs.add(str(v))
    return sorted(refs)


def _lean_schema_replacement(schema_name: str) -> str:
    mapping = {
        "work-item.schema.yaml": "project/schemas/lean/worker-handoff.schema.yaml",
        "assignment.schema.yaml": "project/schemas/lean/worker-handoff.schema.yaml",
        "worker-result.schema.yaml": "project/schemas/lean/worker-handoff.schema.yaml (deliver field)",
        "decision.schema.yaml": "github_issue_or_pr (GitHub is canonical for decisions)",
        "review.schema.yaml": "github_pr_review (GitHub is canonical for reviews)",
        "evidence.schema.yaml": "github_pr_checks (GitHub is canonical for CI evidence)",
        "risk-record.schema.yaml": "project/schemas/lean/worker-handoff.schema.yaml (risk field)",
    }
    return mapping.get(schema_name, "unresolved")


def _lean_tool_replacement(tool_rel: str) -> str:
    return {
        "tools/pos/validate.py": "tools/pos/lean/validate.py",
        "tools/pos/generate.py": "tools/pos/lean/generate.py",
        "tools/pos/schemas.py": "tools/pos/lean/schemas.py",
        "tools/pos/transitions.py": "none (lean uses GitHub state transitions via derived.py)",
        "tools/pos/requirements.txt": "retain (shared; lean tools use same deps)",
        "tools/pos/README.md": "none (retire; lean tools are self-documenting via --help)",
    }.get(tool_rel, "unresolved")


def _lean_generated_replacement(gf_rel: str) -> str:
    return {
        "project/generated/AGENTS.md": "project/lean/generated/WORKER_CONTEXT.yaml",
        "project/generated/CURRENT_STATE.md": "project/lean/generated/CURRENT_STATE.md",
        "project/generated/MANAGER_INBOX.md": "project/lean/generated/CURRENT_STATE.md (blockers section)",
    }.get(gf_rel, "unresolved")


def _lean_test_replacement(tf_rel: str) -> str:
    return {
        "tests/pos/test_repository_bootstrap.py":
            "tests/pos/lean/test_lean_validator.py + tests/pos/lean/test_reconcile.py "
            "+ tests/pos/lean/test_generate.py + tests/pos/lean/test_migration_assessment.py "
            "+ tests/pos/lean/test_integrity.py (manifest integrity check — LEAN-POS-05)",
        "tests/pos/test_role_bootstrap.py": "unresolved — role bootstrap may not have lean equivalent",
    }.get(tf_rel, "unresolved")


def _lean_root_pointer_replacement(rp_name: str) -> str:
    return {
        "AGENTS.md": "pointer to project/lean/generated/WORKER_CONTEXT.yaml",
        "CURRENT_STATE.md": "pointer to project/lean/generated/CURRENT_STATE.md",
        "MANAGER_INBOX.md": "pointer to project/lean/generated/CURRENT_STATE.md (blockers section)",
    }.get(rp_name, "unresolved")


def _lean_root_config_replacement(rc_name: str) -> str:
    return {
        "project/lean/archive/legacy/BOOTSTRAP_STATUS.yaml":
            "project/lean/state/project-state.yaml (archived; lean state is canonical)",
        "project/roles/registry.yaml": "retain (roles are independent of POS system)",
        "project/README.md": "retain (repository entry point)",
    }.get(rc_name, "retain")


def _lean_record_replacement(category: str, rec: dict, dir_key: str) -> str:
    gh_derivable_categories = ("result_record", "review_record", "evidence_record")
    if category in gh_derivable_categories:
        return "archive_in_place — content largely derivable from GitHub PR history"
    if category == "work_record":
        return ("project/lean/handoffs/ (worker-handoff record for active items); "
                "archive for accepted items")
    if category == "assignment_record":
        return ("project/lean/handoffs/ (scope/lock/accept fields replace assignment); "
                "archive for historical items")
    if category == "decision_record":
        status = rec.get("status", "")
        if status == "pending":
            return ("founder_decision_required before archiving — "
                    "open decision has no lean equivalent (BLKR-004)")
        return "archive_in_place"
    if category == "risk_record":
        return "project/lean/handoffs/ (risk field in worker-handoff)"
    return "archive_in_place"


def _tool_references(tool_rel: str) -> list[str]:
    return {
        "tools/pos/validate.py": ["project/schemas/", "governance/manifest.yaml",
                                  "project/BOOTSTRAP_STATUS.yaml"],
        "tools/pos/generate.py": ["project/BOOTSTRAP_STATUS.yaml", "project/work/",
                                  "project/assignments/", "project/results/",
                                  "project/decisions/"],
        "tools/pos/schemas.py": ["governance/manifest.yaml"],
        "tools/pos/transitions.py": [],
        "tools/pos/requirements.txt": [],
        "tools/pos/README.md": [],
    }.get(tool_rel, [])


def _tool_blockers(tool_rel: str) -> list[str]:
    if tool_rel in ("tools/pos/validate.py", "tools/pos/generate.py",
                    "tools/pos/schemas.py", "tools/pos/transitions.py"):
        return ["BLKR-003"]
    return []


# ---------------------------------------------------------------------------
# Capability map
# ---------------------------------------------------------------------------

def build_capability_map(generated_at: str) -> dict:
    """Return static capability-map dict. All reasoning is encoded here."""
    capabilities = [
        {
            "id": "structural_validation",
            "description": "Validate canonical records against JSON Schema",
            "legacy_implementation": "tools/pos/validate.py (Phase 1–3)",
            "status": "replaced",
            "lean_implementation": "tools/pos/lean/validate.py (all 4 lean schemas)",
            "gap": None,
            "blocker": None,
        },
        {
            "id": "deterministic_validation",
            "description": "Validation output is identical for identical input",
            "legacy_implementation": "tools/pos/validate.py (stateless checks)",
            "status": "replaced",
            "lean_implementation": "tools/pos/lean/validate.py (offline, no clock dependency)",
            "gap": None,
            "blocker": None,
        },
        {
            "id": "github_reconciliation",
            "description": "Derive project operational state from GitHub API snapshot",
            "legacy_implementation": "none — legacy POS does not query GitHub",
            "status": "replaced",
            "lean_implementation": ("tools/pos/lean/reconcile.py + tools/pos/lean/derived.py "
                                    "(8 derived states, F001–F012 facts)"),
            "gap": None,
            "blocker": None,
        },
        {
            "id": "work_bounding",
            "description": "Define and enforce the scope of a unit of work",
            "legacy_implementation": "assignment.schema.yaml (allowed_scope/forbidden_scope fields)",
            "status": "replaced",
            "lean_implementation": ("project/schemas/lean/worker-handoff.schema.yaml "
                                    "(scope + lock fields with minItems:1)"),
            "gap": None,
            "blocker": None,
        },
        {
            "id": "scope_protection",
            "description": "Record which paths must not be modified",
            "legacy_implementation": "assignment.yaml forbidden_scope field",
            "status": "replaced",
            "lean_implementation": "worker-handoff.schema.yaml lock field (minItems:1)",
            "gap": None,
            "blocker": None,
        },
        {
            "id": "risk_class_recording",
            "description": "Record and expose the risk class of a unit of work",
            "legacy_implementation": "work-item.schema.yaml + risk-record.schema.yaml",
            "status": "replaced",
            "lean_implementation": "worker-handoff.schema.yaml risk field (enum R0–R5)",
            "gap": None,
            "blocker": None,
        },
        {
            "id": "risk_floor_enforcement",
            "description": ("Apply RISK-001 deterministic classification algorithm from "
                            "declared properties; effective_class >= deterministic_class"),
            "legacy_implementation": ("tools/pos/validate.py check_risk_records(); "
                                      "risk-record.schema.yaml with declared_properties"),
            "status": "partially_replaced",
            "lean_implementation": ("worker-handoff.schema.yaml records risk class manually; "
                                    "lean validate.py checks enum only; RISK-001 §9 property-to-class "
                                    "algorithm not implemented in lean"),
            "gap": ("Lean has no equivalent of the RISK-001 §9.2 deterministic classification "
                    "from declared_properties. Risk class is manually declared, not derived. "
                    "Gap accepted — Founder approved github_satisfies_pos_record_requirement "
                    "(BLKR-001 resolved)."),
            "blocker": None,
        },
        {
            "id": "authority_awareness",
            "description": "Know which actors are authorized to approve/merge",
            "legacy_implementation": "project/BOOTSTRAP_STATUS.yaml authority block",
            "status": "replaced",
            "lean_implementation": ("tools/pos/lean/derived.py (authorized_mergers from fixture); "
                                    "configurable per reconciliation snapshot"),
            "gap": None,
            "blocker": None,
        },
        {
            "id": "acceptance_detection",
            "description": "Detect when a unit of work has been accepted",
            "legacy_implementation": "work_item.status=accepted + ASA2-DECISION-001 decided",
            "status": "replaced",
            "lean_implementation": ("tools/pos/lean/derived.py: F005 (merged by authorized) "
                                    "+ F007 (approved by authorized) → state=accepted"),
            "gap": None,
            "blocker": None,
        },
        {
            "id": "governance_conflict_reporting",
            "description": "Report governance violations without resolving them",
            "legacy_implementation": "tools/pos/validate.py FAIL outputs (non-authority language)",
            "status": "replaced",
            "lean_implementation": ("tools/pos/lean/derived.py: G005 (unauthorized merge), "
                                    "G006 (conflicting state) → state=conflict; "
                                    "tools/pos/lean/validate.py: E001–E010 error codes"),
            "gap": None,
            "blocker": None,
        },
        {
            "id": "generated_project_orientation",
            "description": "Produce a human-readable current project state view",
            "legacy_implementation": "tools/pos/generate.py → project/generated/CURRENT_STATE.md",
            "status": "replaced",
            "lean_implementation": ("tools/pos/lean/generate.py current-state → "
                                    "project/lean/generated/CURRENT_STATE.md"),
            "gap": None,
            "blocker": None,
        },
        {
            "id": "generated_worker_context",
            "description": "Produce a bounded, token-budgeted worker context package",
            "legacy_implementation": "tools/pos/generate.py → project/generated/AGENTS.md",
            "status": "replaced_with_different_mechanism",
            "lean_implementation": ("tools/pos/lean/generate.py worker-context → "
                                    "project/lean/generated/WORKER_CONTEXT.yaml "
                                    "(YAML structured, token-budgeted; legacy was Markdown)"),
            "gap": None,
            "blocker": None,
        },
        {
            "id": "exceptional_coordination",
            "description": "Track work requiring coordination beyond a single PR",
            "legacy_implementation": "none — legacy POS has no exceptional-work record type",
            "status": "replaced",
            "lean_implementation": ("project/schemas/lean/exceptional-work.schema.yaml "
                                    "(trigger enum, open/resolved/cancelled states)"),
            "gap": None,
            "blocker": None,
        },
        {
            "id": "trial_rule_tracking",
            "description": "Track active governance trial rules",
            "legacy_implementation": "none — legacy POS has no trial-rule record type",
            "status": "replaced",
            "lean_implementation": ("project/schemas/lean/trial-rule.schema.yaml "
                                    "(active_trial/adopted/withdrawn/superseded states)"),
            "gap": None,
            "blocker": None,
        },
        {
            "id": "audit_traceability",
            "description": ("Produce explicit records of evidence, reviews, and decisions "
                            "for each unit of work"),
            "legacy_implementation": ("project/evidence/, project/reviews/, project/decisions/ "
                                      "with cross-referenced records"),
            "status": "partially_replaced",
            "lean_implementation": ("GitHub PR reviews + CI check runs serve as audit trail; "
                                    "derived.py surfaces review/check facts (F006–F009); "
                                    "no lean equivalent of explicit evidence/ or review/ records"),
            "gap": ("Lean relies on GitHub PR audit trail; no offline audit record equivalent. "
                    "Gap accepted — Founder approved github_satisfies_pos_record_requirement "
                    "(BLKR-001 resolved). Confirmed in LEAN-POS-06: project state plus GitHub "
                    "and git history preserve required traceability without legacy lifecycle duplication."),
            "blocker": None,
        },
        {
            "id": "migration_reversibility",
            "description": "Ability to return to dual-POS or legacy-only operation",
            "legacy_implementation": "N/A — pre-migration",
            "status": "partially_replaced",
            "lean_implementation": ("Cutover plan includes rollback steps for each phase; "
                                    "git history preserves all legacy artifacts; "
                                    "CUTOVER-01 through CUTOVER-05 complete; "
                                    "canonical lean state exists at project/lean/state/project-state.yaml; "
                                    "archived records recoverable via git or archive path; "
                                    "legacy runtime deleted in LEAN-POS-10 (CUTOVER-05)"),
            "gap": ("CUTOVER-06 (verify_lean_only_repository) not yet complete"),
            "blocker": None,
        },
        {
            "id": "offline_operation",
            "description": "All validation operates without network access",
            "legacy_implementation": "tools/pos/validate.py (no network calls)",
            "status": "replaced",
            "lean_implementation": ("tools/pos/lean/validate.py (proven offline: "
                                    "test_validate_does_not_import_github)"),
            "gap": None,
            "blocker": None,
        },
        {
            "id": "ci_validation",
            "description": "CI checks are run on every PR touching POS paths",
            "legacy_implementation": (".github/workflows/validate-pos.yml: "
                                      "pytest tests/pos, tools/pos/validate.py, "
                                      "tools/pos/generate.py, git-diff check"),
            "status": "replaced",
            "lean_implementation": ("CI runs: pytest tests/pos (includes all lean tests); "
                                    "tools/pos/lean/check_integrity.py; "
                                    "tools/pos/lean/validate.py (project_state schema); "
                                    "tools/pos/lean/generate.py (deterministic, fixed timestamp); "
                                    "git-diff check on CURRENT_STATE.md only. "
                                    "Legacy validator and generator removed from CI in LEAN-POS-08."),
            "gap": None,
            "blocker": None,
        },
        {
            "id": "historical_record_preservation",
            "description": "Preserve access to pre-lean canonical work, assignment, and decision records",
            "legacy_implementation": ("project/work/, project/assignments/, project/results/, "
                                      "project/decisions/, project/reviews/, project/evidence/, "
                                      "project/risks/, project/BOOTSTRAP_STATUS.yaml"),
            "status": "replaced",
            "lean_implementation": ("project/lean/archive/legacy/ — byte-preserved historical records; "
                                    "git history preserves original paths and content. "
                                    "Archived in LEAN-POS-09 (CUTOVER-04)."),
            "gap": None,
            "blocker": None,
        },
        {
            "id": "frozen_governance_integrity",
            "description": "Verify frozen governance files match manifest SHA-256 hashes",
            "legacy_implementation": ("tools/pos/validate.py check_frozen_files(); "
                                      "tests/pos/test_repository_bootstrap.py "
                                      "test_frozen_hashes_match_manifest"),
            "status": "replaced",
            "lean_implementation": ("tools/pos/lean/check_integrity.py (I001-I005 error codes, "
                                    "stdlib only); CI step 'Check frozen governance integrity' added; "
                                    "19 tests in tests/pos/lean/test_integrity.py. Added in LEAN-POS-05."),
            "gap": None,
            "blocker": None,
        },
        {
            "id": "entrypoint_integrity",
            "description": "Guarantee root AGENTS.md and CURRENT_STATE.md stay Lean-only after every push",
            "legacy_implementation": "N/A — regression first observed in LEAN-POS-09",
            "status": "replaced",
            "lean_implementation": ("tools/pos/lean/check_entrypoints.py (E001-E010 error codes, "
                                    "stdlib only); CI step 'Check entrypoint invariants' added; "
                                    "tests/pos/lean/test_entrypoint_invariants.py. Added in LEAN-POS-10."),
            "gap": None,
            "blocker": None,
        },
        {
            "id": "branch_freshness_and_conflict_preflight",
            "description": "Detect stale branches and merge conflicts before push without modifying worktree",
            "legacy_implementation": "N/A — gap first identified in LEAN-POS-10 root cause analysis",
            "status": "replaced_with_different_mechanism",
            "lean_implementation": ("tools/pos/lean/pre_push_check.py (checks freshness, conflict probe, "
                                    "entrypoints, integrity, validator); .githooks/pre-push (optional local hook); "
                                    "CI duplicates critical invariants. Added in LEAN-POS-10."),
            "gap": ("Local git hooks cannot be enforced by GitHub. "
                    "CI duplicates critical invariants as the authoritative barrier."),
            "blocker": None,
        },
    ]

    replaced = sum(1 for c in capabilities if c["status"] in ("replaced", "replaced_with_different_mechanism"))
    partial = sum(1 for c in capabilities if c["status"] == "partially_replaced")
    blocked = sum(1 for c in capabilities if c["status"] == "blocked")
    gaps = sum(1 for c in capabilities if c["gap"] and c["blocker"])

    return {
        "generated_at": generated_at,
        "summary": {
            "total_capabilities": len(capabilities),
            "replaced": replaced,
            "replaced_with_different_mechanism": sum(1 for c in capabilities if c["status"] == "replaced_with_different_mechanism"),
            "partially_replaced": partial,
            "blocked": blocked,
            "gaps_requiring_blockers": gaps,
        },
        "capabilities": capabilities,
    }


# ---------------------------------------------------------------------------
# Blockers
# ---------------------------------------------------------------------------

def build_blockers(generated_at: str) -> dict:
    """Return open blockers and compact resolved records. Sorted by id."""
    blockers: list[dict] = []

    resolved_blockers = [
        {
            "id": "BLKR-001",
            "type": "governance_conflict",
            "severity": "high",
            "code": MIGR_GOVERNANCE_CONFLICT,
            "status": "resolved",
            "resolved_in": "LEAN-POS-05",
            "resolution": (
                "Founder approved github_satisfies_pos_record_requirement — GitHub Issues and PRs "
                "constitute the canonical POS record for ordinary lean work under RISK-001 and POS-RS. "
                "Explicit project/evidence/, project/reviews/, and project/decisions/ records are not "
                "required for lean work items."
            ),
            "affected_capabilities": [
                "risk_floor_enforcement",
                "audit_traceability",
                "migration_reversibility",
            ],
        },
        {
            "id": "BLKR-002",
            "type": "manifest_integrity",
            "severity": "high",
            "code": "M005",
            "status": "resolved",
            "resolved_in": "LEAN-POS-05",
            "resolution": (
                "Founder approved manifest_resolution=update_hashes. All six frozen governance file "
                "hashes corrected in governance/manifest.yaml. Frozen file content was unchanged since "
                "first commit; hashes were originally computed against pre-move paths. "
                "tools/pos/lean/check_integrity.py now verifies all frozen files on every CI run."
            ),
            "affected_capabilities": [
                "frozen_governance_integrity",
            ],
        },
        {
            "id": "BLKR-004",
            "type": "canonical_data_not_migrated",
            "severity": "high",
            "code": MIGR_CANONICAL_DATA_GAP,
            "status": "resolved",
            "resolved_in": "LEAN-POS-05",
            "resolution": (
                "Founder approved founder_merge_implies_acceptance — the Founder merge of "
                "pos-bootstrap-02 constitutes acceptance of ASA2-WORK-001 and closes "
                "ASA2-DECISION-001 as decided. Bootstrap records are archivable without "
                "creating lean equivalents."
            ),
            "affected_capabilities": [
                "audit_traceability",
            ],
        },
        {
            "id": "BLKR-003",
            "type": "ci_dependency",
            "severity": "medium",
            "code": MIGR_CI_DEPENDENCY,
            "status": "resolved",
            "resolved_in": "LEAN-POS-08",
            "resolution": (
                "Lean validator, generator, integrity checker, tests, and deterministic "
                "root generated-output diff check are active in CI. "
                "Legacy validator (tools/pos/validate.py) and legacy generator "
                "(tools/pos/generate.py) are no longer invoked by CI."
            ),
            "affected_capabilities": [
                "ci_validation",
            ],
        },
        {
            "id": "BLKR-005",
            "type": "documentation_dependency",
            "severity": "medium",
            "code": "M007",
            "status": "resolved",
            "resolved_in": "LEAN-POS-08",
            "resolution": (
                "Root operational documentation (AGENTS.md, CURRENT_STATE.md) updated to "
                "point to Lean POS. MANAGER_INBOX.md deleted — no lean equivalent. "
                "CI diff check retargeted to CURRENT_STATE.md only."
            ),
            "affected_capabilities": [
                "ci_validation",
            ],
        },
        {
            "id": "BLKR-006",
            "type": "missing_capability",
            "severity": "high",
            "code": "M003",
            "status": "resolved",
            "resolved_in": "LEAN-POS-05",
            "resolution": (
                "Founder approved lean_integrity_checker=approved_minimal. "
                "tools/pos/lean/check_integrity.py added (stdlib only, I001-I005 error codes). "
                "CI step 'Check frozen governance integrity' added to .github/workflows/validate-pos.yml. "
                "19 tests added in tests/pos/lean/test_integrity.py."
            ),
            "affected_capabilities": [
                "frozen_governance_integrity",
            ],
        },
    ]

    return {
        "generated_at": generated_at,
        "summary": {
            "total_blockers": len(blockers),
            "resolved_blockers": len(resolved_blockers),
            "by_severity": {
                "high": sum(1 for b in blockers if b["severity"] == "high"),
                "medium": sum(1 for b in blockers if b["severity"] == "medium"),
                "low": sum(1 for b in blockers if b["severity"] == "low"),
            },
            "by_type": sorted(set(b["type"] for b in blockers)),
            "cutover_ready": True,
            "cutover_ready_reason": (
                "All blockers resolved; CUTOVER-05 complete; next phase is CUTOVER-06 "
                "(verify_lean_only_repository)"
            ),
        },
        "blockers": blockers,
        "resolved_blockers": resolved_blockers,
        "founder_decisions_required": [],
        "founder_decisions_recorded": [
            {
                "id": "FD-001",
                "blocker": "BLKR-001",
                "decision": "github_satisfies_pos_record_requirement — approved",
                "decided_in": "LEAN-POS-05",
            },
            {
                "id": "FD-002",
                "blocker": "BLKR-002",
                "decision": "manifest_resolution=update_hashes — approved",
                "decided_in": "LEAN-POS-05",
            },
            {
                "id": "FD-003",
                "blocker": "BLKR-004",
                "decision": "founder_merge_implies_acceptance — approved",
                "decided_in": "LEAN-POS-05",
            },
            {
                "id": "FD-004",
                "blocker": "BLKR-006",
                "decision": "lean_integrity_checker=approved_minimal — approved",
                "decided_in": "LEAN-POS-05",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Cutover plan
# ---------------------------------------------------------------------------

def build_cutover_plan(generated_at: str) -> dict:
    phases = [
        {
            "id": "CUTOVER-01",
            "name": "resolve_governance_and_integrity_blockers",
            "status": "complete",
            "completed_in": "LEAN-POS-05",
            "goal": ("Resolve all governance conflicts and manifest integrity failures. "
                     "Required before any runtime cutover proceeds."),
            "scope": [
                "governance/manifest.yaml (Founder updates hashes)",
                "governance/amendments/GOV-AMD-001.md (if amendment required)",
                "project/work/ASA2-WORK-001.yaml (status → accepted)",
                "project/decisions/ASA2-DECISION-001.yaml (status → decided)",
            ],
            "resolution_summary": [
                "FD-001 decided — github_satisfies_pos_record_requirement approved; BLKR-001 closed",
                "FD-002 decided — manifest_resolution=update_hashes; all 6 frozen file hashes corrected; BLKR-002 closed",
                "FD-003 decided — founder_merge_implies_acceptance; ASA2-WORK-001 archivable; BLKR-004 closed",
                "FD-004 decided — lean_integrity_checker=approved_minimal; check_integrity.py added to CI; BLKR-006 closed",
            ],
            "verification": [
                "python tools/pos/lean/check_integrity.py — exits 0",
                "python -m pytest tests/pos/lean/test_integrity.py -v — 19 passed",
            ],
            "rollback": [
                "Revert governance/manifest.yaml if hash update was incorrect",
                "Revert ASA2-DECISION-001 to pending if decision was premature",
            ],
            "risk": "R2",
            "acceptance_authority": "Founder",
        },
        {
            "id": "CUTOVER-02",
            "name": "establish_canonical_lean_project_state",
            "status": "complete",
            "completed_in": "LEAN-POS-06",
            "goal": ("Create the minimal lean project-state record and confirm lean "
                     "records are valid and complete for current operational state."),
            "scope": [
                "project/lean/state/project-state.yaml (canonical — new path, not fixtures)",
                "tests/pos/lean/test_project_state_cutover.py",
                "tests/pos/lean/fixtures/project-state-cutover/",
            ],
            "resolution_summary": [
                "Canonical project-state authored at project/lean/state/project-state.yaml",
                "Existing project-state.schema.yaml used unchanged (additionalProperties:false respected)",
                "State maps objective→current_objective, constraints→durable_constraints, refs→authority_refs",
                "phase info encoded in notes field; tested by test_active_phase_matches_cutover_plan",
                "No legacy records created or modified; no BOOTSTRAP_STATUS copied",
                "python tools/pos/lean/validate.py passes; generate.py current-state works without BOOTSTRAP_STATUS",
                "38 new tests added; 299 lean tests pass; 403 repository tests pass",
            ],
            "verification": [
                "python tools/pos/lean/validate.py --file project/lean/state/project-state.yaml "
                "--schema project_state — PASS",
                "python tools/pos/lean/check_integrity.py — exits 0",
                "python -m pytest tests/pos/lean -v — 299 passed",
                "python -m pytest tests/pos -v — 403 passed",
                "generate current-state twice with --generated-at injected — byte-identical output",
            ],
            "rollback": [
                "Delete project/lean/state/project-state.yaml to return to pre-CUTOVER-02 state",
                "All prior state preserved in git history",
            ],
            "risk": "R2",
            "acceptance_authority": "Founder",
        },
        {
            "id": "CUTOVER-03",
            "name": "switch_ci_and_documentation_entrypoints",
            "status": "complete",
            "completed_in": "LEAN-POS-08",
            "goal": ("Update CI to run lean tools and tests. Update root entrypoint files "
                     "to point to lean generated outputs. Remove MANAGER_INBOX."),
            "scope": [
                ".github/workflows/validate-pos.yml",
                "AGENTS.md",
                "CURRENT_STATE.md",
                "MANAGER_INBOX.md (deleted)",
            ],
            "resolution_summary": [
                "CI: 'Run validator' replaced with lean validate.py (project_state schema)",
                "CI: 'Run generator' replaced with lean generate.py (fixed --generated-at)",
                "CI: git-diff check retargeted to CURRENT_STATE.md only",
                "CI: MANAGER_INBOX.md removed from paths trigger and diff check",
                "AGENTS.md rewritten as lean POS entry point (no legacy instructions)",
                "CURRENT_STATE.md regenerated from lean generator (offline, deterministic)",
                "MANAGER_INBOX.md deleted — no lean equivalent; git history sufficient",
                "BLKR-003 and BLKR-005 resolved",
            ],
            "verification": [
                "CI invokes tools/pos/lean/validate.py — no tools/pos/validate.py",
                "CI invokes tools/pos/lean/generate.py — no tools/pos/generate.py",
                "git diff --exit-code CURRENT_STATE.md passes after lean generation",
                "AGENTS.md points to project/lean/state/project-state.yaml",
                "MANAGER_INBOX.md absent from repository",
            ],
            "rollback": [
                "Revert validate-pos.yml to previous version from git history",
                "Restore AGENTS.md and CURRENT_STATE.md from git history",
                "Restore MANAGER_INBOX.md from git history if needed",
            ],
            "risk": "R2",
            "acceptance_authority": "Founder",
        },
        {
            "id": "CUTOVER-04",
            "name": "archive_historical_legacy_records",
            "status": "complete",
            "completed_in": "LEAN-POS-09",
            "goal": ("Move legacy canonical records to an archive location. "
                     "Git history is preserved. Records are not rewritten or deleted."),
            "scope": [
                "project/work/ → project/lean/archive/legacy/work/",
                "project/assignments/ → project/lean/archive/legacy/assignments/",
                "project/results/ → project/lean/archive/legacy/results/",
                "project/decisions/ → project/lean/archive/legacy/decisions/",
                "project/reviews/ → project/lean/archive/legacy/reviews/",
                "project/evidence/ → project/lean/archive/legacy/evidence/",
                "project/risks/ → project/lean/archive/legacy/risks/",
                "project/BOOTSTRAP_STATUS.yaml → project/lean/archive/legacy/BOOTSTRAP_STATUS.yaml",
            ],
            "resolution_summary": [
                "git mv for all 7 record directories and BOOTSTRAP_STATUS.yaml to archive path",
                "project/lean/archive/legacy/README.md created (noncanonical marker)",
                "project/lean/state/project-state.yaml notes updated to CUTOVER-04 active, CUTOVER-05 next",
                "CURRENT_STATE.md regenerated from lean generator (offline, deterministic)",
                "migration.py updated: historical_record_preservation → replaced; archive paths in inventory",
                "No active CI, lean tool, or entrypoint depends on archived paths",
                "All archived file bytes preserved exactly (git mv, not copy+rewrite)",
            ],
            "verification": [
                "python -m pytest tests/pos/lean -v — passes",
                "python tools/pos/lean/validate.py exits 0",
                "git log confirms archive paths are in history",
                "Archived files are accessible via git history with original content",
            ],
            "rollback": [
                "git mv project/lean/archive/legacy/* back to project/ directories",
                "All files preserved in git history regardless",
            ],
            "risk": "R2",
            "acceptance_authority": "Founder",
        },
        {
            "id": "CUTOVER-05",
            "name": "remove_legacy_runtime_and_generated_views",
            "status": "complete",
            "completed_in": "LEAN-POS-10",
            "goal": ("Delete legacy tool files, schemas, generated views, and root pointers "
                     "that have been replaced by lean equivalents. "
                     "CI must be lean-only before this phase."),
            "resolution_summary": [
                "git rm tools/pos/validate.py tools/pos/generate.py tools/pos/schemas.py tools/pos/transitions.py",
                "git rm project/schemas/*.schema.yaml (7 files)",
                "git rm project/generated/AGENTS.md project/generated/CURRENT_STATE.md project/generated/MANAGER_INBOX.md",
                "git rm tests/pos/test_repository_bootstrap.py tests/pos/test_role_bootstrap.py (legacy-only tests)",
                "AGENTS.md and CURRENT_STATE.md restored to Lean entrypoint content",
                "Added tools/pos/lean/check_entrypoints.py and pre_push_check.py safeguards",
                "Added CI step for entrypoint invariants and AGENTS.md drift check",
                "project-state notes updated to CUTOVER-05 active / CUTOVER-06 next",
            ],
            "verification": [
                "CI passes after deletions",
                "python -m pytest tests/pos/lean -v passes",
                "python tools/pos/lean/check_entrypoints.py exits 0",
                "No active references to deleted files",
            ],
            "rollback": [
                "git revert CUTOVER-05 commit",
                "All deleted files are in git history and recoverable",
            ],
            "risk": "R2",
            "acceptance_authority": "Founder",
        },
        {
            "id": "CUTOVER-06",
            "name": "verify_lean_only_repository",
            "status": "pending",
            "goal": ("Confirm the repository operates correctly with lean POS only. "
                     "No dual canonical system remains."),
            "scope": [
                "tests/pos/test_repository_bootstrap.py (retire or rewrite for lean)",
                "tests/pos/test_role_bootstrap.py (assess for lean relevance)",
            ],
            "prerequisites": [
                "CUTOVER-05 complete",
                "CI green with lean-only toolchain",
            ],
            "actions": [
                "1. Run full test suite python -m pytest tests/ -v",
                "2. Confirm no test imports from tools.pos.validate or tools.pos.generate (legacy)",
                "3. Retire or rewrite tests/pos/test_repository_bootstrap.py for lean",
                "4. Confirm no project/ directory contains both legacy and lean records",
                "5. Confirm project/lean/generated/ is the sole generated view directory",
                "6. Tag git commit as lean-cutover-complete",
            ],
            "verification": [
                "python -m pytest tests/ -v — all lean tests pass; no legacy-only tests remain",
                "grep -r 'tools.pos.validate' tests/ — no matches (only lean)",
                "grep -r 'tools.pos.generate' tests/ — no matches (only lean)",
                "project/lean/generated/CURRENT_STATE.md exists and < 3500 tokens",
                "project/generated/ does not exist",
            ],
            "rollback": [
                "git revert CUTOVER-06 commit",
                "Restore test files from git history",
            ],
            "risk": "R2",
            "acceptance_authority": "Founder",
        },
    ]

    deletion_manifest = _build_deletion_manifest()

    retained_artifacts = [
        {"path": "governance/frozen/", "reason": "frozen governance — always retain"},
        {"path": "governance/amendments/", "reason": "governance amendment register"},
        {"path": "governance/manifest.yaml", "reason": "manifest retained for lean integrity check"},
        {"path": "roles/", "reason": "role specifications are independent of POS system"},
        {"path": "project/schemas/lean/", "reason": "lean schemas are canonical"},
        {"path": "project/lean/", "reason": "lean records, generated views, archive, and migration"},
        {"path": "tools/pos/lean/", "reason": "lean toolchain"},
        {"path": "tests/pos/lean/", "reason": "lean test suite"},
        {"path": "tools/pos/requirements.txt", "reason": "shared dependency file for lean and legacy tests"},
        {"path": "project/roles/registry.yaml", "reason": "role registry — independent of POS system"},
        {"path": "project/README.md", "reason": "repository documentation"},
        {"path": ".github/workflows/validate-pos.yml", "reason": "retained with lean steps (CUTOVER-03)"},
    ]

    return {
        "generated_at": generated_at,
        "preconditions": [
            "All BLKR-001–BLKR-006 resolved",
            "CUTOVER-01, CUTOVER-02, CUTOVER-03, CUTOVER-04, CUTOVER-05 complete",
            "Founder has approved FD-001 through FD-004",
        ],
        "cutover_ready": True,
        "cutover_ready_reason": (
            "All blockers resolved; CUTOVER-05 complete; "
            "next phase is CUTOVER-06 (verify_lean_only_repository)"
        ),
        "phases": phases,
        "rollback": {
            "strategy": "Each phase is independently reversible via git revert or git mv",
            "global_rollback": (
                "If full rollback to legacy-only is required after CUTOVER-05: "
                "git revert commits from CUTOVER-05 and CUTOVER-04. "
                "All archived records are in git history. Legacy tools are recoverable."
            ),
            "point_of_no_return": "None — git history preserves all artifacts indefinitely",
        },
        "verification": {
            "final_state_checks": [
                "python -m pytest tests/ -v — all lean tests pass",
                "python tools/pos/lean/validate.py exits 0",
                "python tools/pos/lean/generate.py current-state exits 0",
                "CI passes on a clean PR",
                "No dual canonical system: project/work/ does not exist at active path; "
                "project/lean/archive/legacy/ holds historical records; "
                "project/lean/ is the canonical lean record location",
            ]
        },
        "deletion_manifest": deletion_manifest,
        "retained_artifacts": retained_artifacts,
        "founder_decisions": [
            {
                "id": "FD-001",
                "summary": "Governance compatibility: GitHub as canonical POS record for lean work",
                "required_before": "CUTOVER-01",
            },
            {
                "id": "FD-002",
                "summary": "Manifest hash correction (three pre-existing test failures)",
                "required_before": "CUTOVER-01",
            },
            {
                "id": "FD-003",
                "summary": "Accept ASA2-WORK-001 and close ASA2-DECISION-001 as decided",
                "required_before": "CUTOVER-01",
            },
            {
                "id": "FD-004",
                "summary": "Approve lean manifest integrity check (prerequisite for CUTOVER-05)",
                "required_before": "CUTOVER-03",
            },
        ],
    }


def _build_deletion_manifest() -> list[dict]:
    entries = [
        {
            "path": "tools/pos/validate.py",
            "reason": "Replaced by tools/pos/lean/validate.py",
            "replacement": "tools/pos/lean/validate.py",
            "dependencies_checked": [".github/workflows/validate-pos.yml — must be updated in CUTOVER-03"],
            "required_prior_phase": "CUTOVER-03",
            "rollback_method": "git revert or git checkout HEAD~1 -- tools/pos/validate.py",
        },
        {
            "path": "tools/pos/generate.py",
            "reason": "Replaced by tools/pos/lean/generate.py",
            "replacement": "tools/pos/lean/generate.py",
            "dependencies_checked": [".github/workflows/validate-pos.yml — must be updated in CUTOVER-03"],
            "required_prior_phase": "CUTOVER-03",
            "rollback_method": "git revert or git checkout HEAD~1 -- tools/pos/generate.py",
        },
        {
            "path": "tools/pos/schemas.py",
            "reason": "Replaced by tools/pos/lean/schemas.py",
            "replacement": "tools/pos/lean/schemas.py",
            "dependencies_checked": ["tools/pos/validate.py, tools/pos/generate.py — deleted in same phase"],
            "required_prior_phase": "CUTOVER-05",
            "rollback_method": "git revert CUTOVER-05 commit",
        },
        {
            "path": "tools/pos/transitions.py",
            "reason": "Replaced by GitHub state transitions in tools/pos/lean/derived.py",
            "replacement": "tools/pos/lean/derived.py (WORK_ITEM_TRANSITIONS implicit in state machine)",
            "dependencies_checked": ["No CI step references transitions.py directly"],
            "required_prior_phase": "CUTOVER-05",
            "rollback_method": "git revert CUTOVER-05 commit",
        },
        {
            "path": "project/schemas/work-item.schema.yaml",
            "reason": "Replaced by project/schemas/lean/worker-handoff.schema.yaml",
            "replacement": "project/schemas/lean/worker-handoff.schema.yaml",
            "dependencies_checked": ["tools/pos/validate.py — deleted in same phase"],
            "required_prior_phase": "CUTOVER-05",
            "rollback_method": "git revert CUTOVER-05 commit",
        },
        {
            "path": "project/schemas/assignment.schema.yaml",
            "reason": "Replaced by worker-handoff scope/lock fields",
            "replacement": "project/schemas/lean/worker-handoff.schema.yaml (scope + lock)",
            "dependencies_checked": ["tools/pos/validate.py — deleted in same phase"],
            "required_prior_phase": "CUTOVER-05",
            "rollback_method": "git revert CUTOVER-05 commit",
        },
        {
            "path": "project/schemas/worker-result.schema.yaml",
            "reason": "Replaced by worker-handoff deliver field + GitHub PR",
            "replacement": "project/schemas/lean/worker-handoff.schema.yaml (deliver field)",
            "dependencies_checked": ["tools/pos/validate.py — deleted in same phase"],
            "required_prior_phase": "CUTOVER-05",
            "rollback_method": "git revert CUTOVER-05 commit",
        },
        {
            "path": "project/schemas/decision.schema.yaml",
            "reason": "GitHub Issues/PRs replace explicit decision records",
            "replacement": "github_issue (canonical per lean model)",
            "dependencies_checked": ["BLKR-001 must be resolved — requires Founder FD-001"],
            "required_prior_phase": "CUTOVER-05",
            "rollback_method": "git revert CUTOVER-05 commit",
        },
        {
            "path": "project/schemas/review.schema.yaml",
            "reason": "GitHub PR reviews replace explicit review records",
            "replacement": "github_pr_review (canonical per lean model)",
            "dependencies_checked": ["BLKR-001 must be resolved — requires Founder FD-001"],
            "required_prior_phase": "CUTOVER-05",
            "rollback_method": "git revert CUTOVER-05 commit",
        },
        {
            "path": "project/schemas/evidence.schema.yaml",
            "reason": "GitHub CI check runs replace explicit evidence records",
            "replacement": "github_pr_checks (canonical per lean model)",
            "dependencies_checked": ["BLKR-001 must be resolved — requires Founder FD-001"],
            "required_prior_phase": "CUTOVER-05",
            "rollback_method": "git revert CUTOVER-05 commit",
        },
        {
            "path": "project/schemas/risk-record.schema.yaml",
            "reason": "Replaced by worker-handoff risk field",
            "replacement": "project/schemas/lean/worker-handoff.schema.yaml (risk field)",
            "dependencies_checked": ["BLKR-001 — risk_floor_enforcement gap must be documented"],
            "required_prior_phase": "CUTOVER-05",
            "rollback_method": "git revert CUTOVER-05 commit",
        },
        {
            "path": "project/generated/AGENTS.md",
            "reason": "Replaced by project/lean/generated/WORKER_CONTEXT.yaml",
            "replacement": "project/lean/generated/WORKER_CONTEXT.yaml",
            "dependencies_checked": [
                ".github/workflows/validate-pos.yml git-diff check — updated in CUTOVER-03",
                "AGENTS.md root pointer — updated in CUTOVER-03",
            ],
            "required_prior_phase": "CUTOVER-03",
            "rollback_method": "run python tools/pos/generate.py (legacy generator still in git history)",
        },
        {
            "path": "project/generated/CURRENT_STATE.md",
            "reason": "Replaced by project/lean/generated/CURRENT_STATE.md",
            "replacement": "project/lean/generated/CURRENT_STATE.md",
            "dependencies_checked": [
                ".github/workflows/validate-pos.yml git-diff check — updated in CUTOVER-03",
                "CURRENT_STATE.md root pointer — updated in CUTOVER-03",
            ],
            "required_prior_phase": "CUTOVER-03",
            "rollback_method": "run python tools/pos/generate.py (legacy generator still in git history)",
        },
        {
            "path": "project/generated/MANAGER_INBOX.md",
            "reason": "Replaced by blockers section in project/lean/generated/CURRENT_STATE.md",
            "replacement": "project/lean/generated/CURRENT_STATE.md (conflicts + undetermined sections)",
            "dependencies_checked": [
                ".github/workflows/validate-pos.yml git-diff check — updated in CUTOVER-03",
                "MANAGER_INBOX.md root pointer — updated in CUTOVER-03",
            ],
            "required_prior_phase": "CUTOVER-03",
            "rollback_method": "run python tools/pos/generate.py (legacy generator still in git history)",
        },
    ]
    return sorted(entries, key=lambda e: e["path"])
