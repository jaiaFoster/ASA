from __future__ import annotations

import copy
import json
from datetime import timedelta

import pytest

from tools.morning_brief_agent import claims, ledger
from tools.morning_brief_agent import run as run_mod
from tools.morning_brief_agent.briefs import Brief, discover
from tools.morning_brief_agent.github_api import GitHubClient, GitHubError

BRIEF = Brief("2026-10-08", "claude-morning-briefs/2026-10-08.md", "b" * 64)


def record(**over):
    rec = {
        "schema": ledger.SCHEMA, "brief_id": BRIEF.brief_id, "sha256": BRIEF.sha256,
        "state": "reviewed", "run_id": "run-1", "full_brief_read": True,
        "observations": [
            {"id": "O1", "summary": "x", "disposition": "EXISTING_ISSUE", "issue": 540,
             "evidence": "code path verified"},
            {"id": "O2", "summary": "y", "disposition": "EXPECTED_BEHAVIOR", "evidence": "contract"},
        ],
    }
    rec.update(over)
    return rec


# ---- ledger validation ------------------------------------------------------
def test_valid_reviewed_record_passes():
    ledger.validate_record(record(), BRIEF.sha256, lambda n: True)


@pytest.mark.parametrize("mutate,msg", [
    (lambda r: r.update(sha256="c" * 64), "does not match"),
    (lambda r: r.update(full_brief_read=False), "full_brief_read"),
    (lambda r: r.update(observations=[]), "at least one"),
    (lambda r: r["observations"][0].update(disposition="DONE"), "invalid disposition"),
    (lambda r: r["observations"][0].pop("issue"), "integer issue"),
    (lambda r: r["observations"][1].update(evidence=" "), "evidence"),
    (lambda r: r["observations"][1].update(id="O1"), "duplicated"),
    (lambda r: r.update(schema="other"), "schema"),
])
def test_incomplete_records_are_rejected(mutate, msg):
    rec = copy.deepcopy(record())
    mutate(rec)
    with pytest.raises(ValueError, match=msg):
        ledger.validate_record(rec, BRIEF.sha256, lambda n: True)


def test_referenced_issue_must_exist():
    with pytest.raises(ValueError, match="not found"):
        ledger.validate_record(record(), BRIEF.sha256, lambda n: False)


def test_reviewing_record_needs_no_observations():
    ledger.validate_record(record(state="reviewing", observations=[]), BRIEF.sha256)


# ---- state derivation / crash recovery -------------------------------------
def issue(state="open"):
    return {"number": 5, "state": state, "body": ledger.intake_marker(BRIEF)}


def comment(cid, rec, assoc="OWNER", at="2026-11-13T15:00:00Z"):
    return {"id": cid, "body": ledger.render_record(rec), "created_at": at, "author_association": assoc}


NOW = ledger.parse_ts("2026-11-13T16:00:00Z")


def test_states_discovered_queued_reviewing_reviewed_completed():
    assert ledger.derive_status(BRIEF, None, [], NOW).state == "discovered"
    assert ledger.derive_status(BRIEF, issue(), [], NOW).state == "queued"
    reviewing = comment(1, record(state="reviewing"))
    assert ledger.derive_status(BRIEF, issue(), [reviewing], NOW).state == "reviewing"
    reviewed = comment(2, record())
    assert ledger.derive_status(BRIEF, issue(), [reviewing, reviewed], NOW).state == "reviewed"
    assert ledger.derive_status(BRIEF, issue("closed"), [reviewed], NOW).state == "completed"


def test_stale_reviewing_record_is_crash_recovered_to_queued():
    stale = comment(1, record(state="reviewing"), at="2026-11-13T01:00:00Z")
    assert ledger.derive_status(BRIEF, issue(), [stale], NOW).state == "queued"


def test_review_of_old_revision_does_not_count():
    old = comment(1, record(sha256="d" * 64))
    status = ledger.derive_status(BRIEF, issue("closed"), [old], NOW)
    assert status.state == "queued"


def test_untrusted_commenter_cannot_forge_review():
    forged = comment(1, record(), assoc="NONE")
    assert ledger.derive_status(BRIEF, issue(), [forged], NOW).state == "queued"


def test_unseen_content_hash_flags_revision_notice():
    changed = {"number": 5, "state": "open", "body": ledger.intake_marker(Brief("2026-10-08", "p", "e" * 64))}
    assert ledger.derive_status(BRIEF, changed, [], NOW).needs_revision_notice


def test_ledger_record_cli_posts_validates_and_closes(gh, brief_root, monkeypatch, tmp_path):
    monkeypatch.setattr(run_mod, "discover", lambda: discover(brief_root))
    run_mod.main(["intake", "--batch", "1"], client=gh)
    brief = discover(brief_root)[0]
    gh.seed_issue(540, "canonical", "body")
    rec = record(brief_id=brief.brief_id, sha256=brief.sha256)
    path = tmp_path / "rec.json"
    path.write_text(json.dumps(rec))
    run_mod.main(["ledger-record", "--issue", "1", "--file", str(path)], client=gh)
    assert gh.issues[1]["state"] == "closed"
    bad = dict(rec, observations=[])
    path.write_text(json.dumps(bad))
    with pytest.raises(SystemExit, match="INVALID"):
        run_mod.main(["ledger-record", "--issue", "1", "--file", str(path)], client=gh)
    with pytest.raises(SystemExit, match="not the canonical"):
        run_mod.main(["ledger-record", "--issue", "999", "--file", str(path)], client=gh)


