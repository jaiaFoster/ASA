from __future__ import annotations

from tools.morning_brief_agent import claims, selection
from tools.morning_brief_agent import run as run_mod
from tools.morning_brief_agent.ledger import parse_ts

NOW = parse_ts("2026-11-13T17:00:00Z")


def mk(number, title="t", labels=("engineering-ready",), body="", state="open"):
    return {"number": number, "title": title, "labels": [{"name": n} for n in labels],
            "body": body, "state": state}


def rank(issues, pulls=(), comments=None):
    comments = comments or {}
    return selection.rank_candidates(issues, list(pulls), lambda n: comments.get(n, []), NOW)


def test_unlabeled_and_excluded_issues_are_never_selected():
    issues = [mk(1, labels=()), mk(2, labels=("engineering-ready", "needs-architect")),
              mk(3, labels=("engineering-ready", "claude-pilot")), mk(4, state="closed")]
    eligible, skipped = rank(issues)
    assert eligible == [] and {s["issue"] for s in skipped} == {2, 3}


def test_priority_tiers_hold_then_root_defect_then_unlocking_p0():
    issues = [
        mk(10, "plain", labels=("engineering-ready", "P1")),
        mk(11, "HOLD: correction needed", labels=("engineering-ready", "P2")),
        mk(12, "root defect", labels=("engineering-ready", "bug", "P1")),
        mk(13, "unlocker", labels=("engineering-ready", "P0")),
        mk(14, "downstream", labels=("needs-architect",), body="Depends on #13"),
    ]
    eligible, _ = rank(issues)
    assert [c["issue"] for c in eligible] == [11, 13, 12, 10]


def test_open_dependencies_block_but_closed_ones_do_not():
    issues = [mk(1, body="Blocked by #2"), mk(2, labels=("blocked",)), mk(3, body="requires #4"),
              mk(4, state="closed", labels=())]
    eligible, skipped = rank(issues)
    assert [c["issue"] for c in eligible] == [3]
    assert any(s["issue"] == 1 and "dependencies" in s["reason"] for s in skipped)


def test_claimed_or_pr_owned_issues_are_skipped_but_stale_claims_are_not():
    live = {"id": 1, "created_at": "2026-11-13T16:30:00Z", "author_association": "OWNER",
            "body": claims.render_claim("claim", "A", "r", 240)}
    stale = {"id": 2, "created_at": "2026-11-13T01:00:00Z", "author_association": "OWNER",
             "body": claims.render_claim("claim", "A", "r", 60)}
    issues = [mk(1), mk(2), mk(3)]
    pulls = [{"number": 9, "title": "x", "body": "Closes #3", "head": {"ref": "b"}}]
    eligible, skipped = rank(issues, pulls, {1: [live], 2: [stale]})
    assert [c["issue"] for c in eligible] == [2]
    assert {s["issue"] for s in skipped} == {1, 3}


def test_candidates_cli_lists_only_ready(gh, capsys, monkeypatch):
    gh.seed_issue(1, "ready", "")
    gh.issues[1]["labels"] = ["engineering-ready"]
    gh.seed_issue(2, "not ready", "")
    run_mod.main(["candidates"], client=gh)
    import json
    out = json.loads(capsys.readouterr().out)
    assert [c["issue"] for c in out["eligible"]] == [1]


def test_snapshot_writes_all_issues_and_open_prs(gh, tmp_path, capsys):
    gh.seed_issue(1, "a", "body one", state="closed")
    gh.seed_issue(2, "b", "body two")
    gh.pulls = [{"number": 9, "title": "p", "body": "b", "head": {"ref": "x"}}]
    out = tmp_path / "snap.json"
    run_mod.main(["snapshot", "--output", str(out)], client=gh)
    import json
    data = json.loads(out.read_text())
    assert [i["number"] for i in data["issues"]] == [1, 2] and data["open_pulls"][0]["head"] == "x"
