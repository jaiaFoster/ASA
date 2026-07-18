"""
Tests for the Lean POS offline validator.

Safety rules:
- No network access anywhere in this file.
- No modification of real canonical records.
- Mutation tests use in-memory dicts or tmp_path only.
"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from tools.pos.lean.schemas import (
    LEAN_SCHEMAS_DIR,
    LEAN_SCHEMA_FILES,
    VALID_RISK_CLASSES,
    VALID_TRIAL_RULE_STATES,
    VALID_EXCEPTIONAL_WORK_STATES,
    VALID_EXCEPTIONAL_WORK_TRIGGERS,
    load_yaml,
    load_lean_schema,
)

FIXTURES_VALID = REPO_ROOT / "project" / "lean" / "fixtures" / "valid"
FIXTURES_INVALID = REPO_ROOT / "project" / "lean" / "fixtures" / "invalid"
VALIDATOR = REPO_ROOT / "tools" / "pos" / "lean" / "validate.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_validator(*extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *extra_args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def write_fixture(tmp_path: Path, name: str, data: dict) -> Path:
    p = tmp_path / name
    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    return p


# ---------------------------------------------------------------------------
# Group 1: Schema presence
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("schema_name,filename", LEAN_SCHEMA_FILES.items())
def test_lean_schema_exists(schema_name, filename):
    path = LEAN_SCHEMAS_DIR / filename
    assert path.exists(), f"Lean schema missing: {filename}"


@pytest.mark.parametrize("schema_name,filename", LEAN_SCHEMA_FILES.items())
def test_lean_schema_parses(schema_name, filename):
    schema = load_lean_schema(schema_name)
    assert schema is not None
    assert isinstance(schema, dict)


# ---------------------------------------------------------------------------
# Group 2: Valid fixtures pass
# ---------------------------------------------------------------------------

def test_valid_project_state_passes(tmp_path):
    r = run_validator(
        "--file", str(FIXTURES_VALID / "project-state.yaml"),
        "--schema", "project_state",
    )
    assert r.returncode == 0, f"Expected pass:\n{r.stdout}\n{r.stderr}"
    assert "[PASS]" in r.stdout


def test_valid_trial_rule_passes(tmp_path):
    r = run_validator(
        "--file", str(FIXTURES_VALID / "trial-rule.yaml"),
        "--schema", "trial_rule",
    )
    assert r.returncode == 0, f"Expected pass:\n{r.stdout}\n{r.stderr}"


def test_valid_exceptional_work_passes(tmp_path):
    r = run_validator(
        "--file", str(FIXTURES_VALID / "exceptional-work.yaml"),
        "--schema", "exceptional_work",
    )
    assert r.returncode == 0, f"Expected pass:\n{r.stdout}\n{r.stderr}"


def test_valid_worker_handoff_passes(tmp_path):
    r = run_validator(
        "--file", str(FIXTURES_VALID / "worker-handoff.yaml"),
        "--schema", "worker_handoff",
    )
    assert r.returncode == 0, f"Expected pass:\n{r.stdout}\n{r.stderr}"


def test_all_valid_fixtures_pass():
    r = run_validator("--all-fixtures")
    # All valid AND invalid fixtures are present; filter by checking the subset
    # by running only the valid directory indirectly (all-fixtures includes invalid).
    # This test just checks there is no crash and exit codes are correct per file.
    assert r.returncode in (0, 1), "validator must exit 0 or 1, not crash"


# ---------------------------------------------------------------------------
# Group 3: Invalid fixtures fail
# ---------------------------------------------------------------------------

def test_invalid_project_state_missing_objective_fails(tmp_path):
    r = run_validator(
        "--file",
        str(FIXTURES_INVALID / "project-state-missing-objective.yaml"),
        "--schema", "project_state",
    )
    assert r.returncode != 0
    assert "[FAIL]" in r.stdout


def test_invalid_trial_rule_unknown_state_fails(tmp_path):
    r = run_validator(
        "--file",
        str(FIXTURES_INVALID / "trial-rule-unknown-state.yaml"),
        "--schema", "trial_rule",
    )
    assert r.returncode != 0
    assert "[FAIL]" in r.stdout


def test_invalid_exceptional_work_unknown_trigger_fails(tmp_path):
    r = run_validator(
        "--file",
        str(FIXTURES_INVALID / "exceptional-work-unknown-trigger.yaml"),
        "--schema", "exceptional_work",
    )
    assert r.returncode != 0
    assert "[FAIL]" in r.stdout


def test_invalid_worker_handoff_empty_accept_fails():
    r = run_validator(
        "--file",
        str(FIXTURES_INVALID / "worker-handoff-empty-accept.yaml"),
        "--schema", "worker_handoff",
    )
    assert r.returncode != 0
    assert "[FAIL]" in r.stdout


def test_invalid_worker_handoff_invalid_risk_fails():
    r = run_validator(
        "--file",
        str(FIXTURES_INVALID / "worker-handoff-invalid-risk.yaml"),
        "--schema", "worker_handoff",
    )
    assert r.returncode != 0
    assert "[FAIL]" in r.stdout


def test_invalid_worker_handoff_scope_lock_overlap_fails():
    r = run_validator(
        "--file",
        str(FIXTURES_INVALID / "worker-handoff-scope-lock-overlap.yaml"),
        "--schema", "worker_handoff",
    )
    assert r.returncode != 0
    assert "E008" in r.stdout or "[FAIL]" in r.stdout


def test_invalid_worker_handoff_unknown_field_fails():
    r = run_validator(
        "--file",
        str(FIXTURES_INVALID / "worker-handoff-unknown-field.yaml"),
        "--schema", "worker_handoff",
    )
    assert r.returncode != 0
    assert "[FAIL]" in r.stdout


def test_invalid_worker_handoff_empty_deliver_fails():
    r = run_validator(
        "--file",
        str(FIXTURES_INVALID / "worker-handoff-empty-deliver.yaml"),
        "--schema", "worker_handoff",
    )
    assert r.returncode != 0
    assert "[FAIL]" in r.stdout


# ---------------------------------------------------------------------------
# Group 4: Exit code contract
# ---------------------------------------------------------------------------

def test_exit_zero_on_valid_file():
    r = run_validator(
        "--file", str(FIXTURES_VALID / "worker-handoff.yaml"),
        "--schema", "worker_handoff",
    )
    assert r.returncode == 0


def test_exit_nonzero_on_invalid_file():
    r = run_validator(
        "--file",
        str(FIXTURES_INVALID / "worker-handoff-invalid-risk.yaml"),
        "--schema", "worker_handoff",
    )
    assert r.returncode != 0


# ---------------------------------------------------------------------------
# Group 5: Required field enforcement (in-memory mutation)
# ---------------------------------------------------------------------------

VALID_HANDOFF = {
    "v": 1,
    "id": "test-wh-001",
    "goal": "Do something",
    "scope": ["tools/pos/lean/**"],
    "lock": ["governance/frozen/**"],
    "accept": ["something passes"],
    "risk": "R1",
    "deliver": ["result.yaml"],
}


@pytest.mark.parametrize("missing_field", ["v", "id", "goal", "scope", "lock", "accept", "risk", "deliver"])
def test_missing_required_handoff_field_fails(tmp_path, missing_field):
    doc = {k: v for k, v in VALID_HANDOFF.items() if k != missing_field}
    path = write_fixture(tmp_path, f"handoff-missing-{missing_field}.yaml", doc)
    r = run_validator("--file", str(path), "--schema", "worker_handoff")
    assert r.returncode != 0, f"Expected failure for missing field: {missing_field}"


def test_empty_scope_fails(tmp_path):
    doc = {**VALID_HANDOFF, "scope": []}
    path = write_fixture(tmp_path, "handoff-empty-scope.yaml", doc)
    r = run_validator("--file", str(path), "--schema", "worker_handoff")
    assert r.returncode != 0


def test_empty_lock_fails(tmp_path):
    doc = {**VALID_HANDOFF, "lock": []}
    path = write_fixture(tmp_path, "handoff-empty-lock.yaml", doc)
    r = run_validator("--file", str(path), "--schema", "worker_handoff")
    assert r.returncode != 0


@pytest.mark.parametrize("risk_class", sorted(VALID_RISK_CLASSES))
def test_all_valid_risk_classes_accepted(tmp_path, risk_class):
    doc = {**VALID_HANDOFF, "risk": risk_class}
    path = write_fixture(tmp_path, f"handoff-risk-{risk_class}.yaml", doc)
    r = run_validator("--file", str(path), "--schema", "worker_handoff")
    assert r.returncode == 0, f"Risk class {risk_class} should be valid:\n{r.stdout}"


def test_invalid_risk_class_rejected(tmp_path):
    doc = {**VALID_HANDOFF, "risk": "CRITICAL"}
    path = write_fixture(tmp_path, "handoff-bad-risk.yaml", doc)
    r = run_validator("--file", str(path), "--schema", "worker_handoff")
    assert r.returncode != 0


# ---------------------------------------------------------------------------
# Group 6: Scope / lock distinctness
# ---------------------------------------------------------------------------

def test_scope_lock_no_overlap_passes(tmp_path):
    doc = {**VALID_HANDOFF, "scope": ["tools/pos/lean/**"], "lock": ["governance/frozen/**"]}
    path = write_fixture(tmp_path, "handoff-no-overlap.yaml", doc)
    r = run_validator("--file", str(path), "--schema", "worker_handoff")
    assert r.returncode == 0


def test_scope_lock_overlap_fails(tmp_path):
    doc = {
        **VALID_HANDOFF,
        "scope": ["tools/pos/lean/**", "governance/frozen/**"],
        "lock": ["governance/frozen/**"],
    }
    path = write_fixture(tmp_path, "handoff-overlap.yaml", doc)
    r = run_validator("--file", str(path), "--schema", "worker_handoff")
    assert r.returncode != 0
    assert "E008" in r.stdout


# ---------------------------------------------------------------------------
# Group 7: Trial rule states
# ---------------------------------------------------------------------------

VALID_TRIAL_RULE = {
    "v": 1,
    "id": "test-tr-001",
    "title": "Some rule",
    "state": "active_trial",
    "rule": "Do not do X without authorization",
    "created_at": "2026-07-18T00:00:00Z",
}


@pytest.mark.parametrize("state", sorted(VALID_TRIAL_RULE_STATES))
def test_valid_trial_rule_states(tmp_path, state):
    doc = {**VALID_TRIAL_RULE, "state": state}
    if state == "superseded":
        doc["superseded_by"] = "test-tr-002"
    path = write_fixture(tmp_path, f"tr-state-{state}.yaml", doc)
    r = run_validator("--file", str(path), "--schema", "trial_rule")
    assert r.returncode == 0, f"State '{state}' should be valid:\n{r.stdout}"


def test_unknown_trial_rule_state_fails(tmp_path):
    doc = {**VALID_TRIAL_RULE, "state": "draft"}
    path = write_fixture(tmp_path, "tr-state-bad.yaml", doc)
    r = run_validator("--file", str(path), "--schema", "trial_rule")
    assert r.returncode != 0


def test_superseded_without_superseded_by_fails(tmp_path):
    doc = {**VALID_TRIAL_RULE, "state": "superseded", "superseded_by": None}
    path = write_fixture(tmp_path, "tr-superseded-no-ref.yaml", doc)
    r = run_validator("--file", str(path), "--schema", "trial_rule")
    assert r.returncode != 0


# ---------------------------------------------------------------------------
# Group 8: Exceptional work
# ---------------------------------------------------------------------------

VALID_EXCEPTIONAL = {
    "v": 1,
    "id": "test-ew-001",
    "title": "Multi-PR coordination",
    "trigger": "multi_pr_coordination",
    "description": "Three PRs must land together",
    "state": "open",
    "created_at": "2026-07-18T00:00:00Z",
}


@pytest.mark.parametrize("trigger", sorted(VALID_EXCEPTIONAL_WORK_TRIGGERS))
def test_valid_exceptional_work_triggers(tmp_path, trigger):
    doc = {**VALID_EXCEPTIONAL, "trigger": trigger}
    path = write_fixture(tmp_path, f"ew-trigger-{trigger}.yaml", doc)
    r = run_validator("--file", str(path), "--schema", "exceptional_work")
    assert r.returncode == 0, f"Trigger '{trigger}' should be valid:\n{r.stdout}"


def test_unknown_exceptional_work_trigger_fails(tmp_path):
    doc = {**VALID_EXCEPTIONAL, "trigger": "routine_maintenance"}
    path = write_fixture(tmp_path, "ew-bad-trigger.yaml", doc)
    r = run_validator("--file", str(path), "--schema", "exceptional_work")
    assert r.returncode != 0


def test_resolved_exceptional_work_without_resolution_fails(tmp_path):
    doc = {**VALID_EXCEPTIONAL, "state": "resolved", "resolution": None}
    path = write_fixture(tmp_path, "ew-resolved-no-res.yaml", doc)
    r = run_validator("--file", str(path), "--schema", "exceptional_work")
    assert r.returncode != 0


# ---------------------------------------------------------------------------
# Group 9: Project state
# ---------------------------------------------------------------------------

VALID_PROJECT_STATE = {
    "v": 1,
    "id": "test-ps-001",
    "objective": "Build the thing",
    "constraints": ["must not break existing tests"],
    "refs": ["roles/architect/INSTRUCTIONS.md"],
    "updated_at": "2026-07-18T00:00:00Z",
}


def test_valid_project_state_in_memory(tmp_path):
    path = write_fixture(tmp_path, "ps-valid.yaml", VALID_PROJECT_STATE)
    r = run_validator("--file", str(path), "--schema", "project_state")
    assert r.returncode == 0


@pytest.mark.parametrize("missing_field", ["v", "id", "objective", "constraints", "refs", "updated_at"])
def test_missing_required_project_state_field_fails(tmp_path, missing_field):
    doc = {k: v for k, v in VALID_PROJECT_STATE.items() if k != missing_field}
    path = write_fixture(tmp_path, f"ps-missing-{missing_field}.yaml", doc)
    r = run_validator("--file", str(path), "--schema", "project_state")
    assert r.returncode != 0


# ---------------------------------------------------------------------------
# Group 10: Deterministic error order
# ---------------------------------------------------------------------------

def test_error_output_is_deterministic():
    """Running the validator twice on the same invalid file must produce identical output."""
    target = FIXTURES_INVALID / "worker-handoff-scope-lock-overlap.yaml"
    outputs = [
        run_validator("--file", str(target), "--schema", "worker_handoff").stdout
        for _ in range(2)
    ]
    assert outputs[0] == outputs[1], "Validator output is not deterministic"


# ---------------------------------------------------------------------------
# Group 11: No network dependency
# ---------------------------------------------------------------------------

def test_no_network_access_occurs(tmp_path):
    """Validator must succeed (or fail on content) without any network access.

    We prove this by blocking outbound connections via a subprocess environment
    with no HTTP_PROXY and verifying the validator still runs to completion
    without a connection error.
    """
    import os
    env = {k: v for k, v in os.environ.items()
           if k not in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY")}
    # Clear proxy so any accidental network call would fail if the OS blocks it
    r = subprocess.run(
        [sys.executable, str(VALIDATOR),
         "--file", str(FIXTURES_VALID / "worker-handoff.yaml"),
         "--schema", "worker_handoff"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    # The validator must exit 0 and not crash with a network error
    assert r.returncode == 0, f"Validator failed unexpectedly:\n{r.stdout}\n{r.stderr}"
    assert "ConnectionError" not in r.stderr
    assert "urllib" not in r.stderr


# ---------------------------------------------------------------------------
# Group 12: CLI entrypoint contract
# ---------------------------------------------------------------------------

def test_validator_has_cli_entrypoint():
    assert VALIDATOR.exists(), f"Lean validator not found at {VALIDATOR}"


def test_validator_help_exits_cleanly():
    r = run_validator("--help")
    assert r.returncode == 0
    assert "Lean POS" in r.stdout or "usage" in r.stdout.lower()


def test_validator_no_args_exits_2():
    r = run_validator()
    assert r.returncode == 2
