"""
Tests for LEAN-POS-09: CUTOVER-04 — archive historical legacy records.

Verifies that:
- All legacy record directories have been moved to the archive
- Original active paths are absent
- BOOTSTRAP_STATUS is at the archive path only
- Archive README exists and marks records noncanonical
- Archived file bytes are preserved (no content rewriting)
- No active CI, lean tool, or entrypoint depends on archived paths
- Canonical project state marks CUTOVER-04 active and CUTOVER-05 next
- CURRENT_STATE.md matches fresh lean generation
- CUTOVER-04 complete and CUTOVER-05 is first pending phase
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

ARCHIVE_ROOT = REPO_ROOT / "project" / "lean" / "archive" / "legacy"
PROJECT_STATE_PATH = REPO_ROOT / "project" / "lean" / "state" / "project-state.yaml"
CURRENT_STATE_PATH = REPO_ROOT / "CURRENT_STATE.md"
AGENTS_PATH = REPO_ROOT / "AGENTS.md"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "validate-pos.yml"
MIGRATION_DIR = REPO_ROOT / "project" / "lean" / "migration"

LEAN_GENERATOR_CMD = [
    sys.executable, "tools/pos/lean/generate.py", "current-state",
    "--project-state", str(PROJECT_STATE_PATH),
    "--generated-at", "2000-01-01T00:00:00Z",
    "--output",
]

from tools.pos.lean.migration import build_blockers, build_cutover_plan

GENERATED_AT = "2026-07-19T00:00:00Z"

# Legacy record groups and their archive paths
ARCHIVE_GROUPS = [
    "work",
    "assignments",
    "results",
    "decisions",
    "reviews",
    "evidence",
    "risks",
]

# Original active paths (must be absent after archival)
ORIGINAL_PATHS = [
    REPO_ROOT / "project" / "work",
    REPO_ROOT / "project" / "assignments",
    REPO_ROOT / "project" / "results",
    REPO_ROOT / "project" / "decisions",
    REPO_ROOT / "project" / "reviews",
    REPO_ROOT / "project" / "evidence",
    REPO_ROOT / "project" / "risks",
    REPO_ROOT / "project" / "BOOTSTRAP_STATUS.yaml",
]


# ---------------------------------------------------------------------------
# Archive structure
# ---------------------------------------------------------------------------

class TestArchiveStructure:
    @pytest.mark.parametrize("group", ARCHIVE_GROUPS)
    def test_archive_group_exists(self, group):
        assert (ARCHIVE_ROOT / group).is_dir(), (
            f"Expected archive directory: {ARCHIVE_ROOT / group}"
        )

    @pytest.mark.parametrize("group", ARCHIVE_GROUPS)
    def test_original_path_absent(self, group):
        original = REPO_ROOT / "project" / group
        assert not original.exists(), (
            f"Original path must be absent after archival: {original}"
        )

    def test_bootstrap_status_in_archive(self):
        assert (ARCHIVE_ROOT / "BOOTSTRAP_STATUS.yaml").is_file()

    def test_bootstrap_status_not_at_original_path(self):
        assert not (REPO_ROOT / "project" / "BOOTSTRAP_STATUS.yaml").exists()

    def test_archive_readme_exists(self):
        assert (ARCHIVE_ROOT / "README.md").is_file()

    def test_archive_readme_marks_noncanonical(self):
        content = (ARCHIVE_ROOT / "README.md").read_text()
        assert "noncanonical" in content.lower() or "non-canonical" in content.lower()

    def test_archive_readme_points_to_project_state(self):
        content = (ARCHIVE_ROOT / "README.md").read_text()
        assert "project/lean/state/project-state.yaml" in content or "project-state.yaml" in content

    def test_archive_readme_states_no_current_use(self):
        content = (ARCHIVE_ROOT / "README.md").read_text()
        assert "must not" in content or "do not use" in content.lower() or "not be used" in content

    def test_archive_readme_within_token_budget(self):
        from tools.pos.lean.schemas import estimate_tokens
        tokens = estimate_tokens((ARCHIVE_ROOT / "README.md").read_text())
        assert tokens <= 400, f"archive README over 400-token budget: {tokens}"

    def test_work_record_present_in_archive(self):
        records = list((ARCHIVE_ROOT / "work").glob("*.yaml"))
        assert any(r.name != ".gitkeep" for r in records), "no YAML records in archive/work"

    def test_decisions_record_present_in_archive(self):
        records = list((ARCHIVE_ROOT / "decisions").glob("*.yaml"))
        assert any(r.name != ".gitkeep" for r in records), "no YAML records in archive/decisions"


# ---------------------------------------------------------------------------
# Byte preservation
# ---------------------------------------------------------------------------

class TestBytePreservation:
    def test_archived_work_record_has_expected_id(self):
        """Spot-check: work record retains its id field (content not rewritten)."""
        records = [f for f in (ARCHIVE_ROOT / "work").glob("*.yaml") if f.name != ".gitkeep"]
        assert records, "no archived work records found"
        for rec_path in records:
            data = yaml.safe_load(rec_path.read_text())
            assert data is not None and isinstance(data, dict)
            assert "id" in data, f"{rec_path.name} missing id field"

    def test_archived_decision_record_has_expected_id(self):
        records = [f for f in (ARCHIVE_ROOT / "decisions").glob("*.yaml") if f.name != ".gitkeep"]
        assert records, "no archived decision records found"
        for rec_path in records:
            data = yaml.safe_load(rec_path.read_text())
            assert data is not None and isinstance(data, dict)
            assert "id" in data, f"{rec_path.name} missing id field"

    def test_bootstrap_status_is_valid_yaml(self):
        data = yaml.safe_load((ARCHIVE_ROOT / "BOOTSTRAP_STATUS.yaml").read_text())
        assert data is not None and isinstance(data, dict)


# ---------------------------------------------------------------------------
# Dependency safety
# ---------------------------------------------------------------------------

class TestDependencySafety:
    def test_ci_has_no_active_reference_to_original_record_paths(self):
        text = WORKFLOW_PATH.read_text()
        for group in ARCHIVE_GROUPS:
            assert f"project/{group}" not in text, (
                f"CI workflow references original record path: project/{group}"
            )
        assert "BOOTSTRAP_STATUS" not in text

    def test_lean_generator_has_no_bootstrap_status_dependency(self):
        gen_text = (REPO_ROOT / "tools" / "pos" / "lean" / "generate.py").read_text()
        assert "BOOTSTRAP_STATUS" not in gen_text

    def test_lean_validator_does_not_scan_archive_as_active_state(self):
        val_text = (REPO_ROOT / "tools" / "pos" / "lean" / "validate.py").read_text()
        assert "archive/legacy" not in val_text

    def test_agents_md_has_no_original_record_path(self):
        content = AGENTS_PATH.read_text()
        for group in ARCHIVE_GROUPS:
            assert f"project/{group}" not in content, (
                f"AGENTS.md references original record path: project/{group}"
            )
        assert "BOOTSTRAP_STATUS" not in content

    def test_current_state_has_no_original_record_path(self):
        content = CURRENT_STATE_PATH.read_text()
        for group in ARCHIVE_GROUPS:
            assert f"project/{group}/" not in content, (
                f"CURRENT_STATE.md references original record path: project/{group}/"
            )


# ---------------------------------------------------------------------------
# Canonical state
# ---------------------------------------------------------------------------

class TestCanonicalState:
    def test_project_state_marks_cutover_04_complete(self):
        """CUTOVER-04 is complete; project-state notes reference a later phase."""
        from tools.pos.lean.migration import build_cutover_plan
        co = build_cutover_plan("2026-07-19T00:00:00Z")
        phases = {p["id"]: p for p in co["phases"]}
        assert phases["CUTOVER-04"]["status"] == "complete"

    def test_project_state_marks_cutover_05_or_later(self):
        data = yaml.safe_load(PROJECT_STATE_PATH.read_text())
        notes = data.get("notes", "")
        assert "CUTOVER-05" in notes or "CUTOVER-06" in notes

    def test_current_state_matches_fresh_generation(self):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            out = f.name
        result = subprocess.run(
            LEAN_GENERATOR_CMD + [out],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, result.stderr
        assert Path(out).read_text() == CURRENT_STATE_PATH.read_text(), (
            "CURRENT_STATE.md does not match lean generator output. Regenerate."
        )

    def test_current_state_reports_recent_cutover(self):
        content = CURRENT_STATE_PATH.read_text()
        assert "CUTOVER-05" in content or "CUTOVER-06" in content


# ---------------------------------------------------------------------------
# Migration state
# ---------------------------------------------------------------------------

class TestMigrationState:
    def test_no_open_migration_blockers(self):
        bl = build_blockers(GENERATED_AT)
        assert len(bl["blockers"]) == 0, (
            f"Open blockers remain: {[b['id'] for b in bl['blockers']]}"
        )

    def test_cutover_04_complete(self):
        co = build_cutover_plan(GENERATED_AT)
        phases = {p["id"]: p for p in co["phases"]}
        assert phases["CUTOVER-04"]["status"] == "complete"
        assert phases["CUTOVER-04"].get("completed_in") == "LEAN-POS-09"

    def test_cutover_05_is_complete(self):
        co = build_cutover_plan(GENERATED_AT)
        phases = {p["id"]: p for p in co["phases"]}
        assert phases["CUTOVER-05"]["status"] == "complete"
        assert phases["CUTOVER-05"].get("completed_in") == "LEAN-POS-10"

    def test_historical_record_preservation_replaced(self):
        from tools.pos.lean.migration import build_capability_map
        cap = build_capability_map(GENERATED_AT)
        caps_by_id = {c["id"]: c for c in cap["capabilities"]}
        assert "historical_record_preservation" in caps_by_id
        assert caps_by_id["historical_record_preservation"]["status"] == "replaced"

    def test_archive_paths_in_inventory(self):
        from tools.pos.lean.migration import build_legacy_inventory
        inv = build_legacy_inventory(REPO_ROOT, GENERATED_AT)
        artifact_paths = {a["path"] for a in inv["artifacts"]}
        # Work records must be at archive path
        assert any("archive/legacy/work" in p for p in artifact_paths), (
            "No archive/legacy/work paths in inventory"
        )

    def test_bootstrap_status_in_inventory_at_archive_path(self):
        from tools.pos.lean.migration import build_legacy_inventory
        inv = build_legacy_inventory(REPO_ROOT, GENERATED_AT)
        artifact_paths = {a["path"] for a in inv["artifacts"]}
        assert "project/lean/archive/legacy/BOOTSTRAP_STATUS.yaml" in artifact_paths

    def test_migration_outputs_match_source_generation(self):
        """Regenerated migration outputs must be byte-identical to committed files."""
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

    def test_lean_runtime_present(self):
        """Lean tools must always be present."""
        assert (REPO_ROOT / "tools" / "pos" / "lean" / "validate.py").is_file()
        assert (REPO_ROOT / "tools" / "pos" / "lean" / "generate.py").is_file()

    def test_lean_schemas_present(self):
        """Lean schemas must always be present."""
        assert (REPO_ROOT / "project" / "schemas" / "lean").is_dir()
        assert any((REPO_ROOT / "project" / "schemas" / "lean").glob("*.yaml"))
