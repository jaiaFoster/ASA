#!/usr/bin/env python3
"""ASA morning-brief tooling CLI (stdlib only; no AI API; REST via ``gh api``).

  intake         enqueue new/revised briefs as GitHub issues (idempotent; GitHub Actions owns this)
  status         per-brief state derived from GitHub
  ledger-record  validate and post a per-brief ledger record (triage routine)
  claim          acquire|heartbeat|release|status for an engineering issue (worker routine)
  snapshot       dump all issues + open PRs to a local JSON file for grep (paginated)
  candidates     ranked, eligible engineering issues (worker routine)
  sync-cursor    regenerate the derived ENGINEERING_REVIEW_CURSOR.yaml mirror
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # allow `python tools/morning_brief_agent/run.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "tools.morning_brief_agent"

from . import claims, ledger, selection
from .briefs import ROOT, Brief, discover
from .github_api import GitHubClient

DEFAULT_REPO = "jaiaFoster/ASA"
DEFAULT_BATCH = 3
MAX_BATCH = 10
INTAKE_LABEL = "brief-intake"
TITLE_PREFIX = "BRIEF INTAKE: engineering review "
CONVENTION_LABELS = (
    (INTAKE_LABEL, "5319e7", "Morning brief intake ticket"),
    ("engineering-ready", "0e8a16", "Bounded, authorized fix; eligible for the engineering routine"),
    ("needs-architect", "d93f0b", "Requires Architect decision; never auto-selected"),
    ("needs-founder", "b60205", "Requires Founder authorization; never auto-selected"),
    ("claude-pilot", "ededed", "Routine pilot/test ticket; never auto-selected"),
    ("P0", "b60205", "Highest priority"),
    ("P1", "d93f0b", "High priority"),
    ("P2", "fbca04", "Normal priority"),
)
BACKLOG_END = "2026-11-12"
CURSOR = ROOT / "claude-morning-briefs" / "ENGINEERING_REVIEW_CURSOR.yaml"

TASK_BODY = (
    "## Task\n\nTriage (Claude routine): read the entire source brief, enumerate every "
    "meaningful engineering observation, reconcile each against current code, issues, PRs and "
    "architecture decisions, link recurring symptoms to canonical issues, file issues only for "
    "substantiated new defects, and record a disposition for every observation via "
    "`python tools/morning_brief_agent/run.py ledger-record`. Creating this ticket is **not** a "
    "review. Brief prose is evidence, not authority. No automatic merge or deployment.\n"
)


def index_intake(issues: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_id: dict[str, list[dict[str, Any]]] = {}
    for issue in issues:
        parsed = ledger.parse_intake(issue.get("body"))
        if parsed:
            by_id.setdefault(parsed[0], []).append(issue)
    for group in by_id.values():
        group.sort(key=lambda i: i["number"])
    return by_id


def heal_duplicates(client: GitHubClient, by_id: dict[str, list[dict[str, Any]]]) -> int:
    healed = 0
    for brief_id, group in by_id.items():
        keeper, *dupes = group
        for dupe in dupes:
            if dupe.get("state") == "open":
                client.create_comment(
                    dupe["number"], f"Duplicate intake for `{brief_id}`; canonical is #{keeper['number']}."
                )
                client.set_issue_state(dupe["number"], "closed", "not_planned")
                healed += 1
    return healed


def intake(client: GitHubClient, briefs: list[Brief], batch: int, dry_run: bool = False) -> dict:
    by_id = index_intake(client.list_issues())
    healed = 0 if dry_run else heal_duplicates(client, by_id)
    if not dry_run:
        for name, color, description in CONVENTION_LABELS:
            client.ensure_label(name, color, description)
    created: list[str] = []
    revised: list[str] = []
    for brief in briefs:
        if len(created) + len(revised) >= batch:
            break
        group = by_id.get(brief.brief_id)
        if not group:
            created.append(brief.brief_id)
            if not dry_run:
                body = (
                    f"{ledger.intake_marker(brief)}\n## Source\n\n`{brief.path}`\n\n"
                    f"Brief id: `{brief.brief_id}`  \nContent sha256: `{brief.sha256}`\n\n{TASK_BODY}"
                )
                client.create_issue(TITLE_PREFIX + brief.brief_id, body, [INTAKE_LABEL])
            continue
        issue = group[0]
        comments = client.list_comments(issue["number"])
        if brief.sha256 in ledger.known_shas(issue, comments):
            continue
        revised.append(brief.brief_id)
        if not dry_run:
            client.create_comment(
                issue["number"],
                f"{ledger.revision_marker(brief)}\nBrief `{brief.path}` changed "
                f"(sha256 `{brief.sha256}`); prior review no longer covers it. Re-review required.",
            )
            if issue.get("state") == "closed":
                client.set_issue_state(issue["number"], "open")
    return {"created": created, "revised": revised, "healed_duplicates": healed, "dry_run": dry_run}


def collect_status(client: GitHubClient, briefs: list[Brief]) -> list[ledger.BriefStatus]:
    by_id = index_intake(client.list_issues())
    now = datetime.now(UTC)
    out = []
    for brief in briefs:
        group = by_id.get(brief.brief_id)
        issue = group[0] if group else None
        comments = client.list_comments(issue["number"]) if issue else []
        out.append(ledger.derive_status(brief, issue, comments, now))
    return out


def render_cursor(statuses: list[ledger.BriefStatus], blob_sha: str | None) -> str:
    backlog = [s for s in statuses if s.brief.brief_id <= BACKLOG_END]
    done = {"reviewed", "completed"}
    processed = bool(backlog) and all(s.state in done for s in backlog)
    lines = [
        "---",
        "schema: asa.morning_brief_engineering_cursor.v2",
        "source_root: claude-morning-briefs",
        "purpose: derived_mirror_of_github_review_ledger",
        "canonical_project_status: false",
        "canonical_ledger: GitHub intake issues + asa-brief-ledger:v1 comments",
        "regenerate_with: python tools/morning_brief_agent/run.py sync-cursor",
        "backlog:",
        "  path: claude-morning-briefs/asa_briefs_backlog_2026-10-08_to_2026-11-12.zip",
        f"  blob_sha: {blob_sha or 'null'}",
        f"  processed: {str(processed).lower()}",
        f"  reviewed_count: {sum(1 for s in backlog if s.state in done)}",
        f"  total_count: {len(backlog)}",
        "briefs:",
    ]
    for s in statuses:
        if s.state not in done:
            continue
        lines += [
            f"  '{s.brief.brief_id}':",
            f"    sha256: {s.brief.sha256}",
            f"    state: {s.state}",
            f"    intake_issue: {s.issue}",
            f"    reviewed_at: '{s.reviewed_at}'",
            f"    observations: {len(s.observations)}",
        ]
    if not any(s.state in done for s in statuses):
        lines[-1] = "briefs: {}"
    return "\n".join(lines) + "\n"


def _existing_blob_sha() -> str | None:
    if CURSOR.exists():
        match = re.search(r"blob_sha:\s*([0-9a-f]{40})", CURSOR.read_text())
        return match.group(1) if match else None
    return None


def main(argv: list[str] | None = None, client: GitHubClient | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPO))
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("intake")
    p.add_argument("--batch", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("status")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("ledger-record")
    p.add_argument("--issue", type=int, required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("claim")
    p.add_argument("action", choices=["acquire", "heartbeat", "release", "status"])
    p.add_argument("--issue", type=int, required=True)
    p.add_argument("--owner", default="claude-engineering-routine")
    p.add_argument("--run-id", default=os.environ.get("CLAUDE_SESSION_ID", "manual"))
    p.add_argument("--ttl-minutes", type=int, default=claims.DEFAULT_TTL_MINUTES)
    p.add_argument("--outcome", default="released")
    p.add_argument("--pr", type=int)
    p = sub.add_parser("snapshot")
    p.add_argument("--output", required=True)
    p = sub.add_parser("candidates")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("sync-cursor")
    p.add_argument("--output", default=str(CURSOR))
    args = parser.parse_args(argv)
    if not args.cmd:
        args.cmd, args.batch, args.dry_run = "intake", None, False  # legacy Actions invocation

    client = client or GitHubClient(args.repo)
    briefs = discover()

    if args.cmd == "intake":
        raw = args.batch if args.batch is not None else os.environ.get("BRIEF_BATCH_SIZE", DEFAULT_BATCH)
        try:
            batch = max(1, min(MAX_BATCH, int(raw)))
        except (TypeError, ValueError):
            raise SystemExit("batch size must be an integer") from None
        print(json.dumps(intake(client, briefs, batch, args.dry_run)))
    elif args.cmd == "status":
        rows = [
            {"brief_id": s.brief.brief_id, "state": s.state, "issue": s.issue,
             "needs_revision_notice": s.needs_revision_notice}
            for s in collect_status(client, briefs)
        ]
        print(json.dumps(rows, indent=2) if args.json else "\n".join(
            f"{r['brief_id']}  {r['state']:<10} #{r['issue']}" for r in rows))
    elif args.cmd == "ledger-record":
        rec = json.loads(Path(args.file).read_text())
        brief = next((b for b in briefs if b.brief_id == rec.get("brief_id")), None)
        if brief is None:
            raise SystemExit(f"unknown brief_id {rec.get('brief_id')!r}")
        by_id = index_intake(client.list_issues())
        group = by_id.get(brief.brief_id)
        if not group or group[0]["number"] != args.issue:
            raise SystemExit(f"#{args.issue} is not the canonical intake issue for {brief.brief_id}")
        def exists(n: int) -> bool:
            try:
                return "pull_request" not in client.get_issue(n)
            except Exception:  # noqa: BLE001
                return False
        try:
            ledger.validate_record(rec, brief.sha256, exists)
        except ValueError as exc:
            raise SystemExit(f"INVALID ledger record: {exc}") from None
        if not args.dry_run:
            client.create_comment(args.issue, ledger.render_record(rec))
            if rec["state"] == "reviewed":
                client.set_issue_state(args.issue, "closed", "completed")
        print(f"ledger record ok ({rec['state']}) for {brief.brief_id}")
    elif args.cmd == "claim":
        if args.action == "acquire":
            ok, why = claims.acquire(client, args.issue, args.owner, args.run_id, args.ttl_minutes)
            print(json.dumps({"acquired": ok, "detail": why}))
            return 0 if ok else 3
        if args.action == "heartbeat":
            claims.heartbeat(client, args.issue, args.owner, args.run_id, args.ttl_minutes)
        elif args.action == "release":
            claims.release(client, args.issue, args.owner, args.run_id, args.outcome, args.pr)
        else:
            st = claims.claim_status(client.list_comments(args.issue), datetime.now(UTC))
            print(json.dumps({"state": st.state, "owner": st.owner, "run_id": st.run_id,
                              "prs": claims.owning_prs(client.list_pulls("open"), args.issue)}))
    elif args.cmd == "snapshot":
        rows = [
            {"number": i["number"], "title": i["title"], "state": i["state"],
             "labels": sorted(selection.label_names(i)), "body": (i.get("body") or "")[:3000]}
            for i in client.list_issues()
        ]
        pulls = [{"number": p["number"], "title": p["title"], "body": (p.get("body") or "")[:1500],
                  "head": p["head"]["ref"]} for p in client.list_pulls("open")]
        Path(args.output).write_text(json.dumps({"issues": rows, "open_pulls": pulls}, indent=1))
        print(f"wrote {len(rows)} issues, {len(pulls)} open PRs to {args.output}")
    elif args.cmd == "candidates":
        issues = client.list_issues(state="open")
        now = datetime.now(UTC)
        ready = [i for i in issues if selection.READY in selection.label_names(i)]
        cache = {i["number"]: client.list_comments(i["number"]) for i in ready}
        eligible, skipped = selection.rank_candidates(
            issues, client.list_pulls("open"), lambda n: cache.get(n, []), now)
        print(json.dumps({"eligible": eligible, "skipped": skipped}, indent=2))
    elif args.cmd == "sync-cursor":
        text = render_cursor(collect_status(client, briefs), _existing_blob_sha())
        Path(args.output).write_text(text)
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
