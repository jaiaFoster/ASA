"""Constants and helpers for the Lean POS validator. No network access."""

import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LEAN_SCHEMAS_DIR = REPO_ROOT / "project" / "schemas" / "lean"

LEAN_SCHEMA_FILES = {
    "project_state": "project-state.schema.yaml",
    "trial_rule": "trial-rule.schema.yaml",
    "exceptional_work": "exceptional-work.schema.yaml",
    "worker_handoff": "worker-handoff.schema.yaml",
}

VALID_RISK_CLASSES = {"R0", "R1", "R2", "R3", "R4", "R5"}

VALID_TRIAL_RULE_STATES = {"active_trial", "adopted", "withdrawn", "superseded"}

VALID_EXCEPTIONAL_WORK_STATES = {"open", "resolved", "cancelled"}

VALID_EXCEPTIONAL_WORK_TRIGGERS = {
    "multi_pr_coordination",
    "multi_worker_coordination",
    "cross_repository_work",
    "durable_external_blocker",
    "risk_requires_structured_controls",
    "explicitly_requested",
}

# Error codes: stable, machine-readable, ordered for deterministic output.
ERR_SCHEMA_MISSING = "E001"
ERR_YAML_PARSE = "E002"
ERR_MISSING_REQUIRED_FIELD = "E003"
ERR_UNKNOWN_FIELD = "E004"
ERR_INVALID_STATE = "E005"
ERR_EMPTY_LIST = "E006"
ERR_INVALID_RISK_CLASS = "E007"
ERR_SCOPE_LOCK_OVERLAP = "E008"
ERR_SCHEMA_VALIDATION = "E009"
ERR_INVALID_REFERENCE = "E010"

# Reconciliation error codes (online layer only)
RECON_INVALID_INPUT = "G001"
RECON_REMOTE_UNAVAILABLE = "G002"
RECON_INCOMPLETE_DATA = "G003"
RECON_AUTHORITY_UNKNOWN = "G004"
RECON_UNAUTHORIZED_MERGE = "G005"
RECON_CONFLICTING_STATE = "G006"
RECON_UNSUPPORTED_RESPONSE = "G007"
RECON_WRITE_ATTEMPT_PROHIBITED = "G008"

# Migration assessment error codes
MIGR_INVALID_INPUT = "M001"
MIGR_UNRESOLVED_REFERENCE = "M002"
MIGR_UNMAPPED_CAPABILITY = "M003"
MIGR_CANONICAL_DATA_GAP = "M004"
MIGR_GOVERNANCE_CONFLICT = "M005"
MIGR_CI_DEPENDENCY = "M006"
MIGR_TEST_DEPENDENCY = "M007"
MIGR_AUTHORITY_UNDETERMINED = "M008"
MIGR_NONDETERMINISTIC_OUTPUT = "M009"
MIGR_WRITE_OUTSIDE_SCOPE = "M010"

LEAN_MIGRATION_DIR = REPO_ROOT / "project" / "lean" / "migration"

# Derived states produced by reconciliation (never stored as canonical)
DERIVED_STATES = (
    "planned",
    "active",
    "review",
    "blocked",
    "accepted",
    "cancelled",
    "conflict",
    "undetermined",
)


LEAN_GENERATED_DIR = REPO_ROOT / "project" / "lean" / "generated"

LEAN_GENERATED_HEADER = (
    "<!-- THIS FILE IS GENERATED. DO NOT EDIT MANUALLY.\n"
    "     Regenerate with: python tools/pos/lean/generate.py\n"
    "     This file is not a canonical record. -->\n"
)

# Estimated token budget thresholds (1 token ≈ 4 chars)
TOKEN_BUDGET_CURRENT_STATE = 3500
TOKEN_BUDGET_WORKER_CONTEXT_NORMAL = 2000
TOKEN_BUDGET_WORKER_CONTEXT_ELEVATED = 3500  # R3+


def estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token ≈ 4 characters."""
    return max(1, len(text) // 4)


def load_yaml(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_lean_schema(name: str):
    filename = LEAN_SCHEMA_FILES.get(name)
    if filename is None:
        return None
    path = LEAN_SCHEMAS_DIR / filename
    if not path.exists():
        return None
    return load_yaml(path)
