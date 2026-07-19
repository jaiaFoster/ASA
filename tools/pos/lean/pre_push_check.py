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

import re
import shutil
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
        rc5, behind, _ = _run(["git", "rev-list", "--count", "HEAD..origin/main"])
        behind_count = behind if rc5 == 0 else "?"
        return False, (
            f"Branch is behind origin/main by {behind_count} commit(s).\n"
            f"  HEAD:         {head_sha}\n"
            f"  origin/main:  {om_sha}\n"
            f"  Fix: git fetch origin main && git rebase origin/main\n"
            f"  Then regenerate generated outputs if any files changed."
        )
    return True, f"origin/main ({om_sha[:8]}) is ancestor of HEAD ({head_sha[:8]})"


def _conflict_probe_merge_tree() -> tuple[str, bool, str]:
    """Try git merge-tree --write-tree. Returns (status, ok, detail).

    status values: 'clean', 'conflict', 'unsupported', 'error'
    """
    rc, out, err = _run(["git", "merge-tree", "--write-tree", "HEAD", "origin/main"])
    combined = out + "\n" + err

    if rc == 0:
        return "clean", True, "No merge conflicts detected (merge-tree)"

    if rc == 1 and ("CONFLICT" in combined or "conflict" in combined.lower()):
        paths = re.findall(r'CONFLICT[^:]*:\s*(\S+)', combined)
        path_info = ", ".join(paths) if paths else "(see output)"
        snippet = combined[:400]
        return "conflict", False, f"Merge conflicts with origin/main: {path_info}\n{snippet}"

    # rc != 0 and no CONFLICT text: distinguish unsupported option from other errors
    is_option_error = any(
        tok in combined.lower()
        for tok in ("unknown option", "unknown switch", "usage:", "unrecognized",
                    "invalid option", "not a git command")
    )
    if rc not in (0, 1):
        if is_option_error:
            return "unsupported", False, combined[:200]
        # Unexpected exit code with no option-error text — fail closed
        return "error", False, f"merge-tree rc={rc}, unexpected:\n{combined[:200]}"

    # rc==1 with no conflict markers — treat as unexpected error, fail closed
    return "error", False, f"merge-tree rc=1 with no conflict markers:\n{combined[:200]}"


def _conflict_probe_worktree() -> tuple[bool, str]:
    """Fallback: detect conflicts via a temporary detached worktree.

    Never modifies the primary worktree or index.
    Always cleans up the temporary worktree, even on error.
    Fails closed if the probe cannot be completed.
    """
    tmp_parent = Path(tempfile.mkdtemp(prefix="ppcheck-"))
    wt_path = tmp_parent / "wt"   # must not exist before git worktree add

    try:
        rc_add, out_add, err_add = _run(
            ["git", "worktree", "add", "--detach", str(wt_path), "HEAD"]
        )
        if rc_add != 0:
            return False, (
                "Conflict probe failed: cannot create temporary worktree:\n"
                f"{(out_add + err_add)[:200]}"
            )

        try:
            rc_merge, out_merge, err_merge = _run(
                ["git", "merge", "--no-commit", "--no-ff", "origin/main"],
                cwd=wt_path,
            )

            # Inspect unmerged paths
            _, unmerged, _ = _run(
                ["git", "diff", "--name-only", "--diff-filter=U"],
                cwd=wt_path,
            )
            conflict_paths = [p for p in unmerged.splitlines() if p]

            if conflict_paths:
                _run(["git", "merge", "--abort"], cwd=wt_path)
                path_info = ", ".join(conflict_paths)
                return False, f"Merge conflicts with origin/main: {path_info}"

            if rc_merge != 0:
                # Merge failed but reported no unmerged files — unexpected error
                _run(["git", "merge", "--abort"], cwd=wt_path)
                return False, (
                    f"Merge probe failed unexpectedly (rc={rc_merge}):\n"
                    f"{(out_merge + err_merge)[:200]}"
                )

            # Clean merge — abort since we used --no-commit
            _run(["git", "merge", "--abort"], cwd=wt_path)
            return True, "No merge conflicts detected (worktree fallback)"

        finally:
            _run(["git", "worktree", "remove", "--force", str(wt_path)])

    finally:
        _run(["git", "worktree", "prune"])
        shutil.rmtree(tmp_parent, ignore_errors=True)


def check_merge_conflicts() -> tuple[bool, str]:
    """Detect conflicts with origin/main without modifying worktree or index.

    Primary: git merge-tree --write-tree (git >= 2.38, non-destructive).
    Fallback: temporary detached worktree + git merge --no-commit.
    Fails closed on any unverified or unexpected result.
    """
    status, ok, detail = _conflict_probe_merge_tree()

    if status == "clean":
        return True, detail
    if status == "conflict":
        return False, detail
    if status == "error":
        # Unexpected merge-tree error — fail closed without fallback
        return False, f"Conflict probe failed (merge-tree): {detail}"

    # status == "unsupported" — fall through to worktree probe
    return _conflict_probe_worktree()


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
