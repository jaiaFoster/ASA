#!/usr/bin/env python3
"""
Lean POS view generator.

Generates two non-canonical operational views from lean canonical records
and GitHub reconciliation output. No GitHub writes. No canonical mutations.

Subcommands:
  current-state   Generate project/lean/generated/CURRENT_STATE.md
  worker-context  Generate project/lean/generated/WORKER_CONTEXT.yaml

Exit codes:
  0  generation succeeded
  1  generation failed (previous output preserved)
  2  invalid input or configuration

Usage examples:
  python tools/pos/lean/generate.py current-state \\
    --project-state project/lean/fixtures/valid/project-state.yaml \\
    --reconciliation tests/pos/lean/fixtures/views/project-reconciliation.yaml \\
    --output project/lean/generated/CURRENT_STATE.md \\
    --generated-at 2026-07-18T18:00:00Z

  python tools/pos/lean/generate.py worker-context \\
    --handoff project/lean/fixtures/valid/worker-handoff.yaml \\
    --reconciliation tests/pos/lean/fixtures/views/handoff-reconciliation.yaml \\
    --output project/lean/generated/WORKER_CONTEXT.yaml \\
    --generated-at 2026-07-18T18:00:00Z
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml

from tools.pos.lean.schemas import (
    REPO_ROOT,
    LEAN_GENERATED_DIR,
    TOKEN_BUDGET_WORKER_CONTEXT_NORMAL,
    TOKEN_BUDGET_WORKER_CONTEXT_ELEVATED,
    load_yaml,
)
from tools.pos.lean.views import (
    render_current_state,
    render_worker_context,
    estimate_worker_context_tokens,
)


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------

def atomic_write(path: Path, content: str | bytes) -> None:
    """Write content atomically: write to temp, rename. Failure preserves old file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "wb" if isinstance(content, bytes) else "w"
    encoding = None if isinstance(content, bytes) else "utf-8"
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".lean-gen-", suffix=".tmp")
    try:
        with os.fdopen(fd, mode, encoding=encoding) as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def _load_yaml_arg(path_str: str | None, label: str) -> dict | None:
    if not path_str:
        return None
    p = Path(path_str)
    if not p.exists():
        print(f"[ERROR] {label} not found: {p}", file=sys.stderr)
        sys.exit(2)
    try:
        data = load_yaml(p)
    except Exception as exc:
        print(f"[ERROR] {label} YAML parse error in {p}: {exc}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(data, dict):
        print(f"[ERROR] {label} must be a YAML mapping: {p}", file=sys.stderr)
        sys.exit(2)
    return data


def _load_trial_rules(path_str: str | None) -> list[dict]:
    if not path_str:
        return []
    p = Path(path_str)
    if not p.exists():
        return []
    try:
        data = load_yaml(p)
    except Exception:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "rules" in data:
        return data["rules"]
    return []


def _load_reconciliation_live(
    repo: str,
    issue: int | None,
    pr: int | None,
    token: str | None,
    observed_at: str | None,
) -> dict:
    """Fetch live reconciliation; return as dict matching reconcile output format."""
    from tools.pos.lean.github import LiveAdapter
    from tools.pos.lean.derived import derive
    adapter = LiveAdapter(repo, token=token)
    snapshot = adapter.fetch(issue_number=issue, pr_number=pr, observed_at=observed_at)
    result = derive(snapshot)
    return result.to_dict()


# ---------------------------------------------------------------------------
# Subcommand: current-state
# ---------------------------------------------------------------------------

def cmd_current_state(args: argparse.Namespace) -> int:
    project_state = _load_yaml_arg(args.project_state, "project-state")
    if project_state is None:
        print("[ERROR] --project-state is required", file=sys.stderr)
        return 2

    reconciliation: dict | None = None
    if args.reconciliation:
        reconciliation = _load_yaml_arg(args.reconciliation, "reconciliation")
    elif args.repo:
        token = args.token or os.environ.get("GITHUB_TOKEN")
        reconciliation = _load_reconciliation_live(
            args.repo, args.issue, args.pr, token, args.generated_at
        )

    trial_rules = _load_trial_rules(args.trial_rules)
    generated_at = args.generated_at or _derive_timestamp()

    content = render_current_state(
        project_state=project_state,
        reconciliation=reconciliation,
        trial_rules=trial_rules,
        generated_at=generated_at,
        recently_accepted_limit=getattr(args, "accepted_limit", 5),
    )

    out_path = Path(args.output) if args.output else LEAN_GENERATED_DIR / "CURRENT_STATE.md"

    try:
        atomic_write(out_path, content)
    except Exception as exc:
        print(f"[ERROR] Failed to write {out_path}: {exc}", file=sys.stderr)
        return 1

    print(f"Generated: {out_path}")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: worker-context
# ---------------------------------------------------------------------------

def cmd_worker_context(args: argparse.Namespace) -> int:
    handoff = _load_yaml_arg(args.handoff, "handoff")
    if handoff is None:
        print("[ERROR] --handoff is required", file=sys.stderr)
        return 2

    # Validate handoff has required fields
    required = ("v", "id", "goal", "scope", "lock", "accept", "risk", "deliver")
    missing = [f for f in required if f not in handoff]
    if missing:
        print(f"[ERROR] handoff is missing required fields: {missing}", file=sys.stderr)
        return 2

    reconciliation: dict | None = None
    if args.reconciliation:
        reconciliation = _load_yaml_arg(args.reconciliation, "reconciliation")
    elif args.repo:
        token = args.token or os.environ.get("GITHUB_TOKEN")
        reconciliation = _load_reconciliation_live(
            args.repo, args.issue, args.pr, token, args.generated_at
        )

    trial_rules = _load_trial_rules(args.trial_rules)
    generated_at = args.generated_at or _derive_timestamp()
    repository = args.repo or (reconciliation or {}).get("repository", "")
    base_ref = getattr(args, "base_ref", None) or "main"

    ctx = render_worker_context(
        handoff=handoff,
        reconciliation=reconciliation,
        trial_rules=trial_rules,
        generated_at=generated_at,
        repository=repository,
        base_ref=base_ref,
    )

    # Token budget check
    estimated = estimate_worker_context_tokens(ctx)
    risk = handoff.get("risk", "R2")
    budget = TOKEN_BUDGET_WORKER_CONTEXT_ELEVATED if risk in ("R3", "R4", "R5") else TOKEN_BUDGET_WORKER_CONTEXT_NORMAL
    if estimated > budget:
        print(
            f"[WARNING] Estimated token count ({estimated}) exceeds budget ({budget}) for risk={risk}",
            file=sys.stderr,
        )

    content_str = yaml.dump(
        ctx,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )

    out_path = Path(args.output) if args.output else LEAN_GENERATED_DIR / "WORKER_CONTEXT.yaml"

    try:
        atomic_write(out_path, content_str)
    except Exception as exc:
        print(f"[ERROR] Failed to write {out_path}: {exc}", file=sys.stderr)
        return 1

    print(f"Generated: {out_path} (~{estimated} tokens)")
    return 0


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _derive_timestamp() -> str:
    import datetime
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Lean POS view generator. No GitHub writes. No canonical mutations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="command", required=True)

    # --- current-state ---
    cs = sub.add_parser("current-state", help="Generate CURRENT_STATE.md")
    cs.add_argument("--project-state", metavar="PATH", required=True,
                    help="project_state YAML file")
    cs.add_argument("--trial-rules", metavar="PATH",
                    help="YAML file with a list of trial rule records")
    _add_reconciliation_args(cs)
    cs.add_argument("--output", metavar="PATH",
                    help="Output path (default: project/lean/generated/CURRENT_STATE.md)")
    cs.add_argument("--generated-at", metavar="ISO8601",
                    help="Override generation timestamp")
    cs.add_argument("--accepted-limit", type=int, default=5, metavar="N",
                    help="Max recently-accepted items to render (default: 5)")

    # --- worker-context ---
    wc = sub.add_parser("worker-context", help="Generate WORKER_CONTEXT.yaml")
    wc.add_argument("--handoff", metavar="PATH", required=True,
                    help="worker_handoff YAML file")
    wc.add_argument("--trial-rules", metavar="PATH",
                    help="YAML file with a list of trial rule records")
    wc.add_argument("--base-ref", metavar="REF", default="main",
                    help="Base git ref for this handoff (default: main)")
    _add_reconciliation_args(wc)
    wc.add_argument("--output", metavar="PATH",
                    help="Output path (default: project/lean/generated/WORKER_CONTEXT.yaml)")
    wc.add_argument("--generated-at", metavar="ISO8601",
                    help="Override generation timestamp")

    return p


def _add_reconciliation_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--reconciliation", metavar="PATH",
                       help="Pre-computed reconciliation YAML (no network)")
    group.add_argument("--repo", metavar="OWNER/REPO",
                       help="GitHub repository for live reconciliation")
    parser.add_argument("--issue", type=int, metavar="N", help="Issue number (live mode)")
    parser.add_argument("--pr", type=int, metavar="N", help="PR number (live mode)")
    parser.add_argument("--token", metavar="TOKEN",
                        help="GitHub token (or set GITHUB_TOKEN env var)")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "current-state":
        return cmd_current_state(args)
    if args.command == "worker-context":
        return cmd_worker_context(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
