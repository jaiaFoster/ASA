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
