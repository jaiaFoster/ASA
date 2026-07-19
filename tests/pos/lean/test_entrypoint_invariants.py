"""
Tests for LEAN-POS-10: permanent entrypoint invariants.

Verifies that AGENTS.md and CURRENT_STATE.md satisfy Lean POS invariants
and that check_entrypoints.py correctly validates them.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENTS_PATH = REPO_ROOT / "AGENTS.md"
CURRENT_STATE_PATH = REPO_ROOT / "CURRENT_STATE.md"
LEAN_GENERATOR_CMD = [
    sys.executable, "tools/pos/lean/generate.py", "current-state",
    "--project-state", "project/lean/state/project-state.yaml",
    "--generated-at", "2000-01-01T00:00:00Z",
    "--output",
]
LEGACY_TEXTS = [
    "project/generated/AGENTS.md",
    "project/generated/CURRENT_STATE.md",
    "project/generated/MANAGER_INBOX.md",
    "project/generated/",
    "Regenerate with: python tools/pos/generate.py",
    "python tools/pos/generate.py",
    "python tools/pos/validate.py",
]


class TestAgentsInvariants:
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

    def test_agents_contains_no_legacy_pointer(self):
        content = AGENTS_PATH.read_text()
        for legacy in LEGACY_TEXTS:
            assert legacy not in content, f"AGENTS.md contains legacy text: {legacy!r}"

    def test_agents_contains_no_legacy_commands(self):
        content = AGENTS_PATH.read_text()
        assert "tools/pos/generate.py" not in content
        assert "tools/pos/validate.py" not in content

    def test_agents_within_token_budget(self):
        from tools.pos.lean.schemas import estimate_tokens
        tokens = estimate_tokens(AGENTS_PATH.read_text())
        assert tokens <= 1000, f"AGENTS.md over 1000-token budget: {tokens} tokens"

    def test_agents_identifies_lean_pos(self):
        content = AGENTS_PATH.read_text()
        assert "Lean POS" in content or "lean" in content.lower()

    def test_agents_states_github_is_operational(self):
        content = AGENTS_PATH.read_text()
        assert "GitHub" in content or "github" in content.lower()


class TestCurrentStateInvariants:
    def test_current_state_exists(self):
        assert CURRENT_STATE_PATH.exists()

    def test_current_state_contains_generated_warning(self):
        content = CURRENT_STATE_PATH.read_text()
        assert "GENERATED" in content or "generated" in content.lower()

    def test_current_state_contains_no_legacy_pointer(self):
        content = CURRENT_STATE_PATH.read_text()
        for legacy in LEGACY_TEXTS:
            assert legacy not in content, f"CURRENT_STATE.md contains legacy text: {legacy!r}"

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
            "Regenerate with: python tools/pos/lean/generate.py current-state "
            "--project-state project/lean/state/project-state.yaml "
            "--generated-at 2000-01-01T00:00:00Z --output CURRENT_STATE.md"
        )

    def test_current_state_reports_migration_complete(self):
        content = CURRENT_STATE_PATH.read_text()
        assert "complete" in content.lower()

    def test_current_state_reports_cutover_06(self):
        content = CURRENT_STATE_PATH.read_text()
        assert "CUTOVER-06" in content

    def test_current_state_has_lean_heading(self):
        content = CURRENT_STATE_PATH.read_text()
        assert "Lean POS" in content or "Lean" in content


class TestEntrypointCheckerTool:
    def test_checker_exits_zero_on_valid_state(self):
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/check_entrypoints.py"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, (
            f"check_entrypoints.py failed:\n{result.stdout}\n{result.stderr}"
        )

    def test_checker_fails_on_legacy_agents(self, tmp_path):
        """check_entrypoints.py must fail when AGENTS.md is a legacy pointer."""
        import shutil
        # Clone repo to tmp
        repo_copy = tmp_path / "repo"
        shutil.copytree(REPO_ROOT, repo_copy, symlinks=True,
                        ignore=shutil.ignore_patterns(".git"))
        # Overwrite AGENTS.md with legacy pointer content
        (repo_copy / "AGENTS.md").write_text(
            "<!-- This file is a pointer. The canonical version is at project/generated/AGENTS.md.\n"
            "Regenerate with: python tools/pos/generate.py -->\n\n"
            "See [project/generated/AGENTS.md](project/generated/AGENTS.md) for the current generated version.\n"
        )
        # Copy .git so it works
        import subprocess as sp
        sp.run(["git", "init", str(repo_copy)], capture_output=True)
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/check_entrypoints.py"],
            capture_output=True, text=True, cwd=repo_copy,
        )
        assert result.returncode != 0, "checker should fail on legacy AGENTS.md pointer"
        assert "legacy" in result.stdout.lower() or "E002" in result.stdout


class TestProjectStateCutoverAlignment:
    def test_project_state_phase_matches_cutover_plan(self):
        import yaml
        state = yaml.safe_load(
            (REPO_ROOT / "project" / "lean" / "state" / "project-state.yaml").read_text()
        )
        plan = yaml.safe_load(
            (REPO_ROOT / "project" / "lean" / "migration" / "cutover-plan.yaml").read_text()
        )
        notes = state.get("notes", "")
        pending = [p for p in plan["phases"] if p.get("status") != "complete"]
        if pending:
            assert pending[0]["id"] in notes, (
                f"project-state notes should reference {pending[0]['id']} as active/next phase"
            )
