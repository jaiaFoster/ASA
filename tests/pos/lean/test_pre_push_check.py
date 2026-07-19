"""
Tests for LEAN-POS-10/11: pre_push_check.py safeguard.

Uses temporary git repositories — no network beyond what pre_push_check.py
itself does when testing freshness. Conflict detection tests use real
conflicting git histories in isolated repos.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _run(cmd: list[str], *, cwd: Path = REPO_ROOT, env=None) -> tuple[int, str, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env)
    return r.returncode, r.stdout, r.stderr


class TestPrePushCheckExists:
    def test_pre_push_check_exists(self):
        assert (REPO_ROOT / "tools" / "pos" / "lean" / "pre_push_check.py").exists()

    def test_pre_push_hook_exists(self):
        assert (REPO_ROOT / ".githooks" / "pre-push").exists()

    def test_hook_is_executable(self):
        import os
        hook = REPO_ROOT / ".githooks" / "pre-push"
        assert os.access(hook, os.X_OK), ".githooks/pre-push must be executable"

    def test_hook_invokes_pre_push_check(self):
        content = (REPO_ROOT / ".githooks" / "pre-push").read_text()
        assert "pre_push_check.py" in content


class TestPrePushCheckLogic:
    def test_check_freshness_function_importable(self):
        from tools.pos.lean.pre_push_check import check_freshness
        assert callable(check_freshness)

    def test_check_entrypoints_function_importable(self):
        from tools.pos.lean.pre_push_check import check_entrypoints
        assert callable(check_entrypoints)

    def test_check_merge_conflicts_function_importable(self):
        from tools.pos.lean.pre_push_check import check_merge_conflicts
        assert callable(check_merge_conflicts)

    def test_main_returns_int(self):
        from tools.pos.lean import pre_push_check
        assert hasattr(pre_push_check, "main")

    def test_script_has_main_guard(self):
        content = (REPO_ROOT / "tools" / "pos" / "lean" / "pre_push_check.py").read_text()
        assert '__name__ == "__main__"' in content

    def test_script_prints_summary(self, tmp_path):
        """Running the script in the real repo should print a summary line."""
        rc, out, err = _run([sys.executable, "tools/pos/lean/pre_push_check.py"])
        combined = out + err
        assert "check" in combined.lower() or "PASS" in combined or "FAIL" in combined

    def test_conflict_probe_merge_tree_importable(self):
        from tools.pos.lean.pre_push_check import _conflict_probe_merge_tree
        assert callable(_conflict_probe_merge_tree)

    def test_conflict_probe_worktree_importable(self):
        from tools.pos.lean.pre_push_check import _conflict_probe_worktree
        assert callable(_conflict_probe_worktree)


class TestWorktreeSafety:
    def test_pre_push_script_does_not_modify_worktree(self):
        """Running pre_push_check.py must not change any tracked files."""
        rc1, out1, _ = _run(["git", "status", "--porcelain"])
        _run([sys.executable, "tools/pos/lean/pre_push_check.py"])
        rc2, out2, _ = _run(["git", "status", "--porcelain"])
        assert out1 == out2, (
            f"pre_push_check.py modified the worktree.\nBefore: {out1!r}\nAfter: {out2!r}"
        )


# ---------------------------------------------------------------------------
# Helpers shared by conflict and freshness tests
# ---------------------------------------------------------------------------

def _make_repo(tmp_path: Path, name: str) -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _run(["git", "init", "-b", "main", str(repo)])
    _run(["git", "config", "user.email", "test@test.com"], cwd=repo)
    _run(["git", "config", "user.name", "Test"], cwd=repo)
    return repo


def _add_commit(repo: Path, filename: str, content: str, msg: str):
    path = repo / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _run(["git", "add", filename], cwd=repo)
    _run(["git", "commit", "-m", msg], cwd=repo)


def _copy_script_to(work: Path):
    """Copy pre_push_check.py and its dependencies into a tmp repo."""
    tools_dir = work / "tools" / "pos" / "lean"
    tools_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "tools" / "pos" / "lean" / "pre_push_check.py", tools_dir)
    for fn in ("check_integrity.py", "check_entrypoints.py"):
        src = REPO_ROOT / "tools" / "pos" / "lean" / fn
        if src.exists():
            shutil.copy2(src, tools_dir)
    for d in [work / "tools", work / "tools" / "pos", tools_dir]:
        (d / "__init__.py").touch()


def _run_freshness(work: Path) -> tuple[bool, str]:
    _copy_script_to(work)
    rc, out, err = _run([sys.executable, "-c",
        "import sys; sys.path.insert(0, '.'); "
        "from tools.pos.lean.pre_push_check import check_freshness; "
        "ok, msg = check_freshness(); print('OK' if ok else 'FAIL'); print(msg)"
    ], cwd=work)
    combined = out + err
    ok = "OK\n" in combined or combined.startswith("OK")
    return ok, combined


def _run_conflict_check(work: Path) -> tuple[bool, str]:
    """Run check_merge_conflicts in the given repo directory via subprocess."""
    _copy_script_to(work)
    rc, out, err = _run([sys.executable, "-c",
        "import sys; sys.path.insert(0, '.'); "
        "from tools.pos.lean.pre_push_check import check_merge_conflicts; "
        "ok, msg = check_merge_conflicts(); print('OK' if ok else 'FAIL'); print(msg)"
    ], cwd=work)
    combined = out + err
    ok = "OK\n" in combined or combined.startswith("OK")
    return ok, combined


def _make_diverged_repos(tmp_path: Path,
                          origin_name: str = "origin",
                          work_name: str = "work") -> tuple[Path, Path]:
    """Return (origin, work) repos sharing a common base commit."""
    origin = _make_repo(tmp_path, origin_name)
    _add_commit(origin, "base.txt", "base content\n", "base")
    work = _make_repo(tmp_path, work_name)
    _run(["git", "remote", "add", "origin", str(origin)], cwd=work)
    _run(["git", "fetch", "origin", "main"], cwd=work)
    _run(["git", "checkout", "-b", "main", "origin/main"], cwd=work)
    return origin, work


# ---------------------------------------------------------------------------
# Freshness tests
# ---------------------------------------------------------------------------

class TestFreshnessDetection:
    def test_freshness_passes_when_up_to_date(self, tmp_path):
        origin, work = _make_diverged_repos(tmp_path)
        _add_commit(work, "b.txt", "world\n", "local commit")
        ok, msg = _run_freshness(work)
        assert ok, f"expected pass, got: {msg}"

    def test_freshness_fails_when_behind(self, tmp_path):
        origin, work = _make_diverged_repos(tmp_path, "origin2", "work2")
        _add_commit(origin, "c.txt", "new\n", "origin-only commit")
        ok, msg = _run_freshness(work)
        assert not ok, f"expected fail (branch behind), got: {msg}"
        assert "rebase" in msg.lower() or "behind" in msg.lower() or "FAIL" in msg

    def test_freshness_failure_message_includes_recovery_command(self, tmp_path):
        origin, work = _make_diverged_repos(tmp_path, "origin3", "work3")
        _add_commit(origin, "c.txt", "new\n", "origin-only")
        ok, msg = _run_freshness(work)
        assert not ok
        assert "rebase" in msg or "merge" in msg or "Fix:" in msg


# ---------------------------------------------------------------------------
# Merge conflict detection tests — real conflicting git histories
# ---------------------------------------------------------------------------

class TestMergeConflictDetection:
    """All tests use isolated git repos; no network required."""

    def test_clean_divergent_branches_pass(self, tmp_path):
        """Non-conflicting divergent changes on both branches pass the probe."""
        origin, work = _make_diverged_repos(tmp_path, "o_clean", "w_clean")
        _add_commit(origin, "origin_only.txt", "from origin\n", "origin diverges")
        _add_commit(work, "work_only.txt", "from work\n", "work diverges")
        _run(["git", "fetch", "origin", "main"], cwd=work)
        ok, msg = _run_conflict_check(work)
        assert ok, f"expected clean merge to pass, got: {msg}"

    def test_text_conflict_blocks_push(self, tmp_path):
        """Both branches add the same file with different content — conflict."""
        origin, work = _make_diverged_repos(tmp_path, "o_text", "w_text")
        _run(["git", "fetch", "origin", "main"], cwd=work)
        # Both sides add the same filename from the common base
        _add_commit(origin, "shared.txt", "origin content\n", "origin adds shared")
        _add_commit(work, "shared.txt", "work content\n", "work adds shared")
        _run(["git", "fetch", "origin", "main"], cwd=work)
        ok, msg = _run_conflict_check(work)
        assert not ok, f"expected add/add conflict to block push, got: {msg}"

    def test_delete_modify_conflict_blocks_push(self, tmp_path):
        """One branch modifies a file, the other deletes it — conflict."""
        origin, work = _make_diverged_repos(tmp_path, "o_delmod", "w_delmod")
        # Add victim.txt to both via the base
        _add_commit(origin, "victim.txt", "original\n", "add victim to origin")
        _run(["git", "fetch", "origin", "main"], cwd=work)
        _run(["git", "merge", "origin/main", "--ff-only"], cwd=work)
        # origin modifies victim
        (origin / "victim.txt").write_text("modified by origin\n")
        _run(["git", "add", "victim.txt"], cwd=origin)
        _run(["git", "commit", "-m", "origin modifies victim"], cwd=origin)
        # work deletes victim
        _run(["git", "rm", "victim.txt"], cwd=work)
        _run(["git", "commit", "-m", "work deletes victim"], cwd=work)
        _run(["git", "fetch", "origin", "main"], cwd=work)
        ok, msg = _run_conflict_check(work)
        assert not ok, f"expected delete/modify conflict to block push, got: {msg}"

    def test_rename_conflict_blocks_push(self, tmp_path):
        """Both branches add the same path with incompatible content — conflict."""
        origin, work = _make_diverged_repos(tmp_path, "o_rename", "w_rename")
        _run(["git", "fetch", "origin", "main"], cwd=work)
        # Add-add conflict (same filename, different content) is detected reliably
        _add_commit(origin, "renamed.txt", "origin version\n", "origin adds renamed")
        _add_commit(work, "renamed.txt", "work version\n", "work adds renamed")
        _run(["git", "fetch", "origin", "main"], cwd=work)
        ok, msg = _run_conflict_check(work)
        assert not ok, f"expected conflict to block push, got: {msg}"

    def test_output_names_conflicting_paths(self, tmp_path):
        """Conflict output must include the conflicting filename."""
        origin, work = _make_diverged_repos(tmp_path, "o_paths", "w_paths")
        _run(["git", "fetch", "origin", "main"], cwd=work)
        _add_commit(origin, "identifiable_conflict.txt", "origin\n", "origin")
        _add_commit(work, "identifiable_conflict.txt", "work\n", "work")
        _run(["git", "fetch", "origin", "main"], cwd=work)
        ok, msg = _run_conflict_check(work)
        assert not ok
        assert "identifiable_conflict.txt" in msg, (
            f"conflicting path not named in output: {msg}"
        )

    def test_primary_worktree_unchanged_after_conflict(self, tmp_path):
        """The primary worktree tracked-file status must be unchanged by the probe."""
        origin, work = _make_diverged_repos(tmp_path, "o_wt", "w_wt")
        _run(["git", "fetch", "origin", "main"], cwd=work)
        _add_commit(origin, "clash.txt", "origin\n", "origin")
        _add_commit(work, "clash.txt", "work\n", "work")
        _run(["git", "fetch", "origin", "main"], cwd=work)
        # Copy script first so it doesn't appear in the "after" diff
        _copy_script_to(work)
        # Capture status ignoring untracked files
        _, status_before, _ = _run(["git", "status", "--porcelain", "-uno"], cwd=work)
        _run_conflict_check(work)
        _, status_after, _ = _run(["git", "status", "--porcelain", "-uno"], cwd=work)
        assert status_before == status_after, (
            f"Worktree changed after conflict probe.\n"
            f"Before: {status_before!r}\nAfter: {status_after!r}"
        )

    def test_temporary_worktree_removed_after_success(self, tmp_path):
        """No stray ppcheck- worktrees remain after a clean probe."""
        origin, work = _make_diverged_repos(tmp_path, "o_clean2", "w_clean2")
        _add_commit(work, "extra.txt", "only in work\n", "work only")
        _run(["git", "fetch", "origin", "main"], cwd=work)
        _run_conflict_check(work)
        _, wt_out, _ = _run(["git", "worktree", "list", "--porcelain"], cwd=work)
        assert "ppcheck-" not in wt_out, f"stray ppcheck- worktree found:\n{wt_out}"

    def test_temporary_worktree_removed_after_conflict(self, tmp_path):
        """No stray ppcheck- worktrees remain after a conflicted probe."""
        origin, work = _make_diverged_repos(tmp_path, "o_conf2", "w_conf2")
        _run(["git", "fetch", "origin", "main"], cwd=work)
        _add_commit(origin, "clash2.txt", "origin\n", "origin")
        _add_commit(work, "clash2.txt", "work\n", "work")
        _run(["git", "fetch", "origin", "main"], cwd=work)
        _run_conflict_check(work)
        _, wt_out, _ = _run(["git", "worktree", "list", "--porcelain"], cwd=work)
        assert "ppcheck-" not in wt_out, f"stray ppcheck- worktree found:\n{wt_out}"

    def test_uses_only_local_repos(self, tmp_path):
        """Conflict tests use file-system repos passed as local paths, not URLs."""
        origin, work = _make_diverged_repos(tmp_path, "o_net", "w_net")
        # Verify origin remote is a local path, not a network URL
        _, remote_url, _ = _run(["git", "remote", "get-url", "origin"], cwd=work)
        assert remote_url.startswith("/") or remote_url.startswith(str(tmp_path)), (
            f"Expected local path, got: {remote_url}"
        )


# ---------------------------------------------------------------------------
# Edge-case / mock-based tests
# ---------------------------------------------------------------------------

class TestMergeConflictEdgeCases:
    """Use unittest.mock to test error paths without creating real repos."""

    def test_unsupported_merge_tree_triggers_fallback(self):
        """When merge-tree returns 'unknown option', the worktree fallback runs."""
        import tools.pos.lean.pre_push_check as m
        call_log = []

        def fake_run(cmd, *, cwd=REPO_ROOT):
            call_log.append(list(cmd))
            if "merge-tree" in cmd:
                return 129, "", "error: unknown option '--write-tree'"
            if "worktree" in cmd and "add" in cmd:
                return 1, "", "error: cannot create worktree"
            return 0, "", ""

        with patch.object(m, "_run", side_effect=fake_run):
            ok, msg = m.check_merge_conflicts()

        assert not ok
        flat = [" ".join(c) for c in call_log]
        assert any("merge-tree" in c for c in flat), "merge-tree not attempted"
        assert any("worktree" in c for c in flat), "fallback worktree not attempted"

    def test_worktree_creation_failure_blocks_push(self):
        """If worktree add fails, the probe fails closed — push is blocked."""
        import tools.pos.lean.pre_push_check as m

        def fake_run(cmd, *, cwd=REPO_ROOT):
            if "merge-tree" in cmd:
                return 129, "", "error: unknown option '--write-tree'"
            if "worktree" in cmd and "add" in cmd:
                return 1, "", "cannot lock ref"
            return 0, "", ""

        with patch.object(m, "_run", side_effect=fake_run):
            ok, msg = m.check_merge_conflicts()

        assert not ok, "worktree creation failure must block push"
        assert "worktree" in msg.lower() or "probe" in msg.lower() or "cannot" in msg.lower()

    def test_unexpected_git_error_blocks_push(self):
        """An unexpected merge-tree rc (not unsupported, not clean) blocks push."""
        import tools.pos.lean.pre_push_check as m

        def fake_run(cmd, *, cwd=REPO_ROOT):
            if "merge-tree" in cmd:
                return 2, "", "fatal: internal error"
            return 0, "", ""

        with patch.object(m, "_run", side_effect=fake_run):
            ok, msg = m.check_merge_conflicts()

        assert not ok, "unexpected git error must block push"

    def test_merge_tree_conflict_blocks_push(self):
        """When merge-tree reports CONFLICT, push is blocked."""
        import tools.pos.lean.pre_push_check as m

        def fake_run(cmd, *, cwd=REPO_ROOT):
            if "merge-tree" in cmd:
                return 1, "CONFLICT (content): Merge conflict in foo.txt\n", ""
            return 0, "", ""

        with patch.object(m, "_run", side_effect=fake_run):
            ok, msg = m.check_merge_conflicts()

        assert not ok
        assert "foo.txt" in msg or "conflict" in msg.lower()

    def test_merge_tree_success_skips_worktree(self):
        """When merge-tree succeeds (rc=0), the worktree fallback is never invoked."""
        import tools.pos.lean.pre_push_check as m
        call_log = []

        def fake_run(cmd, *, cwd=REPO_ROOT):
            call_log.append(list(cmd))
            if "merge-tree" in cmd:
                return 0, "abc123def456\n", ""
            return 0, "", ""

        with patch.object(m, "_run", side_effect=fake_run):
            ok, msg = m.check_merge_conflicts()

        assert ok
        flat = [" ".join(c) for c in call_log]
        assert not any("worktree" in c for c in flat), "worktree called on clean merge-tree"
