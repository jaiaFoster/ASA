"""
Entrypoint invariant checker for Lean POS.

Validates that AGENTS.md and CURRENT_STATE.md satisfy Lean POS invariants:
- No legacy pointer text
- No legacy tool commands
- Correct lean content references
- CURRENT_STATE.md matches fresh generation
- project-state notes align with cutover plan

Exit codes:
  0  all invariants pass
  1  one or more invariants failed
  2  usage error
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# Legacy pointer / tool strings that must NOT appear in root entrypoints
LEGACY_POINTER_TEXTS = [
    "project/generated/AGENTS.md",
    "project/generated/CURRENT_STATE.md",
    "project/generated/MANAGER_INBOX.md",
    "project/generated/",
    "Regenerate with: python tools/pos/generate.py",
    "python tools/pos/generate.py",
    "python tools/pos/validate.py",
]

AGENTS_REQUIRED = [
    "project/lean/state/project-state.yaml",
    "tools/pos/lean/",
    "CURRENT_STATE.md",
]

TOKEN_BUDGET_AGENTS = 1000
GENERATED_AT_CI = "2000-01-01T00:00:00Z"


def check_agents() -> list[str]:
    errors: list[str] = []
    path = REPO_ROOT / "AGENTS.md"
    if not path.exists():
        return ["E001: AGENTS.md missing"]
    content = path.read_text(encoding="utf-8")

    for legacy in LEGACY_POINTER_TEXTS:
        if legacy in content:
            errors.append(f"E002: AGENTS.md contains legacy text: {legacy!r}")

    for required in AGENTS_REQUIRED:
        if required not in content:
            errors.append(f"E003: AGENTS.md missing required reference: {required!r}")

    # Token budget check
    try:
        from tools.pos.lean.schemas import estimate_tokens
        tokens = estimate_tokens(content)
        if tokens > TOKEN_BUDGET_AGENTS:
            errors.append(f"E005: AGENTS.md exceeds {TOKEN_BUDGET_AGENTS}-token budget ({tokens} tokens)")
    except ImportError:
        pass

    return errors


def check_current_state() -> list[str]:
    errors: list[str] = []
    path = REPO_ROOT / "CURRENT_STATE.md"
    if not path.exists():
        return ["E006: CURRENT_STATE.md missing"]
    content = path.read_text(encoding="utf-8")

    for legacy in LEGACY_POINTER_TEXTS:
        if legacy in content:
            errors.append(f"E007: CURRENT_STATE.md contains legacy text: {legacy!r}")

    # Compare with fresh generation
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
        tmp = f.name
    result = subprocess.run(
        [
            sys.executable,
            "tools/pos/lean/generate.py",
            "current-state",
            "--project-state", "project/lean/state/project-state.yaml",
            "--generated-at", GENERATED_AT_CI,
            "--output", tmp,
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        errors.append(f"E008: Lean generator failed: {result.stderr.strip()}")
    else:
        generated = Path(tmp).read_text(encoding="utf-8")
        committed = content
        if generated != committed:
            errors.append(
                "E008: CURRENT_STATE.md does not match fresh generation. "
                "Regenerate with: python tools/pos/lean/generate.py current-state "
                "--project-state project/lean/state/project-state.yaml "
                f"--generated-at {GENERATED_AT_CI} --output CURRENT_STATE.md"
            )

    return errors


def check_project_state_alignment() -> list[str]:
    """Verify project-state notes phase aligns with cutover plan."""
    errors: list[str] = []
    try:
        import yaml
        state_path = REPO_ROOT / "project" / "lean" / "state" / "project-state.yaml"
        plan_path = REPO_ROOT / "project" / "lean" / "migration" / "cutover-plan.yaml"
        if not state_path.exists() or not plan_path.exists():
            return []
        state = yaml.safe_load(state_path.read_text())
        plan = yaml.safe_load(plan_path.read_text())
        notes = state.get("notes", "")
        phases = plan.get("phases", [])
        pending = [p for p in phases if p.get("status") != "complete"]
        if pending:
            first_pending = pending[0]["id"]
            if first_pending not in notes:
                errors.append(
                    f"E009: project-state notes do not reference first pending phase {first_pending!r}. "
                    "Update notes to match cutover plan."
                )
            if len(pending) > 1:
                second_pending = pending[1]["id"]
                if second_pending not in notes:
                    errors.append(
                        f"E010: project-state notes do not reference next pending phase {second_pending!r}."
                    )
    except Exception as exc:
        errors.append(f"E009: phase alignment check failed: {exc}")
    return errors


def main() -> int:
    all_errors: list[str] = []
    all_errors.extend(check_agents())
    all_errors.extend(check_current_state())
    all_errors.extend(check_project_state_alignment())

    if all_errors:
        print("FAIL: entrypoint invariants violated:")
        for e in all_errors:
            print(f"  {e}")
        return 1

    print("OK: all entrypoint invariants pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
