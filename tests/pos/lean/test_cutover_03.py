"""
Tests for LEAN-POS-08: CUTOVER-03 — switch CI and documentation entrypoints.

Verifies that:
- CI workflow uses lean tools (not legacy)
- CURRENT_STATE.md matches lean generator output
- AGENTS.md points to lean POS state and tools
- MANAGER_INBOX.md is absent
- All migration blockers are resolved
- CUTOVER-03 is complete and CUTOVER-04 is next
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

WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "validate-pos.yml"
AGENTS_PATH = REPO_ROOT / "AGENTS.md"
CURRENT_STATE_PATH = REPO_ROOT / "CURRENT_STATE.md"
MANAGER_INBOX_PATH = REPO_ROOT / "MANAGER_INBOX.md"
PROJECT_STATE_PATH = REPO_ROOT / "project" / "lean" / "state" / "project-state.yaml"
MIGRATION_DIR = REPO_ROOT / "project" / "lean" / "migration"

LEAN_GENERATOR_CMD = [
    sys.executable, "tools/pos/lean/generate.py", "current-state",
    "--project-state", str(PROJECT_STATE_PATH),
    "--generated-at", "2000-01-01T00:00:00Z",
    "--output",
]

from tools.pos.lean.migration import build_blockers, build_cutover_plan


# ---------------------------------------------------------------------------
# Workflow checks
# ---------------------------------------------------------------------------

class TestWorkflow:
    def _workflow_text(self) -> str:
        return WORKFLOW_PATH.read_text()

    def test_workflow_invokes_lean_validator(self):
        text = self._workflow_text()
        assert "tools/pos/lean/validate.py" in text

    def test_workflow_invokes_lean_integrity_checker(self):
        text = self._workflow_text()
        assert "tools/pos/lean/check_integrity.py" in text

    def test_workflow_invokes_lean_generator(self):
        text = self._workflow_text()
        assert "tools/pos/lean/generate.py" in text

    def test_workflow_does_not_invoke_legacy_validator(self):
        text = self._workflow_text()
        # Must not call legacy validator as an active step
        assert "tools/pos/validate.py" not in text

    def test_workflow_does_not_invoke_legacy_generator(self):
        text = self._workflow_text()
        assert "tools/pos/generate.py" not in text

    def test_workflow_diff_check_targets_current_state(self):
        text = self._workflow_text()
        assert "CURRENT_STATE.md" in text
        # The diff check line must include CURRENT_STATE.md
        diff_lines = [l for l in text.splitlines() if "git diff" in l and "exit-code" in l]
        assert any("CURRENT_STATE.md" in l for l in diff_lines), (
            "git diff --exit-code step must target CURRENT_STATE.md"
        )

    def test_workflow_does_not_target_manager_inbox(self):
        text = self._workflow_text()
        # Must not appear in the diff check
        diff_lines = [l for l in text.splitlines() if "git diff" in l]
        assert not any("MANAGER_INBOX" in l for l in diff_lines)

    def test_workflow_generation_uses_fixed_timestamp(self):
        text = self._workflow_text()
        # A fixed --generated-at value must be present for determinism
        assert "--generated-at" in text
        # Must not use a runtime value like $(date ...) in the generator step
        lines = text.splitlines()
        gen_section = False
        for line in lines:
            if "generate.py" in line and "lean" in line:
                gen_section = True
            if gen_section and "date" in line and "$(date" in line:
                pytest.fail("Lean generator uses runtime $(date ...) — must use fixed timestamp")
            if gen_section and line.strip().startswith("-"):
                break  # next step

    def test_workflow_generation_is_offline(self):
        text = self._workflow_text()
        # Generator must not use --repo or --token in the CI step
        lines = text.splitlines()
        in_gen_step = False
        for line in lines:
            if "generate.py current-state" in line:
                in_gen_step = True
            if in_gen_step and ("--repo " in line or "--token" in line):
                pytest.fail("Lean generator in CI uses live network args (--repo/--token)")
            if in_gen_step and line.strip().startswith("- name:") and "generate" not in line.lower():
                break


# ---------------------------------------------------------------------------
# CURRENT_STATE.md entrypoint
# ---------------------------------------------------------------------------

class TestCurrentState:
    def test_current_state_exists(self):
        assert CURRENT_STATE_PATH.exists()

    def test_current_state_matches_fresh_generation(self):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            out = f.name
        result = subprocess.run(
            LEAN_GENERATOR_CMD + [out],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, result.stderr
        generated = Path(out).read_text()
        committed = CURRENT_STATE_PATH.read_text()
        assert generated == committed, (
            "CURRENT_STATE.md does not match lean generator output. "
            "Regenerate with the lean generator using --generated-at 2000-01-01T00:00:00Z."
        )

    def test_current_state_does_not_depend_on_bootstrap_status(self):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            out = f.name
        result = subprocess.run(
            LEAN_GENERATOR_CMD + [out],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, result.stderr
        content = Path(out).read_text()
        assert "bootstrap_01" not in content
        assert "bootstrap_02" not in content
        assert "pos_status" not in content

    def test_current_state_identifies_lean_pos(self):
        content = CURRENT_STATE_PATH.read_text()
        assert "lean" in content.lower() or "Lean" in content


# ---------------------------------------------------------------------------
# AGENTS.md entrypoint
# ---------------------------------------------------------------------------

class TestAgents:
    def test_agents_exists(self):
        assert AGENTS_PATH.exists()

    def test_agents_points_to_lean_state(self):
        content = AGENTS_PATH.read_text()
        assert "project/lean/state/project-state.yaml" in content

    def test_agents_points_to_lean_tools(self):
        content = AGENTS_PATH.read_text()
        assert "tools/pos/lean/" in content

    def test_agents_points_to_cutover_plan(self):
        content = AGENTS_PATH.read_text()
        assert "cutover-plan" in content or "migration" in content

    def test_agents_does_not_require_manager_inbox(self):
        content = AGENTS_PATH.read_text()
        assert "MANAGER_INBOX" not in content

    def test_agents_within_token_budget(self):
        from tools.pos.lean.schemas import estimate_tokens
        tokens = estimate_tokens(AGENTS_PATH.read_text())
        assert tokens <= 1000, f"AGENTS.md over 1000-token budget: {tokens} tokens"

    def test_agents_does_not_reference_legacy_generator(self):
        content = AGENTS_PATH.read_text()
        # Must not instruct use of the legacy generator for normal operation
        assert "tools/pos/generate.py" not in content
        assert "tools/pos/validate.py" not in content


# ---------------------------------------------------------------------------
# MANAGER_INBOX.md absent
# ---------------------------------------------------------------------------

class TestManagerInbox:
    def test_manager_inbox_is_absent(self):
        assert not MANAGER_INBOX_PATH.exists(), (
            "MANAGER_INBOX.md must be deleted in CUTOVER-03"
        )


# ---------------------------------------------------------------------------
# Migration state
# ---------------------------------------------------------------------------

class TestMigrationState:
    GENERATED_AT = "2026-07-18T00:00:00Z"

    def test_no_open_migration_blockers(self):
        bl = build_blockers(self.GENERATED_AT)
        assert len(bl["blockers"]) == 0, (
            f"Open blockers remain: {[b['id'] for b in bl['blockers']]}"
        )

    def test_all_six_blockers_resolved(self):
        bl = build_blockers(self.GENERATED_AT)
        resolved_ids = {b["id"] for b in bl.get("resolved_blockers", [])}
        for blkr in ("BLKR-001", "BLKR-002", "BLKR-003", "BLKR-004", "BLKR-005", "BLKR-006"):
            assert blkr in resolved_ids, f"{blkr} not in resolved_blockers"

    def test_cutover_ready(self):
        bl = build_blockers(self.GENERATED_AT)
        assert bl["summary"]["cutover_ready"] is True

    def test_cutover_03_complete(self):
        co = build_cutover_plan(self.GENERATED_AT)
        phases = {p["id"]: p for p in co["phases"]}
        assert phases["CUTOVER-03"]["status"] == "complete"
        assert phases["CUTOVER-03"].get("completed_in") == "LEAN-POS-08"

    def test_cutover_04_is_first_pending_phase(self):
        co = build_cutover_plan(self.GENERATED_AT)
        pending = [p for p in co["phases"] if p.get("status") != "complete"]
        assert pending, "no pending phases found"
        assert pending[0]["id"] == "CUTOVER-04", (
            f"expected CUTOVER-04 as first pending; got {pending[0]['id']}"
        )

    def test_migration_outputs_match_source_generation(self):
        """Regenerated migration outputs must be byte-identical to committed files."""
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, "tools/pos/lean/assess_migration.py",
                 "--repo-root", ".", "--generated-at", self.GENERATED_AT,
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
