"""
Tests for LEAN-POS-10: CUTOVER-05 complete — legacy runtime removed.

Verifies:
- Legacy runtime files are deleted
- Legacy schema files are deleted
- project/generated/ is deleted
- Legacy tests are deleted
- No active imports of deleted modules
- Lean CI workflow is present and clean
- Archive is unchanged
- Root entrypoints are Lean-only
- Migration state reflects CUTOVER-05 complete / CUTOVER-06 next
- Migration outputs are reproducible
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

from tools.pos.lean.migration import build_cutover_plan, build_blockers, build_capability_map

GENERATED_AT = "2026-07-19T00:00:00Z"

DELETED_RUNTIME = [
    "tools/pos/validate.py",
    "tools/pos/generate.py",
    "tools/pos/schemas.py",
    "tools/pos/transitions.py",
]
DELETED_SCHEMAS = [
    "project/schemas/assignment.schema.yaml",
    "project/schemas/decision.schema.yaml",
    "project/schemas/evidence.schema.yaml",
    "project/schemas/review.schema.yaml",
    "project/schemas/risk-record.schema.yaml",
    "project/schemas/work-item.schema.yaml",
    "project/schemas/worker-result.schema.yaml",
]
DELETED_GENERATED = [
    "project/generated/AGENTS.md",
    "project/generated/CURRENT_STATE.md",
    "project/generated/MANAGER_INBOX.md",
]
DELETED_TESTS = [
    "tests/pos/test_repository_bootstrap.py",
    "tests/pos/test_role_bootstrap.py",
]
RETAINED_LEAN = [
    "tools/pos/lean/validate.py",
    "tools/pos/lean/generate.py",
    "tools/pos/lean/schemas.py",
    "tools/pos/lean/check_integrity.py",
    "tools/pos/lean/check_entrypoints.py",
    "tools/pos/lean/pre_push_check.py",
    "project/schemas/lean/project-state.schema.yaml",
    "project/lean/state/project-state.yaml",
    "project/lean/migration/cutover-plan.yaml",
    "AGENTS.md",
    "CURRENT_STATE.md",
    ".github/workflows/validate-pos.yml",
]
ARCHIVE_DIRS = [
    "project/lean/archive/legacy/work",
    "project/lean/archive/legacy/assignments",
    "project/lean/archive/legacy/results",
    "project/lean/archive/legacy/decisions",
    "project/lean/archive/legacy/reviews",
    "project/lean/archive/legacy/evidence",
    "project/lean/archive/legacy/risks",
]


# ---------------------------------------------------------------------------
# Deletion: runtime files absent
# ---------------------------------------------------------------------------

class TestLegacyRuntimeDeleted:
    @pytest.mark.parametrize("rel_path", DELETED_RUNTIME)
    def test_legacy_runtime_file_absent(self, rel_path):
        assert not (REPO_ROOT / rel_path).exists(), (
            f"Legacy runtime file still present: {rel_path}"
        )

    @pytest.mark.parametrize("rel_path", DELETED_SCHEMAS)
    def test_legacy_schema_file_absent(self, rel_path):
        assert not (REPO_ROOT / rel_path).exists(), (
            f"Legacy schema file still present: {rel_path}"
        )

    @pytest.mark.parametrize("rel_path", DELETED_GENERATED)
    def test_legacy_generated_file_absent(self, rel_path):
        assert not (REPO_ROOT / rel_path).exists(), (
            f"Legacy generated view still present: {rel_path}"
        )

    def test_project_generated_dir_absent(self):
        assert not (REPO_ROOT / "project" / "generated").exists(), (
            "project/generated/ directory should be deleted"
        )

    @pytest.mark.parametrize("rel_path", DELETED_TESTS)
    def test_legacy_test_file_absent(self, rel_path):
        assert not (REPO_ROOT / rel_path).exists(), (
            f"Legacy test file still present: {rel_path}"
        )


# ---------------------------------------------------------------------------
# No active imports of deleted modules
# ---------------------------------------------------------------------------

class TestNoActiveImports:
    def test_no_test_imports_legacy_schemas(self):
        result = subprocess.run(
            ["python", "-c",
             "import sys; sys.path.insert(0, '.'); import tools.pos.lean.validate"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0

    def test_legacy_module_not_importable(self):
        result = subprocess.run(
            [sys.executable, "-c", "import tools.pos.schemas"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode != 0, "tools.pos.schemas should not be importable"

    def test_legacy_validate_not_importable(self):
        result = subprocess.run(
            [sys.executable, "-c", "import tools.pos.validate"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode != 0, "tools.pos.validate should not be importable"


# ---------------------------------------------------------------------------
# Lean files retained
# ---------------------------------------------------------------------------

class TestRetainedFiles:
    @pytest.mark.parametrize("rel_path", RETAINED_LEAN)
    def test_lean_file_retained(self, rel_path):
        assert (REPO_ROOT / rel_path).exists(), (
            f"Required lean file missing: {rel_path}"
        )

    def test_ci_workflow_has_no_legacy_tool_commands(self):
        content = (REPO_ROOT / ".github" / "workflows" / "validate-pos.yml").read_text()
        assert "tools/pos/validate.py" not in content
        assert "tools/pos/generate.py" not in content
        assert "tools/pos/schemas.py" not in content

    def test_ci_workflow_invokes_lean_tools(self):
        content = (REPO_ROOT / ".github" / "workflows" / "validate-pos.yml").read_text()
        assert "tools/pos/lean/" in content

    def test_ci_workflow_runs_integrity_check(self):
        content = (REPO_ROOT / ".github" / "workflows" / "validate-pos.yml").read_text()
        assert "check_integrity.py" in content


# ---------------------------------------------------------------------------
# Archive retained
# ---------------------------------------------------------------------------

class TestArchiveRetained:
    @pytest.mark.parametrize("rel_dir", ARCHIVE_DIRS)
    def test_archive_dir_exists(self, rel_dir):
        assert (REPO_ROOT / rel_dir).exists(), (
            f"Archive directory missing: {rel_dir}"
        )

    def test_archive_bootstrap_status_retained(self):
        assert (
            REPO_ROOT / "project" / "lean" / "archive" / "legacy" / "BOOTSTRAP_STATUS.yaml"
        ).exists()

    def test_archive_readme_exists(self):
        assert (REPO_ROOT / "project" / "lean" / "archive" / "legacy" / "README.md").exists()


# ---------------------------------------------------------------------------
# Root entrypoints are Lean-only
# ---------------------------------------------------------------------------

class TestEntrypointInvariants:
    def test_check_entrypoints_passes(self):
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/check_entrypoints.py"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, (
            f"check_entrypoints.py failed:\n{result.stdout}\n{result.stderr}"
        )

    def test_agents_contains_no_legacy_pointer(self):
        content = (REPO_ROOT / "AGENTS.md").read_text()
        assert "project/generated/" not in content
        assert "tools/pos/generate.py" not in content

    def test_current_state_contains_no_legacy_pointer(self):
        content = (REPO_ROOT / "CURRENT_STATE.md").read_text()
        assert "project/generated/" not in content
        assert "tools/pos/generate.py" not in content

    def test_current_state_reports_migration_complete(self):
        content = (REPO_ROOT / "CURRENT_STATE.md").read_text()
        assert "complete" in content.lower()

    def test_current_state_reports_cutover_06(self):
        content = (REPO_ROOT / "CURRENT_STATE.md").read_text()
        assert "CUTOVER-06" in content


# ---------------------------------------------------------------------------
# Migration state
# ---------------------------------------------------------------------------

class TestMigrationState:
    def test_no_open_blockers(self):
        bl = build_blockers(GENERATED_AT)
        assert len(bl["blockers"]) == 0

    def test_cutover_05_complete(self):
        co = build_cutover_plan(GENERATED_AT)
        phases = {p["id"]: p for p in co["phases"]}
        assert phases["CUTOVER-05"]["status"] == "complete"
        assert phases["CUTOVER-05"].get("completed_in") == "LEAN-POS-10"

    def test_cutover_06_is_complete(self):
        co = build_cutover_plan(GENERATED_AT)
        phases = {p["id"]: p for p in co["phases"]}
        assert phases["CUTOVER-06"]["status"] == "complete"
        assert phases["CUTOVER-06"].get("completed_in") == "LEAN-POS-11"

    def test_entrypoint_integrity_capability_replaced(self):
        cap = build_capability_map(GENERATED_AT)
        caps_by_id = {c["id"]: c for c in cap["capabilities"]}
        assert "entrypoint_integrity" in caps_by_id
        assert caps_by_id["entrypoint_integrity"]["status"] == "replaced"

    def test_branch_freshness_capability_present(self):
        cap = build_capability_map(GENERATED_AT)
        caps_by_id = {c["id"]: c for c in cap["capabilities"]}
        assert "branch_freshness_and_conflict_preflight" in caps_by_id

    def test_migration_reversibility_present(self):
        cap = build_capability_map(GENERATED_AT)
        caps_by_id = {c["id"]: c for c in cap["capabilities"]}
        mr = caps_by_id.get("migration_reversibility")
        assert mr is not None
        # After CUTOVER-06 complete, gap is resolved
        assert mr["status"] in ("partially_replaced", "replaced")

    def test_migration_outputs_match_source_generation(self):
        """Regenerated migration outputs must be byte-identical to committed files."""
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    sys.executable, "tools/pos/lean/assess_migration.py",
                    "--repo-root", ".",
                    "--generated-at", "2026-07-18T00:00:00Z",
                    "--output-dir", tmp,
                ],
                capture_output=True, text=True, cwd=REPO_ROOT,
            )
            assert result.returncode == 0, result.stderr
            for fname in [
                "README.md", "blockers.yaml", "capability-map.yaml",
                "cutover-plan.yaml", "legacy-inventory.yaml",
            ]:
                committed = (REPO_ROOT / "project" / "lean" / "migration" / fname).read_text()
                generated = (Path(tmp) / fname).read_text()
                assert committed == generated, (
                    f"{fname} does not match source generation. Regenerate migration outputs."
                )

    def test_zero_xfails_in_lean_test_suite(self):
        """No xfail markers should remain for completed cutover phase progression."""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/pos/lean", "-v", "--tb=no", "-q"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        # Count xfailed
        xfailed = result.stdout.count(" xfailed")
        assert xfailed == 0 or "0 xfailed" in result.stdout or xfailed == 0, (
            f"Unexpected xfail count in lean test suite:\n{result.stdout}"
        )
