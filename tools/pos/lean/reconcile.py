#!/usr/bin/env python3
"""
Lean POS reconciliation CLI.

Derives operational state from GitHub Issues and pull requests.
Read-only. Never modifies local canonical records or GitHub.

Exit codes:
  0  reconciled without conflict
  1  reconciliation conflict
  2  invalid input or configuration
  3  required remote data unavailable

Error codes: G001–G008 (see tools/pos/lean/schemas.py)

Usage examples:

  # Fixture mode (no network):
  python tools/pos/lean/reconcile.py \\
    --fixture tests/pos/lean/fixtures/github/merged-authorized.yaml \\
    --format yaml

  # Live mode (network + token):
  python tools/pos/lean/reconcile.py \\
    --repo jaiaFoster/ASA --issue 12 --pr 4 \\
    --format yaml
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml

from tools.pos.lean.schemas import (
    RECON_INVALID_INPUT,
    RECON_REMOTE_UNAVAILABLE,
    RECON_CONFLICTING_STATE,
)
from tools.pos.lean.github import FixtureAdapter, LiveAdapter, WriteAttemptError
from tools.pos.lean.derived import derive


def _output(result_dict: dict, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(result_dict, indent=2, sort_keys=False))
    else:
        print(yaml.dump(result_dict, default_flow_style=False, allow_unicode=True, sort_keys=False), end="")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Lean POS reconciliation — read-only, no GitHub writes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture", type=Path, metavar="PATH",
                      help="Pre-normalized YAML fixture (no network required)")
    mode.add_argument("--repo", metavar="OWNER/REPO",
                      help="GitHub repository for live fetch")

    p.add_argument("--issue", type=int, metavar="N", help="Issue number (live mode)")
    p.add_argument("--pr", type=int, metavar="N", help="PR number (live mode)")
    p.add_argument("--token", metavar="TOKEN",
                   help="GitHub token for live mode (or set GITHUB_TOKEN env var)")
    p.add_argument("--observed-at", metavar="ISO8601",
                   help="Override observed_at timestamp for deterministic test output")
    p.add_argument("--format", choices=["yaml", "json"], default="yaml",
                   help="Output format (default: yaml)")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # ------------------------------------------------------------------
    # Acquire snapshot
    # ------------------------------------------------------------------
    try:
        if args.fixture is not None:
            adapter = FixtureAdapter(args.fixture)
            snapshot = adapter.fetch()
            if args.observed_at:
                # Patch observed_at for test determinism
                raw = snapshot.raw()
                raw["observed_at"] = args.observed_at
                from tools.pos.lean.github import GitHubSnapshot
                snapshot = GitHubSnapshot(raw)
        else:
            token = args.token or os.environ.get("GITHUB_TOKEN")
            adapter = LiveAdapter(args.repo, token=token)
            snapshot = adapter.fetch(
                issue_number=args.issue,
                pr_number=args.pr,
                observed_at=args.observed_at,
            )
    except FileNotFoundError as exc:
        print(f"[{RECON_REMOTE_UNAVAILABLE}] {exc}", file=sys.stderr)
        return 3
    except RuntimeError as exc:
        msg = str(exc)
        if RECON_REMOTE_UNAVAILABLE in msg:
            print(msg, file=sys.stderr)
            return 3
        print(f"[{RECON_INVALID_INPUT}] {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"[{RECON_INVALID_INPUT}] {exc}", file=sys.stderr)
        return 2
    except WriteAttemptError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    # ------------------------------------------------------------------
    # Derive state
    # ------------------------------------------------------------------
    result = derive(snapshot)
    _output(result.to_dict(), args.format)

    if result.conflicts:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
