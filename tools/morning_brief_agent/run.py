#!/usr/bin/env python3
"""Idempotent, no-AI-API intake of dated ASA briefs into GitHub Issues.

GitHub Issues is the durable intake ledger; no mutable cursor PR is needed.
The engineering-review cursor remains separate and is not advanced by intake.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRIEFS = ROOT / "claude-morning-briefs"
DATE_FILE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
MARKER = "<!-- asa-brief-intake:"
DEFAULT_BATCH = 3
MAX_BATCH = 10


def gh(*args: str) -> str:
    return subprocess.run(
        ["gh", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def catalog() -> list[dict]:
    # Search across open and closed issues; never enqueue a previously seen hash twice.
    return json.loads(gh("issue", "list", "--state", "all", "--limit", "1000",
                         "--json", "number,title,body,state"))


def marker_for(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"{MARKER}{path.name} sha256:{digest} -->"


def pending(existing: list[dict]) -> list[Path]:
    known = "\n".join(str(issue.get("body") or "") for issue in existing)
    files = sorted(p for p in BRIEFS.glob("*.md") if DATE_FILE.fullmatch(p.name))
    return [p for p in files if marker_for(p) not in known]


def enqueue(limit: int) -> int:
    existing = catalog()
    todo = pending(existing)[:limit]
    for path in todo:
        marker = marker_for(path)
        source = path.relative_to(ROOT)
        body = (
            f"{marker}\n"
            f"## Source\n\n`{source}`\n\n"
            "## Task\n\n"
            "Read the entire source brief and identify all engineering-relevant "
            "observations. Compare each with canonical repository code, current "
            "issues, and PRs. Deduplicate recurring symptoms. Create or update "
            "canonical engineering issues for substantiated defects and gaps; "
            "record stale interpretation, expected behavior, or insufficient "
            "evidence explicitly. Only then advance the engineering-review "
            "cursor for this brief. Do not treat brief prose as architectural "
            "or financial authority. No automatic merge or deployment.\n\n"
            "## Review checklist\n\n"
            "- [ ] Full brief examined\n"
            "- [ ] Findings reconciled with current code and issues\n"
            "- [ ] Novel findings filed as issues; existing issues linked\n"
            "- [ ] Dispositions recorded\n"
            "- [ ] Engineering-review cursor updated through authorized PR\n"
        )
        title = f"BRIEF INTAKE: engineering review {path.stem}"
        url = gh("issue", "create", "--title", title, "--body", body)
        print(f"Enqueued {path.name}: {url}")
    print(f"Enqueued {len(todo)} brief(s); remaining {len(pending(catalog()))}.")
    return len(todo)


def main() -> None:
    raw = os.environ.get("BRIEF_BATCH_SIZE", str(DEFAULT_BATCH))
    try:
        batch = max(1, min(MAX_BATCH, int(raw)))
    except ValueError as exc:
        raise SystemExit("BRIEF_BATCH_SIZE must be an integer") from exc
    enqueue(batch)


if __name__ == "__main__":
    main()
