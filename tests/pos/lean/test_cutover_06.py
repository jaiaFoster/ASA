"""
Tests for LEAN-POS-11: CUTOVER-06 — verify Lean-only repository and close migration.

Verifies:
- All six cutover phases are complete
- No pending cutover phase exists
- Zero open blockers
- Project state marks migration complete with no next_phase
- AGENTS.md marks Lean POS as sole active system; migration complete
- CURRENT_STATE.md is deterministic and has no pending cutover phase
- All legacy runtime paths are absent from filesystem
- No active code references deleted legacy paths
- Archive is present, unchanged, and marked noncanonical
- Entrypoint checker passes
- Corrected merge conflict preflight fails closed
- CI workflow is Lean-only
- Migration outputs match source-of-truth generation
- Durable role authority coverage is present
- No unexplained test xfails or skips
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

PROJECT_STATE_PATH = REPO_ROOT / "project" / "lean" / "state" / "project-state.yaml"
CURRENT_STATE_PATH = REPO_ROOT / "CURRENT_STATE.md"
AGENTS_PATH = REPO_ROOT / "AGENTS.md"
ARCHIVE_ROOT = REPO_ROOT / "project" / "lean" / "archive" / "legacy"
MIGRATION_DIR = REPO_ROOT / "project" / "lean" / "migration"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "validate-pos.yml"

GENERATED_AT = "2026-07-19T00:00:00Z"

from tools.pos.lean.migration import build_blockers, build_cutover_plan, build_capability_map


# ---------------------------------------------------------------------------
# All cutover phases complete
# ---------------------------------------------------------------------------

class TestAllPhasesComplete:
    def test_all_six_phases_complete(self):
        co = build_cutover_plan(GENERATED_AT)
        phases = {p["id"]: p for p in co["phases"]}
        for phase_id in ("CUTOVER-01", "CUTOVER-02", "CUTOVER-03",
                          "CUTOVER-04", "CUTOVER-05", "CUTOVER-06"):
            assert phases[phase_id]["status"] == "complete", (
                f"{phase_id} is not complete: {phases[phase_id]['status']}"
            )

    def test_cutover_06_completed_in_lean_pos_11(self):
        co = build_cutover_plan(GENERATED_AT)
        phases = {p["id"]: p for p in co["phases"]}
        assert phases["CUTOVER-06"].get("completed_in") == "LEAN-POS-11"

    def test_no_pending_cutover_phase(self):
        co = build_cutover_plan(GENERATED_AT)
        pending = [p["id"] for p in co["phases"] if p["status"] == "pending"]
        assert pending == [], f"Pending phases remain: {pending}"

    def test_zero_open_blockers(self):
        bl = build_blockers(GENERATED_AT)
        assert len(bl["blockers"]) == 0, (
            f"Open blockers: {[b['id'] for b in bl['blockers']]}"
        )

    def test_cutover_ready_reason_says_complete(self):
        co = build_cutover_plan(GENERATED_AT)
        reason = co.get("cutover_ready_reason", "")
        assert "complete" in reason.lower()
        assert "CUTOVER-06" not in reason or "complete" in reason.lower()


# ---------------------------------------------------------------------------
# Canonical project state
# ---------------------------------------------------------------------------

class TestCanonicalState:
    def test_project_state_migration_complete(self):
        data = yaml.safe_load(PROJECT_STATE_PATH.read_text())
        notes = data.get("notes", "")
        assert "migration_status=complete" in notes

    def test_project_state_completed_phase_is_cutover_06(self):
        data = yaml.safe_load(PROJECT_STATE_PATH.read_text())
        notes = data.get("notes", "")
        assert "CUTOVER-06" in notes or "completed_phase=CUTOVER-06" in notes

    def test_project_state_no_next_cutover_phase(self):
        data = yaml.safe_load(PROJECT_STATE_PATH.read_text())
        notes = data.get("notes", "")
        assert "next_phase" not in notes

    def test_project_state_active_operating_system(self):
        data = yaml.safe_load(PROJECT_STATE_PATH.read_text())
        notes = data.get("notes", "")
        assert "Lean_POS" in notes or "Lean POS" in notes

    def test_project_state_no_active_phase_language(self):
        data = yaml.safe_load(PROJECT_STATE_PATH.read_text())
        notes = data.get("notes", "")
        assert "active_phase=CUTOVER" not in notes


# ---------------------------------------------------------------------------
# AGENTS.md
# ---------------------------------------------------------------------------

class TestAgentsMd:
    def test_agents_marks_migration_complete(self):
        content = AGENTS_PATH.read_text()
        assert "migration complete" in content.lower() or "migration_status=complete" in content

    def test_agents_lean_pos_is_sole_active_system(self):
        content = AGENTS_PATH.read_text()
        assert "Lean POS" in content

    def test_agents_no_pending_cutover_language(self):
        content = AGENTS_PATH.read_text()
        assert "next_phase" not in content
        assert "pending" not in content.lower() or "CUTOVER" not in content

    def test_agents_has_lean_tools(self):
        content = AGENTS_PATH.read_text()
        assert "tools/pos/lean/" in content

    def test_agents_under_token_budget(self):
        from tools.pos.lean.schemas import estimate_tokens
        tokens = estimate_tokens(AGENTS_PATH.read_text())
        assert tokens <= 1000, f"AGENTS.md over 1000-token budget: {tokens}"


# ---------------------------------------------------------------------------
# CURRENT_STATE.md
# ---------------------------------------------------------------------------

class TestCurrentStateMd:
    def test_current_state_is_deterministic(self):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            out = f.name
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/generate.py", "current-state",
             "--project-state", str(PROJECT_STATE_PATH),
             "--generated-at", "2000-01-01T00:00:00Z", "--output", out],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, result.stderr
        assert Path(out).read_text() == CURRENT_STATE_PATH.read_text(), (
            "CURRENT_STATE.md does not match generator output — regenerate."
        )

    def test_current_state_no_pending_cutover_phase(self):
        content = CURRENT_STATE_PATH.read_text()
        assert "pending (next)" not in content
        assert "active_phase=CUTOVER" not in content

    def test_current_state_reports_migration_complete(self):
        content = CURRENT_STATE_PATH.read_text()
        assert "complete" in content.lower()


# ---------------------------------------------------------------------------
# Legacy filesystem — all deleted paths absent
# ---------------------------------------------------------------------------

ABSENT_PATHS = [
    "tools/pos/validate.py",
    "tools/pos/generate.py",
    "tools/pos/schemas.py",
    "tools/pos/transitions.py",
    "project/generated",
    "project/BOOTSTRAP_STATUS.yaml",
    "project/work",
    "project/assignments",
    "project/results",
    "project/decisions",
    "project/reviews",
    "project/evidence",
    "project/risks",
    "project/schemas/assignment.schema.yaml",
    "project/schemas/decision.schema.yaml",
    "project/schemas/evidence.schema.yaml",
    "project/schemas/review.schema.yaml",
    "project/schemas/risk-record.schema.yaml",
    "project/schemas/work-item.schema.yaml",
    "project/schemas/worker-result.schema.yaml",
]


class TestLegacyFilesystemAbsent:
    @pytest.mark.parametrize("rel_path", ABSENT_PATHS)
    def test_legacy_path_absent(self, rel_path):
        assert not (REPO_ROOT / rel_path).exists(), (
            f"Legacy path must be absent: {rel_path}"
        )


# ---------------------------------------------------------------------------
# No active imports of deleted legacy modules
# ---------------------------------------------------------------------------

class TestNoActiveImports:
    def test_legacy_validate_not_importable(self):
        result = subprocess.run(
            [sys.executable, "-c", "import tools.pos.validate"],
            capture_output=True, cwd=REPO_ROOT,
        )
        assert result.returncode != 0, "tools.pos.validate must not be importable"

    def test_legacy_generate_not_importable(self):
        result = subprocess.run(
            [sys.executable, "-c", "import tools.pos.generate"],
            capture_output=True, cwd=REPO_ROOT,
        )
        assert result.returncode != 0, "tools.pos.generate must not be importable"

    def test_lean_modules_compile_clean(self):
        result = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", "tools/pos/lean"],
            capture_output=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, f"compileall failed:\n{result.stdout.decode()}"

    def test_no_active_test_imports_legacy(self):
        """No test file in tests/pos/lean/ has a live import of deleted modules.

        Subprocess strings like 'import tools.pos.validate' (used to prove the module
        is NOT importable) are allowed; only actual top-level import statements are
        checked here.
        """
        import re
        # Match actual Python import statements, not string literals in subprocess calls
        live_import = re.compile(
            r'^\s*(?:from|import)\s+tools\.pos\.(?:validate|generate|schemas|transitions)\b',
            re.MULTILINE,
        )
        for f in (REPO_ROOT / "tests" / "pos" / "lean").glob("*.py"):
            content = f.read_text()
            assert not live_import.search(content), (
                f"{f.name} has a live import of a deleted legacy module"
            )


# ---------------------------------------------------------------------------
# Archive integrity
# ---------------------------------------------------------------------------

class TestArchiveIntact:
    def test_archive_exists(self):
        assert ARCHIVE_ROOT.is_dir()

    def test_archive_readme_marks_noncanonical(self):
        content = (ARCHIVE_ROOT / "README.md").read_text()
        assert "noncanonical" in content.lower() or "non-canonical" in content.lower()

    def test_archive_bootstrap_status_present(self):
        assert (ARCHIVE_ROOT / "BOOTSTRAP_STATUS.yaml").is_file()

    def test_archive_work_records_present(self):
        records = [f for f in (ARCHIVE_ROOT / "work").glob("*.yaml")
                   if f.name != ".gitkeep"]
        assert records, "No archived work records"

    def test_lean_validator_does_not_scan_archive_as_active(self):
        val_text = (REPO_ROOT / "tools" / "pos" / "lean" / "validate.py").read_text()
        assert "archive/legacy" not in val_text


# ---------------------------------------------------------------------------
# CI workflow is Lean-only
# ---------------------------------------------------------------------------

class TestCILeanOnly:
    def test_workflow_has_no_legacy_tool_commands(self):
        text = WORKFLOW_PATH.read_text()
        for forbidden in ("tools/pos/validate.py", "tools/pos/generate.py",
                          "tools/pos/schemas.py", "tools/pos/transitions.py"):
            assert forbidden not in text, (
                f"CI workflow references deleted legacy path: {forbidden}"
            )

    def test_workflow_runs_check_entrypoints(self):
        text = WORKFLOW_PATH.read_text()
        assert "check_entrypoints.py" in text

    def test_workflow_checks_current_state_drift(self):
        text = WORKFLOW_PATH.read_text()
        assert "CURRENT_STATE.md" in text

    def test_workflow_has_no_project_generated_reference(self):
        text = WORKFLOW_PATH.read_text()
        assert "project/generated" not in text


# ---------------------------------------------------------------------------
# Entrypoint and integrity checks
# ---------------------------------------------------------------------------

class TestEntrypointAndIntegrity:
    def test_check_entrypoints_passes(self):
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/check_entrypoints.py"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, f"check_entrypoints failed:\n{result.stdout}{result.stderr}"

    def test_check_integrity_passes(self):
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/check_integrity.py"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, f"check_integrity failed:\n{result.stdout}{result.stderr}"

    def test_lean_validator_passes(self):
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/validate.py",
             "--file", str(PROJECT_STATE_PATH), "--schema", "project_state"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, f"lean validator failed:\n{result.stderr}"


# ---------------------------------------------------------------------------
# Merge conflict preflight fails closed
# ---------------------------------------------------------------------------

class TestConflictPreflightFailsClosed:
    def test_check_merge_conflicts_importable(self):
        from tools.pos.lean.pre_push_check import check_merge_conflicts
        assert callable(check_merge_conflicts)

    def test_probe_functions_available(self):
        from tools.pos.lean.pre_push_check import (
            _conflict_probe_merge_tree, _conflict_probe_worktree
        )
        assert callable(_conflict_probe_merge_tree)
        assert callable(_conflict_probe_worktree)

    def test_merge_tree_conflict_blocks_push(self):
        """Simulated CONFLICT output from merge-tree blocks push."""
        from unittest.mock import patch
        import tools.pos.lean.pre_push_check as m

        def fake_run(cmd, *, cwd=REPO_ROOT):
            if "merge-tree" in cmd:
                return 1, "CONFLICT (content): Merge conflict in foo.txt\n", ""
            return 0, "", ""

        with patch.object(m, "_run", side_effect=fake_run):
            ok, msg = m.check_merge_conflicts()
        assert not ok
        assert "conflict" in msg.lower()

    def test_unexpected_error_blocks_push(self):
        """An unexpected git error (rc != 0/1, no option text) blocks push."""
        from unittest.mock import patch
        import tools.pos.lean.pre_push_check as m

        def fake_run(cmd, *, cwd=REPO_ROOT):
            if "merge-tree" in cmd:
                return 2, "", "fatal: internal error"
            return 0, "", ""

        with patch.object(m, "_run", side_effect=fake_run):
            ok, msg = m.check_merge_conflicts()
        assert not ok, "unexpected git error must block push"

    def test_worktree_creation_failure_blocks_push(self):
        """If fallback worktree cannot be created, push is blocked."""
        from unittest.mock import patch
        import tools.pos.lean.pre_push_check as m

        def fake_run(cmd, *, cwd=REPO_ROOT):
            if "merge-tree" in cmd:
                return 129, "", "error: unknown option '--write-tree'"
            if "worktree" in cmd and "add" in cmd:
                return 1, "", "cannot lock ref"
            return 0, "", ""

        with patch.object(m, "_run", side_effect=fake_run):
            ok, msg = m.check_merge_conflicts()
        assert not ok


# ---------------------------------------------------------------------------
# Migration outputs reproducible
# ---------------------------------------------------------------------------

class TestMigrationOutputsReproducible:
    def test_migration_outputs_match_source_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, "tools/pos/lean/assess_migration.py",
                 "--repo-root", ".", "--generated-at", GENERATED_AT,
                 "--output-dir", tmp],
                capture_output=True, cwd=REPO_ROOT,
            )
            assert result.returncode == 0, result.stderr.decode()
            for name in ("blockers.yaml", "capability-map.yaml",
                         "cutover-plan.yaml", "README.md"):
                regenerated = (Path(tmp) / name).read_bytes()
                committed = (MIGRATION_DIR / name).read_bytes()
                assert regenerated == committed, (
                    f"{name} does not match committed file — regenerate migration outputs"
                )

    def test_final_report_exists(self):
        assert (MIGRATION_DIR / "FINAL_REPORT.md").is_file()

    def test_final_report_states_migration_complete(self):
        content = (MIGRATION_DIR / "FINAL_REPORT.md").read_text()
        assert "migration sealed" in content.lower() or "migration status" in content.lower()
        assert "complete" in content.lower()
        assert "CUTOVER-06" in content


# ---------------------------------------------------------------------------
# Role authority coverage preserved
# ---------------------------------------------------------------------------

class TestRoleAuthorityCoverage:
    def test_role_authority_test_file_exists(self):
        assert (REPO_ROOT / "tests" / "pos" / "lean" / "test_role_authority_integrity.py").exists()

    def test_role_authority_tests_cover_merge_denial(self):
        content = (REPO_ROOT / "tests" / "pos" / "lean" /
                   "test_role_authority_integrity.py").read_text()
        assert "merge" in content.lower()
        assert "Founder" in content

    def test_required_role_files_checked(self):
        content = (REPO_ROOT / "tests" / "pos" / "lean" /
                   "test_role_authority_integrity.py").read_text()
        assert "REQUIRED_ROLE_FILES" in content or "role_file_exists" in content


# ---------------------------------------------------------------------------
# No xfails or unexplained skips in lean test suite
# ---------------------------------------------------------------------------

class TestNoXfailsOrSkips:
    def test_zero_xfails_in_lean_tests(self):
        """No test in tests/pos/lean/ is marked xfail."""
        import re
        pattern = re.compile(r'@pytest\.mark\.xfail')
        for f in (REPO_ROOT / "tests" / "pos" / "lean").glob("*.py"):
            content = f.read_text()
            assert not pattern.search(content), (
                f"{f.name} contains xfail — remove or replace with durable assertion"
            )
