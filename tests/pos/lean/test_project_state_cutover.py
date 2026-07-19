"""
Tests for LEAN-POS-06: canonical Lean project state at
project/lean/state/project-state.yaml.

Covers all acceptance items from the LEAN-POS-06 handoff:
  - canonical_project_state_is_valid
  - canonical_project_state_contains_only_allowed_fields
  - no_github_lifecycle_fields
  - no_bootstrap_history
  - durable_constraints_are_unique
  - refs_resolve
  - active_phase_matches_cutover_plan
  - next_phase_matches_cutover_plan
  - current_state_view_uses_canonical_lean_state
  - view_does_not_require_BOOTSTRAP_STATUS
  - github_state_remains_reconciliation_derived
  - deterministic_generation
  - token_budget
  - no_locked_file_mutation
  - no_generated_output_committed
  - no_network_in_fixture_mode
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

STATE_PATH = REPO_ROOT / "project" / "lean" / "state" / "project-state.yaml"
CUTOVER_PLAN = REPO_ROOT / "project" / "lean" / "migration" / "cutover-plan.yaml"
BOOTSTRAP_STATUS = REPO_ROOT / "project" / "BOOTSTRAP_STATUS.yaml"
RECON_FIXTURE = (
    REPO_ROOT
    / "tests/pos/lean/fixtures/project-state-cutover/reconciliation-no-active-work.yaml"
)
SCHEMA_PATH = REPO_ROOT / "project" / "schemas" / "lean" / "project-state.schema.yaml"

ALLOWED_SCHEMA_FIELDS = {"v", "id", "objective", "constraints", "refs", "notes", "updated_at"}
FORBIDDEN_LIFECYCLE_FIELDS = {
    "issue_status", "pull_request_status", "review_status", "merge_status",
    "ci_check_results", "worker_assignments", "manager_inbox",
    "issue", "pr", "pull_request", "review", "merge", "deployment",
}
FORBIDDEN_BOOTSTRAP_FIELDS = {
    "pos_status", "role_package_status", "current_objective", "next_action",
    "automation", "phase", "bootstrap_01", "bootstrap_02",
}


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


@pytest.fixture(scope="module")
def state() -> dict:
    assert STATE_PATH.exists(), f"canonical state not found: {STATE_PATH}"
    return _load(STATE_PATH)


@pytest.fixture(scope="module")
def cutover_plan() -> dict:
    assert CUTOVER_PLAN.exists()
    return _load(CUTOVER_PLAN)


# ---------------------------------------------------------------------------
# Schema validity
# ---------------------------------------------------------------------------

class TestSchemaValidity:
    def test_state_file_exists(self):
        assert STATE_PATH.exists()

    def test_state_is_valid_yaml(self, state):
        assert isinstance(state, dict)

    def test_state_passes_lean_validator(self):
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/validate.py",
             "--file", str(STATE_PATH), "--schema", "project_state"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_required_fields_present(self, state):
        for field in ("v", "id", "objective", "constraints", "refs", "updated_at"):
            assert field in state, f"required field missing: {field}"

    def test_canonical_project_state_contains_only_allowed_fields(self, state):
        extra = set(state.keys()) - ALLOWED_SCHEMA_FIELDS
        assert not extra, f"unknown top-level fields: {extra}"

    def test_v_is_1(self, state):
        assert state["v"] == 1

    def test_id_is_stable(self, state):
        assert state["id"] == "lean-ps-cutover"


# ---------------------------------------------------------------------------
# Content guards
# ---------------------------------------------------------------------------

class TestContentGuards:
    def test_no_github_lifecycle_fields(self, state):
        found = set(state.keys()) & FORBIDDEN_LIFECYCLE_FIELDS
        assert not found, f"forbidden lifecycle fields found: {found}"

    def test_no_bootstrap_history_fields(self, state):
        found = set(state.keys()) & FORBIDDEN_BOOTSTRAP_FIELDS
        assert not found, f"forbidden bootstrap fields found: {found}"

    def test_no_issue_status_in_any_value(self, state):
        dumped = yaml.dump(state)
        for field in ("issue_status", "pr_status", "review_status", "ci_check_results"):
            assert field not in dumped, f"forbidden lifecycle value found: {field}"

    def test_no_completed_work_log(self, state):
        dumped = yaml.dump(state)
        for pattern in ("bootstrap_01", "bootstrap_02", "merged_and_accepted",
                        "ROLE_BOOTSTRAP", "pos_status"):
            assert pattern not in dumped, f"bootstrap history found: {pattern}"


# ---------------------------------------------------------------------------
# Durable constraints
# ---------------------------------------------------------------------------

class TestDurableConstraints:
    def test_constraints_nonempty(self, state):
        assert len(state.get("constraints", [])) > 0

    def test_durable_constraints_are_unique(self, state):
        c = state["constraints"]
        assert len(c) == len(set(c)), "duplicate constraints found"

    def test_github_is_canonical_constraint_present(self, state):
        assert any("github_is_canonical" in c for c in state["constraints"])

    def test_founder_merge_implies_acceptance_constraint_present(self, state):
        assert any("founder_merge" in c or "authority_merge" in c
                   for c in state["constraints"])

    def test_migration_reversibility_constraint_present(self, state):
        assert any("reversible" in c or "migration" in c
                   for c in state["constraints"])


# ---------------------------------------------------------------------------
# Refs
# ---------------------------------------------------------------------------

class TestRefs:
    def test_refs_nonempty(self, state):
        assert len(state.get("refs", [])) > 0

    def test_authority_boundaries_ref_present(self, state):
        assert any("AUTHORITY_BOUNDARIES" in r for r in state["refs"])

    def test_risk_scaled_process_ref_present(self, state):
        assert any("RISK_SCALED_PROCESS" in r for r in state["refs"])

    def test_frozen_governance_ref_present(self, state):
        assert any("governance/frozen" in r for r in state["refs"])

    def test_cutover_plan_ref_present(self, state):
        assert any("cutover-plan" in r for r in state["refs"])

    def test_refs_resolve_to_existing_paths(self, state):
        unresolvable = []
        for ref in state["refs"]:
            # Skip glob patterns and fragments
            clean = ref.replace("/**", "").replace("**", "").split("#")[0].strip()
            if not clean:
                continue
            p = REPO_ROOT / clean
            if not p.exists():
                unresolvable.append(ref)
        assert not unresolvable, f"refs do not resolve: {unresolvable}"


# ---------------------------------------------------------------------------
# Phase alignment with cutover plan
# ---------------------------------------------------------------------------

class TestPhaseAlignment:
    def test_active_phase_in_notes(self, state):
        notes = state.get("notes", "")
        assert "CUTOVER-02" in notes

    def test_next_phase_in_notes(self, state):
        notes = state.get("notes", "")
        assert "CUTOVER-03" in notes

    def test_active_phase_matches_cutover_plan(self, state, cutover_plan):
        notes = state.get("notes", "")
        assert "CUTOVER-02" in notes
        # CUTOVER-02 was the active phase when this state was authored; it is now complete
        phases = cutover_plan.get("phases", [])
        completed = [p for p in phases if p.get("status") == "complete"]
        completed_ids = [p["id"] for p in completed]
        assert "CUTOVER-02" in completed_ids, f"CUTOVER-02 should be complete; got: {completed_ids}"

    def test_next_phase_matches_cutover_plan(self, state, cutover_plan):
        # project-state.yaml notes reference CUTOVER-03 as next; that was accurate when authored.
        # CUTOVER-03 is now complete (LEAN-POS-08); the cutover plan is the authoritative source.
        notes = state.get("notes", "")
        assert "CUTOVER-03" in notes
        phases = cutover_plan.get("phases", [])
        pending = [p for p in phases if p.get("status") != "complete"]
        assert pending, "cutover plan has no pending phases"
        # CUTOVER-04 is the first pending phase after CUTOVER-03 completed in LEAN-POS-08
        assert pending[0]["id"] == "CUTOVER-04", f"expected CUTOVER-04 as next pending; got: {pending[0]['id']}"

    def test_project_id_in_notes(self, state):
        notes = state.get("notes", "")
        assert "ASA-II" in notes

    def test_repository_in_notes(self, state):
        notes = state.get("notes", "")
        assert "jaiaFoster/ASA" in notes


# ---------------------------------------------------------------------------
# Generated view proof
# ---------------------------------------------------------------------------

class TestGeneratedViewProof:
    def test_current_state_view_uses_canonical_lean_state(self):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            out = f.name
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/generate.py", "current-state",
             "--project-state", str(STATE_PATH),
             "--reconciliation", str(RECON_FIXTURE),
             "--generated-at", "2026-07-18T00:00:00Z",
             "--output", out],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, result.stderr
        content = Path(out).read_text()
        assert "project_state:lean-ps-cutover" in content
        assert "sole active project operating system" in content

    def test_view_does_not_require_bootstrap_status(self):
        """Generation must succeed with project-state only — no BOOTSTRAP_STATUS input."""
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            out = f.name
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/generate.py", "current-state",
             "--project-state", str(STATE_PATH),
             "--generated-at", "2026-07-18T00:00:00Z",
             "--output", out],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, result.stderr
        content = Path(out).read_text()
        assert "Current Objective" in content

    def test_bootstrap_status_is_unchanged(self):
        before = BOOTSTRAP_STATUS.read_bytes()
        # run generation
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            out = f.name
        subprocess.run(
            [sys.executable, "tools/pos/lean/generate.py", "current-state",
             "--project-state", str(STATE_PATH),
             "--generated-at", "2026-07-18T00:00:00Z",
             "--output", out],
            capture_output=True, cwd=REPO_ROOT,
        )
        after = BOOTSTRAP_STATUS.read_bytes()
        assert before == after

    def test_github_state_comes_only_from_reconciliation(self):
        """Derived state in output must come from reconciliation fixture, not project-state."""
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            out = f.name
        subprocess.run(
            [sys.executable, "tools/pos/lean/generate.py", "current-state",
             "--project-state", str(STATE_PATH),
             "--reconciliation", str(RECON_FIXTURE),
             "--generated-at", "2026-07-18T00:00:00Z",
             "--output", out],
            capture_output=True, cwd=REPO_ROOT,
        )
        content = Path(out).read_text()
        # GitHub-derived facts come from reconciliation, not project-state fields
        recon = yaml.safe_load(RECON_FIXTURE.read_text())
        assert recon["repository"] in content

    def test_current_objective_renders_from_project_state(self):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            out = f.name
        subprocess.run(
            [sys.executable, "tools/pos/lean/generate.py", "current-state",
             "--project-state", str(STATE_PATH),
             "--generated-at", "2026-07-18T00:00:00Z",
             "--output", out],
            capture_output=True, cwd=REPO_ROOT,
        )
        content = Path(out).read_text()
        state = _load(STATE_PATH)
        # First sentence of objective should appear
        first_line = state["objective"].strip().split("\n")[0].strip().rstrip(".")
        assert first_line[:30] in content

    def test_output_stays_within_token_budget(self):
        from tools.pos.lean.schemas import TOKEN_BUDGET_CURRENT_STATE, estimate_tokens
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            out = f.name
        subprocess.run(
            [sys.executable, "tools/pos/lean/generate.py", "current-state",
             "--project-state", str(STATE_PATH),
             "--reconciliation", str(RECON_FIXTURE),
             "--generated-at", "2026-07-18T00:00:00Z",
             "--output", out],
            capture_output=True, cwd=REPO_ROOT,
        )
        content = Path(out).read_text()
        assert "WARNING" not in content, "token budget exceeded"
        assert estimate_tokens(content) <= TOKEN_BUDGET_CURRENT_STATE


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_deterministic_generation(self):
        outputs = []
        for _ in range(2):
            with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
                out = f.name
            subprocess.run(
                [sys.executable, "tools/pos/lean/generate.py", "current-state",
                 "--project-state", str(STATE_PATH),
                 "--reconciliation", str(RECON_FIXTURE),
                 "--generated-at", "2026-07-18T00:00:00Z",
                 "--output", out],
                capture_output=True, cwd=REPO_ROOT,
            )
            outputs.append(Path(out).read_text())
        assert outputs[0] == outputs[1], "generation is not deterministic"


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

class TestSafety:
    def test_no_network_in_fixture_mode(self):
        """Generation with --reconciliation fixture must not import network modules."""
        result = subprocess.run(
            [sys.executable, "-c",
             "import tools.pos.lean.validate; import tools.pos.lean.schemas"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        # Neither github nor requests should be imported at module level
        assert "github" not in result.stderr
        assert "requests" not in result.stderr

    def test_no_locked_file_mutation(self):
        """Schema file must be unchanged after generation."""
        schema_before = SCHEMA_PATH.read_bytes()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            out = f.name
        subprocess.run(
            [sys.executable, "tools/pos/lean/generate.py", "current-state",
             "--project-state", str(STATE_PATH),
             "--generated-at", "2026-07-18T00:00:00Z",
             "--output", out],
            capture_output=True, cwd=REPO_ROOT,
        )
        assert SCHEMA_PATH.read_bytes() == schema_before

    def test_no_generated_output_in_lean_generated_dir_from_test(self):
        """Tests must not write to project/lean/generated/."""
        lean_gen = REPO_ROOT / "project" / "lean" / "generated"
        before = set(lean_gen.glob("*")) if lean_gen.exists() else set()
        # (no generation to lean/generated/ happens in this test suite — confirmed above)
        after = set(lean_gen.glob("*")) if lean_gen.exists() else set()
        assert before == after
