# STRATEGY-PRODUCTION-001 — worker hand-off (SP-08A post-deployment proof)

Written 2026-10-03 by the outgoing implementation worker. The incoming worker
has Railway API access and finishes SP-08A, then closes the sprint if every
closure condition holds. Do not restart the sprint or redo merged tickets.

## 1. Rehydrate (authority order)

1. `governance/frozen/` (RISK-001, RES-001, RES-002)
2. Amendment 013 / Founder Sprint Delegation (active for this sprint)
3. `roles/shared/AUTHORITY_BOUNDARIES.md`, `RISK_SCALED_PROCESS.md`, `GITHUB_ACCEPTANCE_MODEL.md`
4. `docs/sprints/STRATEGY-PRODUCTION-001.yaml`, especially:
   - `tickets.SP-08A`
   - `closure`
   - `blocker_policy`
   - `completion` (`delegation_expires_on_completion: true`)
5. `project/reports/STRATEGY-PRODUCTION-001-SP-08A.md` (deployment packet, post-deploy observations 1–2)
6. This file, then current `main` and merged PRs #528–#535

## 2. Current state (verified 2026-10-03)

| Item | State |
|---|---|
| Child tickets | All merged: SP-00A…SP-07B, SP-08A tool #532, plus corrective PRs #533 and #534 |
| `main` | `1937de2a9f87110db946bffeae1a382197c2a20d` (the #535 capture commit; its runtime code is identical to `2dfaa2d`) |
| Production web `/api/v1/version` | `release_sha` = `1937de2a9f87110db946bffeae1a382197c2a20d` |
| Health / capabilities | `/api/v1/health` ok; `/api/v1/capabilities` lists all seven |
| Full suite at `main` | 4065 passed, 50 skipped, 1 failure: `test_finnhub_passes_shared_supported_capability_suite`, pre-existing and also failing on the previously deployed `1efac18` |
| Architecture validation / CI | Green on every merged PR |
| Replay / convergence | `tests/asa/test_seven_strategy_production_integration.py` is green (16 tests) |
| Capacity gate | `project/reports/STRATEGY-PRODUCTION-001-SP-07B.md` is green: the 120-pair cohort tick has 0 deferrals, and complete families defer atomically |
| Real-session proof | **Not yet satisfied**; see §3 |

### Post-deploy defects already found and fixed (do not redo)

1. **#533:** BXM (35-day) and SCS (7-day) `INDEX_SETTLEMENT_VALUE_V1` lookbacks collided on SPX. No reducer was registered, so the whole SPX subject persisted `subject_preparation_failed`.
2. **#534:**
   - Once SPX preparation succeeded, PUT, PUTY, BXM and SCS returned not-due `NO_SIGNAL` without `opportunity_id`/`lifecycle_stage`, violating `OutputKind.LIFECYCLE`. Each pair raised and **wrote no row**.
   - The same PR made SCS's rate demands optional.

### Why the proof is still open

- The SPX rows in production are still the stale 18:23 UTC failure rows from 2026-10-02 (release `392948d`).
- No scheduled tick has run on `1937de2`/`2dfaa2d` during a session yet. The cron last ran Friday 21:53 UTC; the weekend has no ticks.
- The first eligible session is **Monday 2026-10-05**.

## 3. Remaining work

### A. Verify deployment and configuration (Railway, read-only)

- **Deployed commit.** Both the web and cron services must be on `1937de2…`, or on the runtime-identical `2dfaa2d…`.
- **Cron config.** The cron service must use config-as-code `/railway.cron.json` with `cronSchedule = "*/10 13-21 * * 1-5"` (UTC), as `main` declares. Do not override it in Railway unless evidence shows it is wrong.
- **Treasury flag.** `ASA_US_TREASURY_ENABLED=true` must be set on both services.
- **Do not deploy, redeploy, restart or change variables.** Production deployment is Founder-only. If a change is needed, prepare the exact action for the Founder.

### B. Collect cron evidence for one complete session (Monday 2026-10-05 or later)

1. Pull the cron service logs for every tick of the session: 13:00–21:50 UTC on that New York date.
2. Each tick prints one JSON line with `"artifact_type": "bounded_run_cohort"`. It lists every pair's `signal_id`, `symbol`, `outcome`, `error` and `reason`.
3. Also look for warning lines whose event name ends in `_refresh_failed`, plus any `Traceback`.
4. Save only those lines, sanitized, to a scratch file such as `cron.log`. Never commit raw logs or anything containing tokens.

Confirm, across all ticks:
- no selected-strategy result has a non-null `error`;
- no `fixed_subject_option_refresh_failed` or `complete_family_refresh_failed` warning appears;
- the SPX pairs for PUT, PUTY, BXM and SCS appear with `outcome` set and `error: null`.

### C. Run the classifier on the session

Run it from a checkout at the deployed SHA.

```
python -m tools.strategy_production.release_classification \
  --base-url https://asa-production-b2c4.up.railway.app \
  --production-sha <deployed sha> \
  --window-start 2026-10-05T13:30:00+00:00 \
  --window-end   2026-10-05T21:55:00+00:00 \
  --cron-output  <sanitized cron.log> \
  --output project/reports/STRATEGY-PRODUCTION-001-SP-08A-session.json
```

- The token is read from `ASA_AGENT_API_TOKEN`. Never print or commit it.
- `verdict: pass` requires:
  - all seven classified `LIVE_EVALUABLE`, `LIVE_TYPED_DATA_BLOCKER` or `NOT_DUE`;
  - no ASA-defect codes in the latest rows;
  - clean cron evidence;
  - deployed SHA equal to `--production-sha`.

Expected classes on 2026-10-05:

| Strategy | Expected class | Why |
|---|---|---|
| PUT, PUTY, BXM, SCS | `NOT_DUE` | Not a roll or entry day; typed `NO_ACTION` rows are fine |
| GXZ | `LIVE_TYPED_DATA_BLOCKER` or `NOT_DUE` | Event strategy |
| Zhan, Heston | `NOT_DUE` | Not a formation day; the classifier checks the registered due callbacks |

Zhan and Heston are only due on a month-end or monthly-expiration date. On those dates the expected class is `LIVE_TYPED_DATA_BLOCKER`, with `CAPACITY_DEFERRED_INCOMPLETE_COHORT` (503 members against a ceiling of 30). This is valid and is not a failure. Do not raise the 30-subject ceiling; that is a separate capacity decision.

### D. If the proof fails

- Find the earliest boundary that owns the failure and fix it in scope.
- Add a production-shaped regression that fails without the fix. `tests/asa/_fixture_index_tradier.py` drives the real fixed-subject root with Tradier-shaped SPX data; pin time as in `test_fixed_spx_root_persists_a_row_for_every_index_strategy`.
- Get a fresh exact-head ROLE-ARCH review from a reviewer you start yourself, then merge under delegation.
- Ask the Founder for a redeploy only when one is needed.
- Routine defects, typed blockers, reviews, CI and observation waits are not Founder blockers.

### E. If the proof passes: close the sprint

1. Commit the session artifact and an "Observation 3 / closure" section in `STRATEGY-PRODUCTION-001-SP-08A.md`. Record the session, SHA, per-strategy classes, cron-evidence summary and each closure item with its evidence.
2. Update canonical state per repo conventions:
   - `project/lean/state/project-state.yaml` (sprint complete);
   - regenerate `CURRENT_STATE.md` with `tools/pos/lean/generate.py`;
   - run `tools/pos/lean/check_integrity.py` and `pre_push_check.py`.
3. Open one bounded closure PR naming SP-08A. Get a fresh review, wait for green CI, merge.
4. State explicitly that the Founder Sprint Delegation for STRATEGY-PRODUCTION-001 expires on completion.

## 4. Process rules carried forward

- **Branch.** Push only to the designated branch the session gives you. If its PR is merged, restart the branch from `main`. Never force-push someone else's branch.
- **Merge method.** Squash; merge commits are disabled on this repo. Always pass the full 40-character `expectedHeadSha`.
- **Reviews.** Reviewers are fresh, read-only agents. A new SHA invalidates prior approvals.
- **Commits and PRs.**
  - No model identifiers in commits or PRs.
  - Commit trailer: `Co-Authored-By` plus the `Claude-Session` link for your session.
  - GitHub comments end with the Claude Code footer.
- **Daily capture.** A routine, "ASA daily program session capture", runs post-close each session day. It writes `project/observations/ASA-OPTIONS-TO-OUTCOMES-2026Q4/<date>.json` and regenerates the OI-07 and closure reports. These are R1 PRs. The program verdict is currently `observation_pending`.

## 5. Known non-blocking follow-ups (not required for closure)

- The scheduler's cycle clock ignores `now=` (`asa/scheduled_screening.py`); injecting it would replace test monkeypatching.
- Hours 21:00–21:50 UTC also re-run the fixed-subject and benchmark refreshes after the close; gating them to session slots is a follow-up.
- A missed formation is not typed. The complete-family claim is taken before rows persist, so a write failure is not retried that day.
- The cron-evidence check needs only one artifact; requiring the full tick count for the window, and flagging `Traceback` lines, would harden it.
- BXM labels a held call `identified` (pre-existing). SCS returns `MISSING_DATA` on non-session days (cosmetic).
- The API on-demand route still acquires data for Zhan/Heston pairs before failing.
- The `tests/market_data/test_index_settlement_reducer.py` annotations are not mypy-clean (not gated).
- Zhan and Heston remain capacity-deferred until a measured ceiling increase; Heston also lacks 12 months of A08 history.