# ---- claims ----------------------------------------------------------------
def test_first_claim_wins_and_second_is_rejected(gh):
    gh.seed_issue(7, "eng", "body")
    assert claims.acquire(gh, 7, "A", "r1", now=gh.clock)[0] is True
    ok, why = claims.acquire(gh, 7, "B", "r2", now=gh.clock)
    assert not ok and "held by A" in why


def test_stale_claim_is_recovered_after_ttl(gh):
    gh.seed_issue(7, "eng", "body")
    claims.acquire(gh, 7, "A", "r1", ttl=60, now=gh.clock)
    gh.advance(minutes=61)
    assert claims.claim_status(gh.list_comments(7), gh.clock).state == "stale"
    ok, why = claims.acquire(gh, 7, "B", "r2", now=gh.clock)
    assert ok and "recovered" in why


def test_heartbeat_extends_and_release_frees(gh):
    gh.seed_issue(7, "eng", "body")
    claims.acquire(gh, 7, "A", "r1", ttl=60, now=gh.clock)
    gh.advance(minutes=50)
    claims.heartbeat(gh, 7, "A", "r1", 60)
    gh.advance(minutes=50)
    assert claims.claim_status(gh.list_comments(7), gh.clock).state == "held"
    claims.release(gh, 7, "A", "r1", "pr_opened", pr=99)
    assert claims.claim_status(gh.list_comments(7), gh.clock).state == "free"


def test_release_by_non_holder_is_ignored(gh):
    gh.seed_issue(7, "eng", "body")
    claims.acquire(gh, 7, "A", "r1", now=gh.clock)
    claims.release(gh, 7, "B", "r2", "abandoned")
    assert claims.claim_status(gh.list_comments(7), gh.clock).owner == "A"


def test_race_loser_cleans_up_its_claim(gh):
    gh.seed_issue(7, "eng", "body")
    original = gh.list_comments
    calls = {"n": 0}

    def racing(number):  # a competitor's claim lands between B's check and B's post
        calls["n"] += 1
        if calls["n"] == 2:
            gh.comments[7].insert(0, {"id": 0, "created_at": gh._iso(), "author_association": "OWNER",
                                      "body": claims.render_claim("claim", "A", "r1", 60)})
        return original(number)

    gh.list_comments = racing
    ok, why = claims.acquire(gh, 7, "B", "r2", now=gh.clock)
    assert not ok and "lost race" in why
    assert all("\"owner\": \"B\"" not in c["body"] for c in gh.comments[7])


def test_untrusted_claim_comment_is_ignored(gh):
    gh.seed_issue(7, "eng", "body")
    gh.create_comment(7, claims.render_claim("claim", "mallory", "x", 600), assoc="NONE")
    assert claims.acquire(gh, 7, "A", "r1", now=gh.clock)[0]


def test_existing_pr_blocks_claim_and_ttl_is_capped(gh):
    gh.seed_issue(7, "eng", "body")
    gh.pulls = [{"number": 50, "title": "Fix thing", "body": "Closes #7", "head": {"ref": "x"}}]
    ok, why = claims.acquire(gh, 7, "A", "r1", now=gh.clock)
    assert not ok and "[50]" in why
    gh.pulls = []
    claims.acquire(gh, 7, "A", "r1", ttl=10_000, now=gh.clock)
    gh.advance(minutes=claims.MAX_TTL_MINUTES + 1)
    assert claims.claim_status(gh.list_comments(7), gh.clock).state == "stale"


def test_owning_prs_matches_number_boundaries_and_branch():
    pulls = [
        {"number": 1, "title": "", "body": "see #70", "head": {"ref": "a"}},
        {"number": 2, "title": "", "body": "", "head": {"ref": "claude/issue-7-fix"}},
        {"number": 3, "title": "t", "body": "Fixes #7.", "head": {"ref": "b"}},
    ]
    assert claims.owning_prs(pulls, 7) == [2, 3]


# ---- REST client -----------------------------------------------------------
def test_client_paginates_and_never_uses_graphql():
    pages = {1: [{"number": i} for i in range(100)], 2: [{"number": 100}, {"number": 101, "pull_request": {}}]}
    seen = []

    def runner(args, stdin):
        seen.append(args)
        page = int(args[3].rsplit("&page=", 1)[1])
        return json.dumps(pages[page])

    issues = GitHubClient("o/r", runner).list_issues()
    assert len(issues) == 101  # the PR row is excluded
    assert len(seen) == 2 and all("graphql" not in " ".join(a) and a[0] == "api" for a in seen)


def test_client_retries_transient_errors_then_raises():
    attempts = {"n": 0}
    sleeps: list[float] = []

    def flaky(args, stdin):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise GitHubError("Session policy is temporarily unavailable (HTTP 503)")
        return "[]"

    client = GitHubClient("o/r", flaky, sleep=sleeps.append)
    assert client.list_pulls() == [] and attempts["n"] == 3 and sleeps == [1, 2]

    def hard(args, stdin):
        raise GitHubError("HTTP 404 Not Found")

    with pytest.raises(GitHubError):
        GitHubClient("o/r", hard, sleep=sleeps.append).get_issue(1)


def test_ensure_label_tolerates_existing_but_not_other_errors():
    def exists(args, stdin):
        raise GitHubError("HTTP 422 already_exists")

    GitHubClient("o/r", exists).ensure_label("x", "fff", "d")

    def denied(args, stdin):
        raise GitHubError("HTTP 403 forbidden")

    with pytest.raises(GitHubError):
        GitHubClient("o/r", denied).ensure_label("x", "fff", "d")
