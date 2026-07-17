"""
Tests for the ASA2 POS repository — bootstrap state and lifecycle validation.

Safety rules:
- Never modify real frozen governance files.
- Never modify real canonical records.
- All mutation tests use temporary copies in tmp_path.
- No network access required.
"""

import copy
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.pos.schemas import (
    MANIFEST_PATH,
    BOOTSTRAP_STATUS_PATH,
    ROLE_REGISTRY_PATH,
    SCHEMAS_DIR,
    SCHEMA_FILES,
    REQUIRED_DIRECTORIES,
    GENERATED_FILE_WARNING,
    RISK_CLASSES,
    FORBIDDEN_VALIDATOR_OUTPUT,
    risk_rank,
    sha256_file,
    load_yaml,
    load_records,
    RECORD_DIRS,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

VALID_WORK_ITEM = {
    "id": "ASA2-WORK-999",
    "title": "Test work item",
    "status": "review",
    "objective": "Test objective",
    "scope": "Test scope",
    "owner_role": "ROLE-PM",
    "acceptance_authority": "Founder",
    "dependencies": [],
    "risk": {
        "declared_properties": {"touches_pos_tooling": True},
        "deterministic_class": "R1",
        "manual_override": None,
        "effective_class": "R1",
    },
    "risk_record": "ASA2-RISK-999",
    "assignments": ["ASA2-ASG-999"],
    "results": ["ASA2-RESULT-999"],
    "reviews": ["ASA2-REVIEW-999"],
    "evidence": ["ASA2-EVID-999"],
    "decisions": ["ASA2-DECISION-999"],
    "artifacts": [],
    "created_at": "2026-07-17T00:00:00Z",
    "updated_at": "2026-07-17T00:00:00Z",
}

VALID_RISK_RECORD = {
    "id": "ASA2-RISK-999",
    "subject_type": "work_item",
    "subject_id": "ASA2-WORK-999",
    "status": "confirmed",
    "declared_properties": {"touches_pos_tooling": True},
    "deterministic_class": "R1",
    "manual_override": None,
    "effective_class": "R1",
    "classification_rationale": "Test rationale",
    "property_confirmation": {
        "confirmed": True,
        "confirmed_by": "Founder",
        "confirmed_at": "2026-07-17T00:00:00Z",
        "notes": None,
    },
    "classified_by": "implementation-worker",
    "confirmed_by": "Founder",
    "created_at": "2026-07-17T00:00:00Z",
    "updated_at": "2026-07-17T00:00:00Z",
}

VALID_ASSIGNMENT = {
    "id": "ASA2-ASG-999",
    "work_item_id": "ASA2-WORK-999",
    "risk_record": "ASA2-RISK-999",
    "worker_type": "implementation_worker",
    "status": "submitted",
    "base_commit": "abc123",
    "objective": "Test objective",
    "allowed_scope": ["tools/pos/"],
    "forbidden_scope": ["governance/frozen/"],
    "required_tests": ["pytest"],
    "required_outputs": ["result.yaml"],
    "result_path": "project/results/ASA2-RESULT-999.yaml",
    "assigned_by": "Founder",
    "acceptance_authority": "Founder",
    "created_at": "2026-07-17T00:00:00Z",
    "updated_at": "2026-07-17T00:00:00Z",
}

VALID_RESULT = {
    "id": "ASA2-RESULT-999",
    "assignment_id": "ASA2-ASG-999",
    "work_item_id": "ASA2-WORK-999",
    "status": "complete",
    "summary": "Test complete",
    "files_changed": ["tools/pos/validate.py"],
    "tests_run": ["pytest"],
    "verification": {"passed": True},
    "evidence": ["ASA2-EVID-999"],
    "known_limitations": [],
    "unresolved_questions": [],
    "submitted_at": "2026-07-17T00:00:00Z",
}

VALID_REVIEW = {
    "id": "ASA2-REVIEW-999",
    "subject_type": "work_item",
    "subject_id": "ASA2-WORK-999",
    "work_item_id": "ASA2-WORK-999",
    "reviewer": "implementation-worker",
    "reviewer_role": "ROLE-PM",
    "status": "complete",
    "scope": "Technical review",
    "findings": [{"finding": "All checks passed", "result": "PASS"}],
    "evidence_reviewed": ["ASA2-EVID-999"],
    "conclusion": "technically ready for Founder review",
    "created_at": "2026-07-17T00:00:00Z",
    "completed_at": "2026-07-17T00:00:00Z",
}

VALID_EVIDENCE = {
    "id": "ASA2-EVID-999",
    "subject_type": "work_item",
    "subject_id": "ASA2-WORK-999",
    "evidence_type": "test_output",
    "location": "tests/pos/",
    "description": "pytest output",
    "producer": "implementation-worker",
    "collected_at": "2026-07-17T00:00:00Z",
    "integrity": {"method": "git_commit", "value": "abc123"},
    "notes": None,
}

VALID_DECISION = {
    "id": "ASA2-DECISION-999",
    "title": "Accept test work",
    "question": "Accept?",
    "status": "pending",
    "decision_authority": "Founder",
    "context": "Test context",
    "options": [{"id": "accept"}],
    "affected_records": ["ASA2-WORK-999"],
    "decision": None,
    "rationale": None,
    "created_at": "2026-07-17T00:00:00Z",
    "decided_at": None,
}


def make_repo_copy(tmp_path: Path) -> Path:
    """Copy repo to tmp_path for mutation tests."""
    dest = tmp_path / "ASA"
    shutil.copytree(REPO_ROOT, dest, ignore=shutil.ignore_patterns(".git"))
    return dest


def write_records(repo: Path, records_by_dir: dict) -> None:
    """Write fixture records into a repo copy."""
    for dir_name, records in records_by_dir.items():
        d = repo / "project" / dir_name
        d.mkdir(parents=True, exist_ok=True)
        for rec in records:
            f = d / f"{rec['id']}.yaml"
            with open(f, "w", encoding="utf-8") as fh:
                yaml.dump(rec, fh, default_flow_style=False, allow_unicode=True)


def run_validator(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/pos/validate.py"],
        cwd=repo, capture_output=True, text=True,
    )


def run_generator(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/pos/generate.py"],
        cwd=repo, capture_output=True, text=True,
    )


# ===========================================================================
# Group 1: Required directories
# ===========================================================================

@pytest.mark.parametrize("directory", REQUIRED_DIRECTORIES)
def test_required_directory_exists(directory):
    assert (REPO_ROOT / directory).is_dir(), f"Required directory missing: {directory}"


# ===========================================================================
# Group 2: Manifest integrity
# ===========================================================================

def test_manifest_parses():
    assert MANIFEST_PATH.exists()
    data = load_yaml(MANIFEST_PATH)
    assert data is not None
    assert "documents" in data
    assert isinstance(data["documents"], list)


def test_frozen_hashes_match_manifest():
    data = load_yaml(MANIFEST_PATH)
    mismatches = []
    for doc in data["documents"]:
        if doc.get("status") == "missing":
            continue
        filename = doc.get("filename")
        expected = doc.get("sha256")
        if not filename or not expected:
            continue
        path = REPO_ROOT / filename
        assert path.exists(), f"File listed in manifest not found: {filename}"
        actual = sha256_file(path)
        if actual != expected:
            mismatches.append(f"{doc['id']}: expected {expected[:16]}... got {actual[:16]}...")
    assert not mismatches, "Hash mismatches:\n" + "\n".join(mismatches)


def test_risk_001_in_manifest():
    data = load_yaml(MANIFEST_PATH)
    ids = {d["id"] for d in data["documents"]}
    assert "RISK-001" in ids, "RISK-001 must be in manifest"
    risk = next(d for d in data["documents"] if d["id"] == "RISK-001")
    assert risk.get("status") == "frozen"
    assert risk.get("sha256") is not None
    assert risk.get("filename") is not None


def test_no_audit_placeholders_in_manifest():
    data = load_yaml(MANIFEST_PATH)
    ids = {d["id"] for d in data["documents"]}
    assert "GOV-AUDIT-001" not in ids, "Audit placeholders must be removed from manifest"
    assert "RISK-001-AUDIT-001" not in ids, "Audit placeholders must be removed from manifest"


# ===========================================================================
# Group 3: Bootstrap and registry
# ===========================================================================

def test_bootstrap_status_parses():
    assert BOOTSTRAP_STATUS_PATH.exists()
    data = load_yaml(BOOTSTRAP_STATUS_PATH)
    assert data is not None
    assert "project" in data
    assert "phase" in data


def test_role_registry_parses():
    assert ROLE_REGISTRY_PATH.exists()
    data = load_yaml(ROLE_REGISTRY_PATH)
    assert data is not None
    assert "roles" in data
    assert isinstance(data["roles"], list)
    assert len(data["roles"]) >= 1


# ===========================================================================
# Group 4: Schemas parse
# ===========================================================================

@pytest.mark.parametrize("schema_file", SCHEMA_FILES)
def test_schema_parses(schema_file):
    path = SCHEMAS_DIR / schema_file
    assert path.exists(), f"Schema file missing: {schema_file}"
    data = load_yaml(path)
    assert data is not None


def test_risk_record_schema_exists():
    assert (SCHEMAS_DIR / "risk-record.schema.yaml").exists()


# ===========================================================================
# Group 5: Canonical records valid
# ===========================================================================

def test_canonical_lifecycle_records_exist():
    expected = {
        "work": ["ASA2-WORK-001.yaml"],
        "risks": ["ASA2-RISK-001.yaml"],
        "assignments": ["ASA2-ASG-001.yaml"],
        "results": ["ASA2-RESULT-001.yaml"],
        "reviews": ["ASA2-REVIEW-001.yaml"],
        "evidence": ["ASA2-EVIDENCE-001.yaml"],
        "decisions": ["ASA2-DECISION-001.yaml"],
    }
    for dir_name, files in expected.items():
        for f in files:
            path = REPO_ROOT / "project" / dir_name / f
            assert path.exists(), f"Expected lifecycle record missing: project/{dir_name}/{f}"


def test_canonical_records_parse():
    for dir_name, dir_path in RECORD_DIRS.items():
        records = load_records(dir_path)
        for rec in records:
            assert "_load_error" not in rec, f"Parse error in {rec.get('_source_file')}: {rec.get('_load_error')}"


# ===========================================================================
# Group 6: Validator passes on committed state
# ===========================================================================

def test_validator_passes():
    result = run_validator(REPO_ROOT)
    assert result.returncode == 0, (
        f"Validator failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "[PASS] All checks passed." in result.stdout


# ===========================================================================
# Group 7: Generated files
# ===========================================================================

@pytest.mark.parametrize("filename", ["AGENTS.md", "CURRENT_STATE.md", "MANAGER_INBOX.md"])
def test_generated_files_contain_warning(filename):
    path = REPO_ROOT / "project" / "generated" / filename
    assert path.exists(), f"Generated file missing: project/generated/{filename}"
    content = path.read_text(encoding="utf-8")
    assert "THIS FILE IS GENERATED" in content
    assert "DO NOT EDIT MANUALLY" in content


def test_manager_inbox_contains_pending_decision():
    path = REPO_ROOT / "project" / "generated" / "MANAGER_INBOX.md"
    content = path.read_text(encoding="utf-8")
    assert "ASA2-DECISION-001" in content, "Manager inbox must show pending Founder decision"


def test_generator_is_deterministic():
    outputs = []
    for _ in range(2):
        r = run_generator(REPO_ROOT)
        assert r.returncode == 0, f"Generator failed: {r.stderr}"
        snapshot = {}
        for f in ["AGENTS.md", "CURRENT_STATE.md", "MANAGER_INBOX.md"]:
            p = REPO_ROOT / "project" / "generated" / f
            snapshot[f] = p.read_text(encoding="utf-8")
        outputs.append(snapshot)
    for f in outputs[0]:
        assert outputs[0][f] == outputs[1][f], f"Generator not deterministic for {f}"


# ===========================================================================
# Group 8: Hash mismatch fails validation
# ===========================================================================

def test_validator_fails_on_bad_hash(tmp_path):
    repo = make_repo_copy(tmp_path)
    manifest_path = repo / "governance" / "manifest.yaml"
    data = load_yaml(manifest_path)
    for doc in data["documents"]:
        if doc.get("status") != "missing" and doc.get("sha256"):
            doc["sha256"] = "0" * 64
            break
    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    r = run_validator(repo)
    assert r.returncode != 0
    assert "[FAIL]" in r.stdout


def test_validator_fails_on_missing_risk001(tmp_path):
    repo = make_repo_copy(tmp_path)
    risk_path = repo / "governance" / "frozen" / "RISK-001"
    if risk_path.exists():
        risk_path.unlink()
    r = run_validator(repo)
    assert r.returncode != 0
    assert "[FAIL]" in r.stdout


# ===========================================================================
# Group 9: Invalid lifecycle — reference failures
# ===========================================================================

def test_duplicate_record_id_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    # Write two records with the same ID in different dirs
    dup = copy.deepcopy(VALID_WORK_ITEM)
    dup_asg = copy.deepcopy(VALID_ASSIGNMENT)
    dup_asg["id"] = dup["id"]  # same ID as work item
    write_records(repo, {
        "work": [dup],
        "assignments": [dup_asg],
    })
    r = run_validator(repo)
    assert r.returncode != 0
    assert "Duplicate ID" in r.stdout


def test_assignment_references_missing_work_item_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    asg = copy.deepcopy(VALID_ASSIGNMENT)
    asg["work_item_id"] = "ASA2-WORK-NONEXISTENT"
    write_records(repo, {"assignments": [asg]})
    r = run_validator(repo)
    assert r.returncode != 0
    assert "[FAIL]" in r.stdout


def test_work_item_lists_missing_assignment_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    wi = copy.deepcopy(VALID_WORK_ITEM)
    wi["assignments"] = ["ASA2-ASG-NONEXISTENT"]
    write_records(repo, {"work": [wi]})
    r = run_validator(repo)
    assert r.returncode != 0
    assert "[FAIL]" in r.stdout


def test_submitted_assignment_without_result_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    asg = copy.deepcopy(VALID_ASSIGNMENT)
    asg["status"] = "submitted"
    # Don't write any result
    wi = copy.deepcopy(VALID_WORK_ITEM)
    write_records(repo, {
        "work": [wi],
        "assignments": [asg],
        "risks": [VALID_RISK_RECORD],
        "reviews": [VALID_REVIEW],
        "evidence": [VALID_EVIDENCE],
        "decisions": [VALID_DECISION],
    })
    r = run_validator(repo)
    assert r.returncode != 0
    assert "[FAIL]" in r.stdout


def test_closed_assignment_without_result_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    asg = copy.deepcopy(VALID_ASSIGNMENT)
    asg["status"] = "closed"
    wi = copy.deepcopy(VALID_WORK_ITEM)
    write_records(repo, {
        "work": [wi],
        "assignments": [asg],
        "risks": [VALID_RISK_RECORD],
        "reviews": [VALID_REVIEW],
        "evidence": [VALID_EVIDENCE],
        "decisions": [VALID_DECISION],
    })
    r = run_validator(repo)
    assert r.returncode != 0
    assert "[FAIL]" in r.stdout


def test_review_stage_work_without_review_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    wi = copy.deepcopy(VALID_WORK_ITEM)
    wi["status"] = "review"
    wi["reviews"] = []
    write_records(repo, {
        "work": [wi],
        "assignments": [VALID_ASSIGNMENT],
        "results": [VALID_RESULT],
        "risks": [VALID_RISK_RECORD],
        "evidence": [VALID_EVIDENCE],
        "decisions": [VALID_DECISION],
    })
    r = run_validator(repo)
    assert r.returncode != 0
    assert "[FAIL]" in r.stdout


# ===========================================================================
# Group 10: Invalid lifecycle — acceptance prerequisites
# ===========================================================================

def _accepted_lifecycle():
    wi = copy.deepcopy(VALID_WORK_ITEM)
    wi["status"] = "accepted"
    dec = copy.deepcopy(VALID_DECISION)
    dec["status"] = "decided"
    dec["decision"] = "accept"
    dec["rationale"] = "Looks good"
    dec["decided_at"] = "2026-07-17T12:00:00Z"
    return wi, dec


def test_accepted_work_without_complete_result_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    wi, dec = _accepted_lifecycle()
    res = copy.deepcopy(VALID_RESULT)
    res["status"] = "partial"  # not complete
    write_records(repo, {
        "work": [wi], "assignments": [VALID_ASSIGNMENT],
        "results": [res], "reviews": [VALID_REVIEW],
        "evidence": [VALID_EVIDENCE], "decisions": [dec],
        "risks": [VALID_RISK_RECORD],
    })
    r = run_validator(repo)
    assert r.returncode != 0


def test_accepted_work_without_completed_review_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    wi, dec = _accepted_lifecycle()
    rev = copy.deepcopy(VALID_REVIEW)
    rev["status"] = "in_progress"
    write_records(repo, {
        "work": [wi], "assignments": [VALID_ASSIGNMENT],
        "results": [VALID_RESULT], "reviews": [rev],
        "evidence": [VALID_EVIDENCE], "decisions": [dec],
        "risks": [VALID_RISK_RECORD],
    })
    r = run_validator(repo)
    assert r.returncode != 0


def test_accepted_work_without_evidence_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    wi, dec = _accepted_lifecycle()
    wi["evidence"] = []
    write_records(repo, {
        "work": [wi], "assignments": [VALID_ASSIGNMENT],
        "results": [VALID_RESULT], "reviews": [VALID_REVIEW],
        "decisions": [dec], "risks": [VALID_RISK_RECORD],
    })
    r = run_validator(repo)
    assert r.returncode != 0


def test_accepted_work_without_decided_decision_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    wi, _ = _accepted_lifecycle()
    pending_dec = copy.deepcopy(VALID_DECISION)  # status=pending
    write_records(repo, {
        "work": [wi], "assignments": [VALID_ASSIGNMENT],
        "results": [VALID_RESULT], "reviews": [VALID_REVIEW],
        "evidence": [VALID_EVIDENCE], "decisions": [pending_dec],
        "risks": [VALID_RISK_RECORD],
    })
    r = run_validator(repo)
    assert r.returncode != 0


# ===========================================================================
# Group 11: Invalid lifecycle — decisions
# ===========================================================================

def test_pending_decision_with_nonnull_value_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    dec = copy.deepcopy(VALID_DECISION)
    dec["status"] = "pending"
    dec["decision"] = "accept"  # must be null when pending
    write_records(repo, {"decisions": [dec]})
    r = run_validator(repo)
    assert r.returncode != 0


def test_decided_decision_without_rationale_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    dec = copy.deepcopy(VALID_DECISION)
    dec["status"] = "decided"
    dec["decision"] = "accept"
    dec["decided_at"] = "2026-07-17T12:00:00Z"
    dec["rationale"] = None  # missing
    write_records(repo, {"decisions": [dec]})
    r = run_validator(repo)
    assert r.returncode != 0


# ===========================================================================
# Group 12: Invalid risk records
# ===========================================================================

def test_invalid_risk_class_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    risk = copy.deepcopy(VALID_RISK_RECORD)
    risk["deterministic_class"] = "R9"  # invalid
    risk["effective_class"] = "R9"
    write_records(repo, {"risks": [risk]})
    # Schema validation will catch invalid enum value
    r = run_validator(repo)
    assert r.returncode != 0


def test_effective_class_below_deterministic_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    risk = copy.deepcopy(VALID_RISK_RECORD)
    risk["deterministic_class"] = "R3"
    risk["effective_class"] = "R1"  # below deterministic — not allowed
    write_records(repo, {"risks": [risk]})
    r = run_validator(repo)
    assert r.returncode != 0
    assert "below deterministic" in r.stdout or "[FAIL]" in r.stdout


def test_manual_override_lowering_risk_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    risk = copy.deepcopy(VALID_RISK_RECORD)
    risk["deterministic_class"] = "R3"
    risk["effective_class"] = "R3"
    risk["manual_override"] = {
        "requested_class": "R1",  # would lower risk — not allowed
        "reason": "We think it's fine",
        "authorized_by": "Founder",
        "created_at": "2026-07-17T00:00:00Z",
    }
    write_records(repo, {"risks": [risk]})
    r = run_validator(repo)
    assert r.returncode != 0


def test_manual_override_missing_authority_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    risk = copy.deepcopy(VALID_RISK_RECORD)
    risk["manual_override"] = {
        "requested_class": "R2",
        "reason": "Extra caution",
        "authorized_by": "",  # empty — fails
        "created_at": "2026-07-17T00:00:00Z",
    }
    risk["effective_class"] = "R2"
    write_records(repo, {"risks": [risk]})
    r = run_validator(repo)
    assert r.returncode != 0


def test_confirmed_risk_without_property_confirmation_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    risk = copy.deepcopy(VALID_RISK_RECORD)
    risk["status"] = "confirmed"
    risk["property_confirmation"]["confirmed"] = False  # not confirmed
    write_records(repo, {"risks": [risk]})
    r = run_validator(repo)
    assert r.returncode != 0


def test_risk_subject_does_not_exist_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    risk = copy.deepcopy(VALID_RISK_RECORD)
    risk["subject_id"] = "ASA2-WORK-NONEXISTENT"
    write_records(repo, {"risks": [risk]})
    r = run_validator(repo)
    assert r.returncode != 0


# ===========================================================================
# Group 13: Evidence validation
# ===========================================================================

def test_evidence_subject_does_not_exist_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    evid = copy.deepcopy(VALID_EVIDENCE)
    evid["subject_id"] = "ASA2-WORK-NONEXISTENT"
    write_records(repo, {"evidence": [evid]})
    r = run_validator(repo)
    assert r.returncode != 0


# ===========================================================================
# Group 14: Review validation
# ===========================================================================

def test_completed_review_without_findings_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    wi = copy.deepcopy(VALID_WORK_ITEM)
    rev = copy.deepcopy(VALID_REVIEW)
    rev["status"] = "complete"
    rev["findings"] = []  # no findings
    write_records(repo, {
        "work": [wi], "assignments": [VALID_ASSIGNMENT],
        "results": [VALID_RESULT], "reviews": [rev],
        "evidence": [VALID_EVIDENCE], "decisions": [VALID_DECISION],
        "risks": [VALID_RISK_RECORD],
    })
    r = run_validator(repo)
    assert r.returncode != 0


def test_completed_review_without_evidence_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    wi = copy.deepcopy(VALID_WORK_ITEM)
    rev = copy.deepcopy(VALID_REVIEW)
    rev["evidence_reviewed"] = []  # no evidence
    write_records(repo, {
        "work": [wi], "assignments": [VALID_ASSIGNMENT],
        "results": [VALID_RESULT], "reviews": [rev],
        "evidence": [VALID_EVIDENCE], "decisions": [VALID_DECISION],
        "risks": [VALID_RISK_RECORD],
    })
    r = run_validator(repo)
    assert r.returncode != 0


# ===========================================================================
# Group 15: Structural failures
# ===========================================================================

def test_missing_required_directory_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    import shutil as _shutil
    _shutil.rmtree(repo / "project" / "schemas")
    r = run_validator(repo)
    assert r.returncode != 0


def test_invalid_yaml_fails(tmp_path):
    repo = make_repo_copy(tmp_path)
    bad_file = repo / "project" / "work" / "bad.yaml"
    bad_file.write_text(": : invalid: yaml: [\n", encoding="utf-8")
    r = run_validator(repo)
    assert r.returncode != 0


def test_record_fails_schema_validation(tmp_path):
    repo = make_repo_copy(tmp_path)
    wi = {"id": "ASA2-WORK-999", "title": "Missing required fields"}  # incomplete
    f = repo / "project" / "work" / "ASA2-WORK-999.yaml"
    with open(f, "w", encoding="utf-8") as fh:
        yaml.dump(wi, fh)
    r = run_validator(repo)
    assert r.returncode != 0


# ===========================================================================
# Group 16: Stale generated files
# ===========================================================================

def test_stale_generated_file_detectable(tmp_path):
    repo = make_repo_copy(tmp_path)
    stale_path = repo / "project" / "generated" / "AGENTS.md"
    stale_path.write_text("This is stale content with no warning banner", encoding="utf-8")
    r = run_validator(repo)
    assert r.returncode != 0
    assert "[FAIL]" in r.stdout


def test_generator_output_has_warning_banner(tmp_path):
    repo = make_repo_copy(tmp_path)
    run_generator(repo)
    for filename in ["AGENTS.md", "CURRENT_STATE.md", "MANAGER_INBOX.md"]:
        content = (repo / "project" / "generated" / filename).read_text(encoding="utf-8")
        assert "THIS FILE IS GENERATED" in content
        assert "DO NOT EDIT MANUALLY" in content


# ===========================================================================
# Group 17: Authority-boundary test
# ===========================================================================

def test_validator_never_emits_forbidden_language():
    result = run_validator(REPO_ROOT)
    stdout_upper = result.stdout.upper()
    for forbidden in FORBIDDEN_VALIDATOR_OUTPUT:
        # Allow the word in diagnostic messages about the constraint itself
        # but it must not appear as a status output like "[APPROVED]"
        assert f"[{forbidden}]" not in stdout_upper, (
            f"Validator emitted forbidden authority word as status: [{forbidden}]"
        )


# ===========================================================================
# Group 18: Valid accepted lifecycle fixture
# ===========================================================================

def test_valid_accepted_lifecycle_passes(tmp_path):
    """A complete accepted lifecycle with a decided Founder decision should pass."""
    repo = make_repo_copy(tmp_path)
    wi, dec = _accepted_lifecycle()
    write_records(repo, {
        "work": [wi],
        "assignments": [VALID_ASSIGNMENT],
        "results": [VALID_RESULT],
        "reviews": [VALID_REVIEW],
        "evidence": [VALID_EVIDENCE],
        "decisions": [dec],
        "risks": [VALID_RISK_RECORD],
    })
    r = run_validator(repo)
    assert r.returncode == 0, f"Valid accepted lifecycle failed:\n{r.stdout}\n{r.stderr}"


# ===========================================================================
# Group 19: Risk class ordering
# ===========================================================================

def test_risk_class_ordering():
    assert risk_rank("R0") < risk_rank("R1")
    assert risk_rank("R1") < risk_rank("R2")
    assert risk_rank("R2") < risk_rank("R3")
    assert risk_rank("R3") < risk_rank("R4")
    assert risk_rank("R4") < risk_rank("R5")
    assert risk_rank("INVALID") == -1
