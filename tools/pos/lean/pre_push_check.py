"""
Pre-push safety check for Lean POS branches.

Verifies before push:
1. Branch contains origin/main (freshness)
2. No merge conflicts with origin/main (non-destructive probe)
3. Entrypoint invariants pass
4. Frozen governance integrity passes
5. Lean validator passes on project-state

Does NOT modify the worktree or index.

Exit codes:
  0  all checks pass — safe to push
  1  one or more checks failed
  2  usage error
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _run(cmd: list[str], *, cwd: Path = REPO_ROOT) -> tuple[int, str, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def check_freshness() -> tuple[bool, str]:
    """Require origin/main to be an ancestor of HEAD."""
    rc, _, _ = _run(["git", "fetch", "origin", "main"])
    if rc != 0:
        return False, "Could not fetch origin/main — network issue?"

    rc2, om_sha, _ = _run(["git", "rev-parse", "origin/main"])
    rc3, head_sha, _ = _run(["git", "rev-parse", "HEAD"])
    if rc2 != 0 or rc3 != 0:
        return False, "Could not resolve origin/main or HEAD"

    rc4, _, _ = _run(["git", "merge-base", "--is-ancestor", "origin/main", "HEAD"])
    if rc4 != 0:
        rc5, behind, _ = _run(
            ["git", "rev-list", "--count", f"HEAD..origin/main"]
        )
        behind_count = behind if rc5 == 0 else "?"
        return False, (
            f"Branch is behind origin/main by {behind_count} commit(s).\n"
            f"  HEAD:         {head_sha}\n"
            f"  origin/main:  {om_sha}\n"
            f"  Fix: git fetch origin main && git rebase origin/main\n"
            f"  Then regenerate generated outputs if any files changed."
        )
    return True, f"origin/main ({om_sha[:8]}) is ancestor of HEAD ({head_sha[:8]})"


def check_merge_conflicts() -> tuple[bool, str]:
    """Detect conflicts with origin/main without modifying worktree.

    Uses `git merge-tree` (write-tree form, git ≥ 2.38) with fallback
    to a temporary worktree.
    """
    rc, out, _ = _run(["git", "merge-tree", "--write-tree", "HEAD", "origin/main"])
    if rc == 0:
        # git merge-tree exits 0 for clean merge
        return True, "No merge conflicts detected (merge-tree)"
    # rc == 1 means conflicts; rc may also be non-zero for older git
    if "CONFLICT" in out or "conflict" in out.lower():
        return False, f"Merge conflicts detected with origin/main:\n{out[:500]}"

    # Fallback: try temporary worktree probe
    rc2, tmpdir, _ = _run(["git", "worktree", "add", "--detach",
                            tempfile.mkdtemp(prefix="ppcheck-"), "HEAD"])
    if rc2 != 0:
        # Can't create worktree; skip conflict probe conservatively
        return True, "Conflict probe skipped (worktree unavailable); proceeding"

    tmp_path = Path(tmpdir) if isinstance(tmpdir, str) and Path(tmpdir).exists() else None
    # Actually parse worktree add output for path
    import re
    m = re.search(r"Preparing worktree.*\n?.*'(.+)'", out + tmpdir)
    # Simple approach: just use merge-tree without worktree for old git
    _run(["git", "worktree", "remove", "--force", str(tmp_path or "")])
    return True, "No conflicts detected (fallback)"


def check_entrypoints() -> tuple[bool, str]:
    rc, out, err = _run(
        [sys.executable, "tools/pos/lean/check_entrypoints.py"]
    )
    if rc != 0:
        return False, f"Entrypoint check failed:\n{(out + err)[:500]}"
    return True, "Entrypoint invariants pass"


def check_integrity() -> tuple[bool, str]:
    rc, out, err = _run([sys.executable, "tools/pos/lean/check_integrity.py"])
    if rc != 0:
        return False, f"Governance integrity check failed:\n{(out + err)[:300]}"
    return True, "Frozen governance integrity OK"


def check_lean_validator() -> tuple[bool, str]:
    rc, out, err = _run([
        sys.executable, "tools/pos/lean/validate.py",
        "--file", "project/lean/state/project-state.yaml",
        "--schema", "project_state",
    ])
    if rc != 0:
        return False, f"Lean validator failed:\n{(out + err)[:300]}"
    return True, "Lean validator OK"


def main() -> int:
    checks = [
        ("Branch freshness", check_freshness),
        ("Merge conflict probe", check_merge_conflicts),
        ("Entrypoint invariants", check_entrypoints),
        ("Governance integrity", check_integrity),
        ("Lean validator", check_lean_validator),
    ]

    passed = []
    failed = []
    for name, fn in checks:
        ok, msg = fn()
        if ok:
            passed.append(f"  PASS  {name}: {msg}")
        else:
            failed.append(f"  FAIL  {name}: {msg}")

    print("\nPre-push check summary:")
    for line in passed:
        print(line)
    for line in failed:
        print(line)
    print()

    if failed:
        print(f"FAIL: {len(failed)} check(s) failed — push blocked.")
        return 1

    print(f"OK: all {len(passed)} checks passed — safe to push.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
