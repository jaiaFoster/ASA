# Routine B — Engineering Worker (daily 10:00 America/Phoenix)

Follow `COMMON.md` first. One implementation issue per run. Never merge or deploy.

## Eligibility (enforced by `run.py candidates`)

Open issue labelled `engineering-ready`; not `needs-architect|needs-founder|blocked|claude-pilot`;
no open dependency (`Depends on #N` / `Blocked by #N` / `Requires #N`); no live claim; no open PR
referencing it. Ranking: HOLD/correction items → root defects (`bug`) and P0 issues that unlock
others → everything else; then `P0<P1<P2`, more unlocks, oldest. Only issues that a human or the
triage routine (within the assignment’s “local bounded fix” rule) labelled `engineering-ready`
are authorized. **Removing the label vetoes the work.**

## Procedure

1. `python tools/morning_brief_agent/run.py candidates` → take the first `eligible` issue.
   None → post “no eligible issue” and stop.
2. Claim durably:
   `run.py claim acquire --issue N --owner claude-engineering-routine --run-id <session id> --ttl-minutes 240`.
   Exit code 3 = held, PR-owned, or lost race → move to the next candidate (max 3 tries).
   A claim older than its TTL with no heartbeat is **stale** and is recovered automatically
   (check `git ls-remote origin 'claude/issue-N-*'` first and continue from that branch if present).
3. Read the issue, its source brief(s) (`<!-- asa-source-brief -->`), the canonical owner code, and
   linked issues/PRs. Re-verify the defect on current `main` before changing anything. If it no
   longer reproduces, comment evidence, release with outcome `not_reproducible`, stop.
4. Environment: `source tools/morning_brief_agent/routine_env.sh`.
5. Branch `claude/issue-N-<slug>` from `main`. Implement the smallest root-cause fix at the
   earliest canonical owner. Add a production-shaped regression test (brief evidence where feasible).
   Heartbeat every ~45 min: `run.py claim heartbeat --issue N --run-id …`.
6. Run: `ruff check asa tests/asa`, `mypy asa` (if installed), the relevant tests, and
   `pytest tests/asa -q` when `ASA_PG_AVAILABLE=1`. Record exactly what ran, passed, or could not run.
7. Review `git diff main...` for unintended changes. Stay within the issue’s scope.
8. Push the branch and open a PR via REST (`gh api -X POST repos/jaiaFoster/ASA/pulls`), body:
   root cause, fix, tests run + results (verbatim counts), limitations, `Closes #N`, source-brief
   traceability. Do not enable auto-merge.
9. Comment progress on the issue. Release the claim:
   `run.py claim release --issue N --run-id … --outcome pr_opened --pr <PR#>`
   (or `blocked` / `abandoned` / `not_reproducible` with a comment explaining why).
10. Post the run summary (COMMON.md).

## Escalate, do not implement

New architecture, schema/API changes needing approval, new product capability, unclear ownership,
governance, production trading/broker changes, anything requiring new Founder authorization:
label `needs-architect` / `needs-founder`, comment the exact question, release `blocked`, and
pick the next candidate (still max one implementation per run).

## Failure and recovery

- Failing test you cannot fix in scope → no PR with red tests presented as green; open the PR only
  if it is honest (state failures) or release `blocked` with findings on the issue.
- Session dies mid-work → claim expires (TTL ≤ 12 h); the next run recovers it and resumes from the
  pushed branch. An open PR referencing the issue blocks duplicate PRs.
- Never delete another worker’s branch/PR.
