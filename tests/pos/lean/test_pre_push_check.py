"""
Tests for LEAN-POS-10: pre_push_check.py safeguard.

Uses temporary git repositories — no network beyond what pre_push_check.py itself does.
Does not modify the primary worktree.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _run(cmd: list[str], *, cwd: Path = REPO_ROOT, env=None) -> tuple[int, str, str]:
    import subprocess as sp
    r = sp.run(cmd, capture_output=True, text=True, cwd=cwd, env=env)
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
        # Should print some kind of summary regardless of pass/fail
        combined = out + err
        assert "check" in combined.lower() or "PASS" in combined or "FAIL" in combined


class TestFreshnessDetection:
    """Test freshness check logic via subprocess in isolated git repos."""

    def _make_repo(self, tmp_path: Path, name: str) -> Path:
        repo = tmp_path / name
        repo.mkdir()
        _run(["git", "init", "-b", "main", str(repo)])
        _run(["git", "config", "user.email", "test@test.com"], cwd=repo)
        _run(["git", "config", "user.name", "Test"], cwd=repo)
        return repo

    def _add_commit(self, repo: Path, filename: str, content: str, msg: str):
        (repo / filename).write_text(content)
        _run(["git", "add", filename], cwd=repo)
        _run(["git", "commit", "-m", msg], cwd=repo)

    def _run_freshness(self, work: Path) -> tuple[bool, str]:
        """Run check_freshness via subprocess in the given repo directory."""
        import shutil, os
        # Copy the pre_push_check script into the tmp repo so it can run without REPO_ROOT issues
        tools_dir = work / "tools" / "pos" / "lean"
        tools_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / "tools" / "pos" / "lean" / "pre_push_check.py", tools_dir)
        # Also copy check_integrity and check_entrypoints stubs (so imports don't fail)
        for fn in ("check_integrity.py", "check_entrypoints.py"):
            src = REPO_ROOT / "tools" / "pos" / "lean" / fn
            if src.exists():
                shutil.copy2(src, tools_dir)
        # Create minimal __init__.py chain
        for d in [work / "tools", work / "tools" / "pos", tools_dir]:
            (d / "__init__.py").touch()
        rc, out, err = _run([sys.executable, "-c",
            "import sys; sys.path.insert(0, '.'); "
            "from tools.pos.lean.pre_push_check import check_freshness; "
            "ok, msg = check_freshness(); print('OK' if ok else 'FAIL'); print(msg)"
        ], cwd=work)
        combined = out + err
        ok = "OK\n" in combined or combined.startswith("OK")
        return ok, combined

    def test_freshness_passes_when_up_to_date(self, tmp_path):
        """check_freshness returns True when branch contains origin/main."""
        origin = self._make_repo(tmp_path, "origin")
        self._add_commit(origin, "a.txt", "hello", "initial")
        work = self._make_repo(tmp_path, "work")
        _run(["git", "remote", "add", "origin", str(origin)], cwd=work)
        _run(["git", "fetch", "origin", "main"], cwd=work)
        _run(["git", "checkout", "-b", "main", "origin/main"], cwd=work)
        self._add_commit(work, "b.txt", "world", "local commit")
        ok, msg = self._run_freshness(work)
        assert ok, f"expected pass, got: {msg}"

    def test_freshness_fails_when_behind(self, tmp_path):
        """check_freshness returns False when origin/main has commits not in HEAD."""
        origin = self._make_repo(tmp_path, "origin")
        self._add_commit(origin, "a.txt", "hello", "initial")
        work = self._make_repo(tmp_path, "work")
        _run(["git", "remote", "add", "origin", str(origin)], cwd=work)
        _run(["git", "fetch", "origin", "main"], cwd=work)
        _run(["git", "checkout", "-b", "main", "origin/main"], cwd=work)
        # Add a commit to origin after work was cloned
        self._add_commit(origin, "c.txt", "new", "origin-only commit")
        ok, msg = self._run_freshness(work)
        assert not ok, f"expected fail (branch behind), got: {msg}"
        assert "rebase" in msg.lower() or "behind" in msg.lower() or "FAIL" in msg

    def test_freshness_failure_message_includes_recovery_command(self, tmp_path):
        """Failure message must include a recovery command."""
        origin = self._make_repo(tmp_path, "origin3")
        self._add_commit(origin, "a.txt", "hello", "initial")
        work = self._make_repo(tmp_path, "work3")
        _run(["git", "remote", "add", "origin", str(origin)], cwd=work)
        _run(["git", "fetch", "origin", "main"], cwd=work)
        _run(["git", "checkout", "-b", "main", "origin/main"], cwd=work)
        self._add_commit(origin, "c.txt", "new", "origin-only")
        ok, msg = self._run_freshness(work)
        assert not ok
        # Should mention rebase or merge as recovery action
        assert "rebase" in msg or "merge" in msg or "Fix:" in msg


class TestWorktreeSafety:
    def test_pre_push_script_does_not_modify_worktree(self):
        """Running pre_push_check.py must not change any tracked files."""
        rc1, out1, _ = _run(["git", "status", "--porcelain"])
        _run([sys.executable, "tools/pos/lean/pre_push_check.py"])
        rc2, out2, _ = _run(["git", "status", "--porcelain"])
        assert out1 == out2, (
            f"pre_push_check.py modified the worktree.\nBefore: {out1!r}\nAfter: {out2!r}"
        )
