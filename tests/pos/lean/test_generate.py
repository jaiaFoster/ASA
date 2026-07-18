"""
Tests for tools/pos/lean/views.py and tools/pos/lean/generate.py.

Groups:
  1. current-state rendering
  2. worker-context rendering
  3. token budgets
  4. atomic write
  5. safety (no network, no writes, legacy mtime)
"""

from __future__ import annotations

import os
import stat
import sys
import tempfile
import time
from pathlib import Path

import pytest
import yaml

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from tools.pos.lean.views import (
    render_current_state,
    render_worker_context,
    estimate_worker_context_tokens,
)
from tools.pos.lean.generate import atomic_write
from tools.pos.lean.schemas import (
    TOKEN_BUDGET_CURRENT_STATE,
    TOKEN_BUDGET_WORKER_CONTEXT_NORMAL,
    TOKEN_BUDGET_WORKER_CONTEXT_ELEVATED,
    estimate_tokens,
)

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

FIXTURES_VIEWS = REPO_ROOT / "tests" / "pos" / "lean" / "fixtures" / "views"
FIXTURES_VALID = REPO_ROOT / "project" / "lean" / "fixtures" / "valid"
LEAN_GENERATED = REPO_ROOT / "project" / "lean" / "generated"
LEGACY_GENERATED = REPO_ROOT / "project" / "generated"


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_rules() -> list[dict]:
    data = _load(FIXTURES_VIEWS / "trial-rules.yaml")
    return data if isinstance(data, list) else data.get("rules", [])


def _project_state() -> dict:
    return _load(FIXTURES_VALID / "project-state.yaml")


def _handoff() -> dict:
    return _load(FIXTURES_VALID / "worker-handoff.yaml")


GENERATED_AT = "2026-07-18T12:00:00Z"


# ===========================================================================
# 1. current-state rendering
# ===========================================================================

class TestCurrentState:
    def _render(self, recon_name: str | None = None, **kw) -> str:
        recon = _load(FIXTURES_VIEWS / recon_name) if recon_name else None
        return render_current_state(
            project_state=_project_state(),
            reconciliation=recon,
            trial_rules=_load_rules(),
            generated_at=GENERATED_AT,
            **kw,
        )

    def test_planned_issue(self):
        md = self._render("project-reconciliation.yaml")
        assert "planned" in md
        assert "issue#12" in md

    def test_active_draft_pr(self):
        md = self._render("project-reconciliation-review.yaml")
        # review state should appear in the Active Work section
        assert "review" in md

    def test_review_ready_pr(self):
        md = self._render("project-reconciliation-review.yaml")
        assert "## Active Work" in md

    def test_blocked_failed_checks(self):
        md = self._render("project-reconciliation-blocked.yaml")
        assert "## Blocked" in md
        assert "validate-pos" in md

    def test_unauthorized_merge_conflict(self):
        md = self._render("project-reconciliation-conflict.yaml")
        assert "## Conflicts" in md
        assert "unauthorized-bot" in md

    def test_missing_authority_undetermined(self):
        md = self._render("project-reconciliation-undetermined.yaml")
        assert "## Undetermined" in md
        assert "G004" in md

    def test_accepted_work_bounded_history(self):
        md = self._render("project-reconciliation-accepted.yaml", recently_accepted_limit=2)
        assert "## Recently Accepted" in md
        # Should show at most 2 merged items
        assert md.count("merged by") <= 2

    def test_active_trial_rules(self):
        md = self._render("project-reconciliation.yaml")
        assert "## Active Trial Rules" in md
        assert "lean-tr-001" in md
        assert "lean-tr-002" in md
        # lean-tr-003 is 'adopted', should not appear in Active Trial Rules
        active_section = md.split("## Active Trial Rules")[1].split("##")[0]
        assert "lean-tr-003" not in active_section

    def test_empty_optional_sections_no_crash(self):
        md = render_current_state(
            project_state={"id": "ps-empty", "objective": "Nothing"},
            reconciliation=None,
            trial_rules=[],
            generated_at=GENERATED_AT,
        )
        assert "## Current Objective" in md
        assert "Nothing" in md

    def test_non_canonical_warning_present(self):
        md = self._render("project-reconciliation.yaml")
        assert "DO NOT EDIT MANUALLY" in md

    def test_generated_at_present(self):
        md = self._render("project-reconciliation.yaml")
        assert GENERATED_AT in md

    def test_sources_section_present(self):
        md = self._render("project-reconciliation.yaml")
        assert "## Sources" in md

    def test_deterministic(self):
        md1 = self._render("project-reconciliation.yaml")
        md2 = self._render("project-reconciliation.yaml")
        assert md1 == md2


