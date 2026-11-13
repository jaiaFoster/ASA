from __future__ import annotations

import json

import pytest

from tools.morning_brief_agent import ledger
from tools.morning_brief_agent.briefs import discover
from tools.morning_brief_agent.run import heal_duplicates, index_intake, intake, render_cursor
from tools.morning_brief_agent import run as run_mod


def test_discover_uses_stable_ids_and_ignores_non_briefs(brief_root):
    briefs = discover(brief_root)
    assert [b.brief_id for b in briefs] == ["2026-10-08", "2026-10-09", "2026-10-12", "2026-10-13"]
    assert briefs[0].path == "claude-morning-briefs/2026-10-08.md"
    assert len(briefs[0].sha256) == 64


def test_discover_scans_legacy_producer_root_canonical_wins(brief_root):
    legacy = brief_root / "briefs"
    legacy.mkdir()
    (legacy / "2026-11-13.md").write_text("new from producer")
    (legacy / "2026-10-08.md").write_text("DIFFERENT")
    by_id = {b.brief_id: b for b in discover(brief_root)}
    assert by_id["2026-11-13"].path == "briefs/2026-11-13.md"
    assert by_id["2026-10-08"].path == "claude-morning-briefs/2026-10-08.md"


def test_suffix_ids_supported(brief_root):
    (brief_root / "claude-morning-briefs" / "2026-10-14-postopen.md").write_text("x")
    assert "2026-10-14-postopen" in [b.brief_id for b in discover(brief_root)]


def test_intake_respects_batch_and_is_idempotent(gh, brief_root):
    briefs = discover(brief_root)
    first = intake(gh, briefs, 3)
    assert first["created"] == ["2026-10-08", "2026-10-09", "2026-10-12"]
    again = intake(gh, briefs, 3)
    assert again["created"] == ["2026-10-13"] and again["revised"] == []
    third = intake(gh, briefs, 3)
    assert third == {"created": [], "revised": [], "healed_duplicates": 0, "dry_run": False}
    assert len(gh.issues) == 4


def test_intake_dry_run_writes_nothing(gh, brief_root):
    result = intake(gh, discover(brief_root), 3, dry_run=True)
    assert result["created"] and not gh.issues


def test_legacy_v1_markers_are_recognized_not_duplicated(gh, brief_root):
    brief = discover(brief_root)[0]
    gh.seed_issue(603, "BRIEF INTAKE: engineering review 2026-10-08",
                  f"<!-- asa-brief-intake:2026-10-08.md sha256:{brief.sha256} -->\n## Source")
    result = intake(gh, discover(brief_root), 10)
    assert "2026-10-08" not in result["created"]
    assert len(index_intake(gh.list_issues())["2026-10-08"]) == 1


def test_modified_brief_creates_one_revision_notice_and_reopens(gh, brief_root):
    intake(gh, discover(brief_root), 10)
    gh.set_issue_state(1, "closed")
    (brief_root / "claude-morning-briefs" / "2026-10-08.md").write_text("brief one, EDITED")
    briefs = discover(brief_root)
    out = intake(gh, briefs, 10)
    assert out["revised"] == ["2026-10-08"]
    assert gh.issues[1]["state"] == "open"
    assert intake(gh, briefs, 10)["revised"] == []  # idempotent
    assert sum("asa-brief-revision" in c["body"] for c in gh.comments[1]) == 1


def test_duplicate_intake_issues_are_healed_keeping_lowest(gh, brief_root):
    brief = discover(brief_root)[0]
    for number in (10, 11):
        gh.seed_issue(number, "dup", ledger.intake_marker(brief))
    assert heal_duplicates(gh, index_intake(gh.list_issues())) == 1
    assert gh.issues[10]["state"] == "open" and gh.issues[11]["state"] == "closed"


def test_cursor_mirror_only_lists_reviewed_briefs(gh, brief_root):
    briefs = discover(brief_root)
    intake(gh, briefs, 10)
    rec = {"schema": ledger.SCHEMA, "brief_id": "2026-10-08", "sha256": briefs[0].sha256,
           "state": "reviewed", "run_id": "r1", "full_brief_read": True,
           "observations": [{"id": "O1", "summary": "s", "disposition": "EXPECTED_BEHAVIOR",
                             "evidence": "e"}]}
    gh.create_comment(1, ledger.render_record(rec))
    text = render_cursor(run_mod.collect_status(gh, briefs), "a" * 40)
    assert "'2026-10-08':" in text and "'2026-10-09':" not in text
    assert "processed: false" in text and "reviewed_count: 1" in text
    assert "blob_sha: " + "a" * 40 in text


def test_cli_status_and_cursor_end_to_end(gh, brief_root, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(run_mod, "discover", lambda: discover(brief_root))
    assert run_mod.main(["intake", "--batch", "2"], client=gh) == 0
    assert json.loads(capsys.readouterr().out)["created"] == ["2026-10-08", "2026-10-09"]
    run_mod.main(["status", "--json"], client=gh)
    states = {r["brief_id"]: r["state"] for r in json.loads(capsys.readouterr().out)}
    assert states["2026-10-08"] == "queued" and states["2026-10-13"] == "discovered"
    out = tmp_path / "cursor.yaml"
    run_mod.main(["sync-cursor", "--output", str(out)], client=gh)
    assert "briefs: {}" in out.read_text()


def test_batch_size_must_be_integer(gh, monkeypatch, brief_root):
    monkeypatch.setattr(run_mod, "discover", lambda: discover(brief_root))
    with pytest.raises(SystemExit):
        run_mod.main(["intake", "--batch", "abc"], client=gh)
