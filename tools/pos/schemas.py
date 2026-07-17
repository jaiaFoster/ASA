"""Shared constants and helpers for the ASA2 POS tooling."""

import hashlib
import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

MANIFEST_PATH = REPO_ROOT / "governance" / "manifest.yaml"
BOOTSTRAP_STATUS_PATH = REPO_ROOT / "project" / "BOOTSTRAP_STATUS.yaml"
ROLE_REGISTRY_PATH = REPO_ROOT / "project" / "roles" / "registry.yaml"
SCHEMAS_DIR = REPO_ROOT / "project" / "schemas"
GENERATED_DIR = REPO_ROOT / "project" / "generated"

REQUIRED_DIRECTORIES = [
    "governance/frozen",
    "governance/amendments",
    "governance/audits",
    "governance/history/superseded",
    "project/schemas",
    "project/work",
    "project/assignments",
    "project/results",
    "project/decisions",
    "project/reviews",
    "project/evidence",
    "project/risks",
    "project/roles",
    "project/generated",
    "tools/pos",
    "tests/pos",
    ".github/workflows",
]

SCHEMA_FILES = [
    "work-item.schema.yaml",
    "assignment.schema.yaml",
    "worker-result.schema.yaml",
    "decision.schema.yaml",
    "review.schema.yaml",
    "evidence.schema.yaml",
]

RISK_CLASSES = ["R0", "R1", "R2", "R3", "R4", "R5"]

WORK_ITEM_STATUSES = [
    "proposed", "ready", "assigned", "in_progress",
    "blocked", "review", "accepted", "rejected", "cancelled",
]

ASSIGNMENT_STATUSES = [
    "draft", "issued", "acknowledged", "in_progress",
    "submitted", "closed", "cancelled",
]

WORKER_RESULT_STATUSES = ["partial", "complete", "failed", "blocked"]

DECISION_STATUSES = ["proposed", "pending", "decided", "superseded", "cancelled"]

REVIEW_STATUSES = ["requested", "in_progress", "changes_requested", "complete", "cancelled"]

EVIDENCE_TYPES = [
    "test_output", "command_output", "screenshot", "log",
    "deployment_verification", "source_reference", "diff",
    "review_record", "manual_observation",
]

GENERATED_FILE_WARNING = (
    "THIS FILE IS GENERATED.\n"
    "DO NOT EDIT MANUALLY.\n"
    "Regenerate with: python tools/pos/generate.py\n"
)

FORBIDDEN_VALIDATOR_OUTPUT = [
    "APPROVED", "REJECTED", "SAFE TO MERGE", "GOVERNANCE SATISFIED",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_yaml(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