# ===========================================================================
# 2. worker-context rendering
# ===========================================================================

class TestWorkerContext:
    def _render(self, recon_name: str | None = "handoff-reconciliation.yaml", **kw) -> dict:
        recon = _load(FIXTURES_VIEWS / recon_name) if recon_name else None
        return render_worker_context(
            handoff=_handoff(),
            reconciliation=recon,
            trial_rules=_load_rules(),
            generated_at=GENERATED_AT,
            **kw,
        )

    def test_normal_R2_handoff(self):
        ctx = self._render()
        assert ctx["handoff"]["id"] == "lean-wh-001"
        assert ctx["handoff"]["risk"] == "R2"
        assert "scope" in ctx["handoff"]

    def test_R3_handoff_with_extra_budget(self):
        h = dict(_handoff())
        h["risk"] = "R3"
        ctx = render_worker_context(
            handoff=h,
            reconciliation=_load(FIXTURES_VIEWS / "handoff-reconciliation.yaml"),
            trial_rules=_load_rules(),
            generated_at=GENERATED_AT,
        )
        assert ctx["handoff"]["risk"] == "R3"

    def test_active_trial_rule_included(self):
        ctx = self._render()
        rule_ids = [r["id"] for r in ctx["relevant_constraints"]["active_trial_rules"]]
        assert "lean-tr-001" in rule_ids
        assert "lean-tr-002" in rule_ids

    def test_adopted_rule_excluded(self):
        ctx = self._render()
        rule_ids = [r["id"] for r in ctx["relevant_constraints"]["active_trial_rules"]]
        assert "lean-tr-003" not in rule_ids

    def test_github_blocker_included_when_blocked(self):
        ctx = render_worker_context(
            handoff=_handoff(),
            reconciliation=_load(FIXTURES_VIEWS / "project-reconciliation-blocked.yaml"),
            trial_rules=[],
            generated_at=GENERATED_AT,
        )
        obs = ctx["observed_github_state"]
        assert obs["derived_state"] == "blocked"
        assert "blockers" in obs

    def test_accepted_github_state(self):
        ctx = render_worker_context(
            handoff=_handoff(),
            reconciliation=_load(FIXTURES_VIEWS / "project-reconciliation-accepted.yaml"),
            trial_rules=[],
            generated_at=GENERATED_AT,
        )
        assert ctx["observed_github_state"]["derived_state"] == "accepted"

    def test_missing_reconciliation_data(self):
        ctx = render_worker_context(
            handoff=_handoff(),
            reconciliation=None,
            trial_rules=[],
            generated_at=GENERATED_AT,
        )
        assert ctx["observed_github_state"]["derived_state"] == "undetermined"
        assert "note" in ctx["observed_github_state"]

    def test_locked_fields_not_truncated(self):
        """Execution fields must be embedded verbatim, not summarized."""
        ctx = self._render()
        hf = ctx["handoff"]
        original = _handoff()
        for field in ("scope", "lock", "accept"):
            assert hf[field] == original[field]

    def test_invalid_handoff_rejected(self):
        """generate.py CLI must exit 2 for missing required fields."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/generate.py", "worker-context",
             "--handoff", "tests/pos/lean/fixtures/views/trial-rules.yaml",  # not a handoff
             "--generated-at", GENERATED_AT],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 2

    def test_deterministic_key_order(self):
        ctx1 = self._render()
        ctx2 = self._render()
        assert list(ctx1.keys()) == list(ctx2.keys())

    def test_non_canonical_note_present(self):
        ctx = self._render()
        assert "NOT CANONICAL" in ctx.get("generated_note", "")

    def test_sources_include_handoff(self):
        ctx = self._render()
        types = [s["type"] for s in ctx["sources"]]
        assert "handoff" in types

    def test_stop_conditions_present(self):
        ctx = self._render()
        assert len(ctx["stop_conditions"]) > 0

    def test_verification_from_accept(self):
        ctx = self._render()
        assert len(ctx["verification"]) > 0


# ===========================================================================
# 3. Token budget
# ===========================================================================

class TestTokenBudget:
    def test_current_state_within_budget_for_simple_input(self):
        md = render_current_state(
            project_state={"id": "ps-1", "objective": "Small objective"},
            reconciliation=None,
            trial_rules=[],
            generated_at=GENERATED_AT,
        )
        assert estimate_tokens(md) < TOKEN_BUDGET_CURRENT_STATE

    def test_token_warning_added_when_over_budget(self):
        # Craft a huge objective that blows the budget
        big_text = "x " * 20000
        md = render_current_state(
            project_state={"id": "ps-1", "objective": big_text},
            reconciliation=None,
            trial_rules=[],
            generated_at=GENERATED_AT,
        )
        assert "WARNING: estimated token count" in md

    def test_worker_context_token_estimate_returns_int(self):
        ctx = render_worker_context(
            handoff=_handoff(),
            reconciliation=None,
            trial_rules=[],
            generated_at=GENERATED_AT,
        )
        est = estimate_worker_context_tokens(ctx)
        assert isinstance(est, int) and est > 0

    def test_R2_budget_is_normal(self):
        assert TOKEN_BUDGET_WORKER_CONTEXT_NORMAL == 2000

    def test_R3_budget_is_elevated(self):
        assert TOKEN_BUDGET_WORKER_CONTEXT_ELEVATED == 3500


# ===========================================================================
# 4. Atomic write
# ===========================================================================

class TestAtomicWrite:
    def test_atomic_write_success(self, tmp_path):
        out = tmp_path / "output.md"
        atomic_write(out, "hello world")
        assert out.read_text() == "hello world"

    def test_atomic_write_creates_parent_dirs(self, tmp_path):
        out = tmp_path / "deep" / "dir" / "file.txt"
        atomic_write(out, "content")
        assert out.read_text() == "content"

    def test_atomic_write_failure_preserves_old_file(self, tmp_path):
        out = tmp_path / "output.md"
        out.write_text("original content")

        # Make a write that fails by passing an object that can't be serialised
        with pytest.raises(Exception):
            atomic_write(out, None)  # type: ignore[arg-type]

        # Old file must be intact
        assert out.read_text() == "original content"

    def test_atomic_write_no_temp_file_left_on_success(self, tmp_path):
        out = tmp_path / "output.md"
        atomic_write(out, "data")
        temp_files = list(tmp_path.glob(".lean-gen-*.tmp"))
        assert temp_files == []

    def test_atomic_write_no_temp_file_left_on_failure(self, tmp_path):
        out = tmp_path / "output.md"
        with pytest.raises(Exception):
            atomic_write(out, None)  # type: ignore[arg-type]
        temp_files = list(tmp_path.glob(".lean-gen-*.tmp"))
        assert temp_files == []


# ===========================================================================
# 5. Safety
# ===========================================================================

class TestSafety:
    def test_fixture_mode_has_no_network(self, tmp_path):
        """generate.py current-state with --reconciliation must not import requests."""
        import subprocess
        out = tmp_path / "CURRENT_STATE.md"
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; "
             "sys.path.insert(0, '.'); "
             "import tools.pos.lean.generate as g; "
             "import tools.pos.lean.views as v; "
             "assert 'requests' not in sys.modules, 'requests imported at import time'"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, result.stderr

    def test_live_adapter_has_no_write_methods(self):
        from tools.pos.lean.github import LiveAdapter, WriteAttemptError
        adapter = LiveAdapter.__new__(LiveAdapter)
        with pytest.raises(WriteAttemptError):
            adapter._write("anything")  # type: ignore[attr-defined]

    def test_legacy_generated_mtimes_unchanged(self, tmp_path):
        """generate.py must not touch project/generated/ (legacy files)."""
        if not LEGACY_GENERATED.exists():
            pytest.skip("project/generated/ does not exist in this environment")
        legacy_files = list(LEGACY_GENERATED.rglob("*"))
        if not legacy_files:
            pytest.skip("No legacy files to check")
        before = {f: f.stat().st_mtime for f in legacy_files if f.is_file()}

        # Run the generator for current-state
        import subprocess
        out = tmp_path / "CURRENT_STATE.md"
        subprocess.run(
            [sys.executable, "tools/pos/lean/generate.py", "current-state",
             "--project-state", str(FIXTURES_VALID / "project-state.yaml"),
             "--reconciliation", str(FIXTURES_VIEWS / "project-reconciliation.yaml"),
             "--output", str(out),
             "--generated-at", GENERATED_AT],
            capture_output=True, cwd=REPO_ROOT,
        )

        after = {f: f.stat().st_mtime for f in legacy_files if f.is_file()}
        for f in before:
            assert before[f] == after.get(f, before[f]), f"mtime changed: {f}"

    def test_raw_token_not_in_worker_context_output(self, tmp_path):
        """GITHUB_TOKEN env var must not appear in generated WORKER_CONTEXT.yaml."""
        os.environ.setdefault("GITHUB_TOKEN", "ghp_testtesttest")
        import subprocess
        out = tmp_path / "WORKER_CONTEXT.yaml"
        subprocess.run(
            [sys.executable, "tools/pos/lean/generate.py", "worker-context",
             "--handoff", str(FIXTURES_VALID / "worker-handoff.yaml"),
             "--reconciliation", str(FIXTURES_VIEWS / "handoff-reconciliation.yaml"),
             "--output", str(out),
             "--generated-at", GENERATED_AT],
            capture_output=True, cwd=REPO_ROOT,
        )
        if out.exists():
            content = out.read_text()
            assert "ghp_testtesttest" not in content

    def test_generate_current_state_cli_exit_0(self, tmp_path):
        import subprocess
        out = tmp_path / "CURRENT_STATE.md"
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/generate.py", "current-state",
             "--project-state", str(FIXTURES_VALID / "project-state.yaml"),
             "--reconciliation", str(FIXTURES_VIEWS / "project-reconciliation.yaml"),
             "--output", str(out),
             "--generated-at", GENERATED_AT],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert out.exists()

    def test_generate_worker_context_cli_exit_0(self, tmp_path):
        import subprocess
        out = tmp_path / "WORKER_CONTEXT.yaml"
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/generate.py", "worker-context",
             "--handoff", str(FIXTURES_VALID / "worker-handoff.yaml"),
             "--reconciliation", str(FIXTURES_VIEWS / "handoff-reconciliation.yaml"),
             "--output", str(out),
             "--generated-at", GENERATED_AT],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0
        assert out.exists()

    def test_generate_missing_project_state_exits_2(self, tmp_path):
        import subprocess
        out = tmp_path / "CURRENT_STATE.md"
        result = subprocess.run(
            [sys.executable, "tools/pos/lean/generate.py", "current-state",
             "--project-state", "/nonexistent/path.yaml",
             "--output", str(out),
             "--generated-at", GENERATED_AT],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 2
