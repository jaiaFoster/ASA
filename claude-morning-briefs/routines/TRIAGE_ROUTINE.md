# Routine A — Morning Brief Triage (daily 09:00 America/Phoenix)

Follow `COMMON.md` first. Goal: turn queued briefs into **fully reconciled** dispositions.
Creating an intake ticket is not a review; a brief is reviewed only when every meaningful
observation has a durable disposition recorded through the validating CLI.

Batch: at most **3 briefs per run** (oldest first). Process fewer rather than shortcut.

## Procedure

1. `python tools/morning_brief_agent/run.py status --json` — states are derived from GitHub:
   `discovered → queued → reviewing → reviewed → completed`.
   - Pick up to 3 `queued` briefs, oldest first. (A `reviewing` record older than 12 h is a
     crashed run and already shows as `queued`.)
   - If nothing is `queued` but some are `discovered` (the 08:00 Actions intake failed), run
     `run.py intake --batch 3` (idempotent; self-heals duplicate intake issues), then re-check.
   - If a brief is `queued` with `needs_revision_notice: true`, run `run.py intake` first.
2. Snapshot current work for local search:
   `python tools/morning_brief_agent/run.py snapshot --output $TMPDIR/issues.json`.
3. For each selected brief:
   a. Claim it: post a `reviewing` record (see schema below) with
      `run.py ledger-record --issue <intake#> --file rec.json`.
   b. **Read the entire brief** (`brief.path`). Do not skim; briefs are ~15 KB.
   c. Enumerate every meaningful engineering observation (O1, O2, …): contradictions,
      regressions, repeated blockers, missing explanations, data-quality flags, liveness issues.
   d. Reconcile each against: current code on `main`, the issue snapshot (open **and** closed),
      open PRs, `ENGINEERING_CASE_INDEX.md`, and architecture/governance docs. Follow Steps A–D of
      `project/workers/MORNING-BRIEF-ENGINEER-v1.md` §5. Brief prose is evidence, not authority.
   e. Disposition each observation (exactly one):
      `EXISTING_ISSUE` (link `#N`; comment new evidence once, with an
      `<!-- asa-evidence: <brief_id> -->` marker so reruns don't repeat),
      `NEW_ISSUE` (only for substantiated `CONFIRMED_DEFECT`/`CONFIRMED_PRODUCT_GAP`; search the
      fresh snapshot *and* re-query immediately before creating to avoid duplicates),
      `EXPECTED_BEHAVIOR`, `STALE_BRIEF_INTERPRETATION`, `INSUFFICIENT_EVIDENCE`,
      `ARCHITECTURE_ROUTED` (issue labelled `needs-architect`).
   f. New issue body must include: `<!-- asa-source-brief: <brief_id> -->`, the user-visible
      symptom, evidence (file/line, query, brief date), canonical owner, acceptance criteria.
      Labels: add `engineering-ready` **only** when every “local bounded fix” criterion in
      assignment §5 Step D holds (clear owner, existing contract violated, no semantic/threshold/
      schema/authority change). Otherwise `needs-architect` or `needs-founder`. Add `P0/P1/P2`
      and `bug` where justified. Create via `gh api -X POST repos/jaiaFoster/ASA/issues --input f.json`.
   g. Record completion: `run.py ledger-record --issue <intake#> --file rec.json` with
      `"state": "reviewed"`. The CLI **rejects** records that are incomplete, hash-stale, or cite
      nonexistent issues, and on success closes the intake ticket. Never bypass it.
4. Mirror: `run.py sync-cursor`, update `ENGINEERING_CASE_INDEX.md` rows whose evidence changed,
   commit both on branch `claude/brief-triage-cursor` (reset to `main` each run), push, and
   open-or-update the single PR for that branch. Do not merge it.
5. Post the run summary (COMMON.md). Include: briefs completed, issues created/linked, blockers.

## Ledger record schema (`asa.brief_ledger.v1`)

```json
{"schema":"asa.brief_ledger.v1","brief_id":"2026-10-08","sha256":"<current content sha256>",
 "state":"reviewed","run_id":"<session id>","full_brief_read":true,
 "observations":[{"id":"O1","summary":"…","disposition":"EXISTING_ISSUE","issue":540,
                  "evidence":"asa/…:123 shows …; brief says …"}]}
```
`sha256` must equal `status`'s current hash (use the one in `run.py status --json` output or
`sha256sum`). Use `"state":"reviewing"` (no observations needed) to claim.

## Failure and recovery

- Crash/interruption: the `reviewing` record goes stale after 12 h and the brief re-queues.
  Re-processing is safe: a later `reviewed` record supersedes earlier ones; evidence comments
  and issue creation are deduplicated by marker/search.
- A brief you cannot finish: leave it at `reviewing` (do **not** post `reviewed`), continue with
  the next brief, and report the blocker.
- Brief edited after review: its hash changes → `queued` again; re-review the whole brief.
- Do not run two triage sessions concurrently (manual double-fire): duplicate-issue risk is
  mitigated only by the pre-create search.
