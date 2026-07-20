#!/usr/bin/env python3
"""Collect a bounded, redacted Railway diagnostic snapshot."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.deployment_observer.observer import CommandFailure, collect


def _event() -> dict[str, Any]:
    path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not path:
        return {}
    parsed: Any = json.loads(Path(path).read_text())
    return parsed if isinstance(parsed, dict) else {}


def _boolean(value: str) -> bool:
    return value.lower() not in {"false", "0", "no"}


def main() -> int:
    output_dir = Path(os.environ.get("OBSERVER_OUTPUT_DIR", ".artifacts/railway-deployment"))
    try:
        deployment, _, summary = collect(
            output_dir=output_dir,
            service=os.environ.get("RAILWAY_SERVICE", "ASA"),
            environment=os.environ.get("RAILWAY_ENVIRONMENT", "production"),
            explicit_id=os.environ.get("INPUT_DEPLOYMENT_ID"),
            event=_event(),
            include_runtime_logs=_boolean(os.environ.get("INPUT_INCLUDE_RUNTIME_LOGS", "true")),
        )
        if summary_path := os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(summary_path).open("a") as handle:
                handle.write(summary)
        if output_path := os.environ.get("GITHUB_OUTPUT"):
            with Path(output_path).open("a") as handle:
                handle.write(f"deployment_id={deployment.deployment_id}\n")
        return 0
    except Exception as error:
        # Never retain partially written log artifacts after an unexpected failure.
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        if isinstance(error, CommandFailure):
            failure = {
                "version": 1,
                "collection_status": "failed",
                "command_category": error.category,
                "exit_code": error.exit_code,
                "stderr": error.stderr,
                "stdout": error.stdout,
            }
        else:
            failure = {
                "version": 1,
                "collection_status": "failed",
                "command_category": "observer",
                "exit_code": None,
                "stderr": "",
                "stdout": "",
            }
        (output_dir / "failure.json").write_text(json.dumps(failure, indent=2) + "\n")
        safe_summary = (
            "## Railway deployment observer\n\n"
            "Collection failed safely. No deployment logs were uploaded. "
            f"Command category: `{failure['command_category']}`. "
            f"Exit code: `{failure['exit_code']}`.\n"
        )
        (output_dir / "summary.md").write_text(safe_summary)
        if summary_path := os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(summary_path).open("a") as handle:
                handle.write(safe_summary)
        print("Railway deployment observation failed safely; raw logs were discarded.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
