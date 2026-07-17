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

RECORD_DIRS = {
    "work": REPO_ROOT / "project" / "work",
    "assignments": REPO_ROOT / "project" / "assignments",
    "results": REPO_ROOT / "project" / "results",
    "decisions": REPO_ROOT / "project" / "decisions",
    "reviews": REPO_ROOT / "project" / "reviews",
    "evidence": REPO_ROOT / "project" / "evidence",
    "risks": REPO_ROOT / "project" / "risks",
}

SCHEMA_FOR_RECORD_DIR = {
    "work": "work-item.schema.yaml",
    "assignments": "assignment.schema.yaml",
    "results": "worker-result.schema.yaml",
    "decisions": "decision.schema.yaml",
    "reviews": "review.schema.yaml",
    "evidence": "evidence.schema.yaml",
    "risks": "risk-record.schema.yaml",
}

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
    "risk-record.schema.yaml",
]

# Risk class ordering: index in this list is the rank (higher = more risk)
RISK_CLASSES = ["R0", "R1", "R2", "R3", "R4", "R5"]
RISK_CLASS_RANK = {cls: i for i, cls in enumerate(RISK_CLASSES)}


def risk_rank(cls: str) -> int:
    return RISK_CLASS_RANK.get(cls, -1)


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

RISK_RECORD_STATUSES = ["draft", "classified", "confirmed", "superseded"]

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
    "FOUNDER ACCEPTED",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_yaml(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_records(directory: Path) -> list:
    """Load all YAML records from a directory, skipping .gitkeep."""
    records = []
    if not directory.is_dir():
        return records
    for f in sorted(directory.iterdir()):
        if f.suffix in (".yaml", ".yml") and f.name != ".gitkeep":
            try:
                data = load_yaml(f)
                if data is not None:
                    data["_source_file"] = str(f.relative_to(REPO_ROOT))
                    records.append(data)
            except Exception as e:
                records.append({"_source_file": str(f.relative_to(REPO_ROOT)), "_load_error": str(e)})
    return records
