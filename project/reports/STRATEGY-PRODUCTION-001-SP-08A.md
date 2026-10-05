# STRATEGY-PRODUCTION-001 — SP-08A Founder deployment packet

- Ticket: `SP-08A` (Founder-only action: production deployment)
- Release: exact `main` at the merge commit of this SP-08A PR (`RELEASE_SHA`, reported on the PR and in the Founder handoff). SP-08A adds only a read-only tool and this packet; runtime content is identical to `e987af9` (SP-07B).
- Currently deployed: `1efac180b66d2c521b22058e10cc74c2939a29f2` (SP-06B, #522)
- Database migrations between deployed and release: none

## Contents since the deployed release

| PR | Ticket | Production effect |
|---|---|---|
| #524 | SP-04B | Santa-Clara/Saretto short SPX straddle (SCS) registered and scheduled on the fixed-SPX path |
| #527 | SP-05C | Zhan cross-sectional strategy registered, cataloged, cut over |
| #528 | SP-05D | Heston straddle-momentum strategy registered, cataloged, cut over |
| #529 | SP-07A | Seven-strategy convergence: GXZ on the production claim path; complete-family (Zhan/Heston) atomic scheduling with persisted typed deferral; SCS cut over; cron covers after-close formation ticks |
| #531 | OI-07 | Session capture and regenerated reports (documentation only) |
| #530 | SP-07B | Cycle and complete-family capacity summaries; measured release gate |
| this PR | SP-08A | Read-only release classification tool and this packet |

## Pre-deployment evidence (worker-verified)

- Every ticket merged under delegation, with an exact-head review and CI green.
- Full suite at release: 4049 passed / 50 skipped. The only failure is the pre-existing
  Finnhub provider-compliance test, which also fails on the deployed SHA.
- Architecture validation is green. No strategy-ID branch exists in generic
  runtime, acquisition, API or UI code.
- Capacity gate (SP-07B): the 30-subject claimed-cohort tick (120 pairs)
  completes 120/120 with 270 provider requests and zero deferrals. The complete
  families defer atomically: 503 typed rows, zero provider requests, zero
  partial rankings.
- Replay: the seven-strategy matrix and composition-root replay pass.

## Expected production registry after deploy

All seven are visible in `/api/v1/capabilities`:

- `event_vol_gxz_preea_straddle_to_expiry`
- `index_putwrite_cboe_put`
- `index_putwrite_cboe_puty`
- `index_buywrite_cboe_bxm`
- `index_short_vol_scs_near_atm_straddle`
- `xs_option_zhan_neg_lnprice_dn_call`
- `xs_option_heston_straddle_momentum_lowcost`

## Exact Founder action

1. Deploy `RELEASE_SHA` to the web service and the cron service.
2. Confirm the cron service reads `railway.cron.json`. The file now declares
   `cronSchedule: "*/10 13-21 * * 1-5"` (UTC), which overrides the dashboard
   value `*/10 13-20`. Hour 21 is required: without it, no tick falls after
   the 16:00 EST close, and Zhan (last session of the month) and Heston
   (monthly expiration) could never form on EST dates.
3. Set `ASA_US_TREASURY_ENABLED=true` on both services. This enables the
   public, credential-free US Treasury bill-rate provider (no vendor, no
   cost). Its consumers at this release are Zhan (risk-free series) and SCS
   (optional risk-free input). While it is unset, those inputs are typed
   UNKNOWN. PUT/PUTY sizing stays typed
   `UNKNOWN_CROSS_SUBJECT_TREASURY_RATE_NOT_MATERIALIZED` whether or not the
   flag is set, and BXM does not use rates.

## Health and readiness after deploy

- `/api/v1/version` `release_sha` equals `RELEASE_SHA` on the web service.
- `/api/v1/health` is green, and `/api/v1/screening/operations` shows the
  scheduler ticking.
- `/api/v1/capabilities` lists all seven strategies.

## Real-session observation (worker, after deploy)

Run after the first full post-deploy session, from a checkout at
`RELEASE_SHA`. `cron.log` holds the cron service's log lines for the window
(each tick's `--json` `bounded_run_cohort` artifact):

```
python -m tools.strategy_production.release_classification \
  --base-url <prod> --production-sha RELEASE_SHA \
  --window-start <session open, ISO-8601> --window-end <after 21:50 UTC> \
  --cron-output cron.log \
  --output project/reports/STRATEGY-PRODUCTION-001-SP-08A-session.json
```

Closure requires:
- all seven classified `LIVE_EVALUABLE`, `LIVE_TYPED_DATA_BLOCKER` or `NOT_DUE`;
- no ASA-defect code in the latest rows;
- every selected-strategy result in the cron artifacts with `error == null`;
- no fixed-subject or complete-family refresh failure line;
- the deployed SHA equal to the release.

Latest-state rows alone cannot prove zero exceptions: a raising pair writes
no row, and a later row overwrites an earlier one. That is why the cron
artifacts are required. Reading the cron service logs needs Railway access,
which the worker does not currently have; the Founder supplies the log
export, or authorizes the Railway connector.

Expected outcomes, stated before observation:

| Strategy | Expected class | Why |
|---|---|---|
| GXZ | `NOT_DUE` or `LIVE_TYPED_DATA_BLOCKER` | Event strategy, due only inside its pre-earnings window |
| PUT / PUTY / BXM | `NOT_DUE` off roll dates; `LIVE_EVALUABLE` or typed blocker on roll | Monthly roll strategies |
| SCS | `NOT_DUE` or `LIVE_EVALUABLE` | Monthly fixed-SPX |
| Zhan | `LIVE_TYPED_DATA_BLOCKER` on month-end formation (`CAPACITY_DEFERRED_INCOMPLETE_COHORT`); `NOT_DUE` (no rows, due callback false on every tick) otherwise | 503 members > ceiling of 30 |
| Heston | Same as Zhan on monthly-expiration formation; also lacks 12 months of A08 history | Same |

**Material disclosure.** Under the current ceiling of 30 subjects, Zhan and
Heston cannot produce a ranking. Each formation day they truthfully defer with
a typed blocker until the atomic per-cycle capacity ceiling is raised. Raising
it is a measured capacity decision, not part of this release. No partial
ranking is substituted.

On a non-formation session, Zhan and Heston write no new rows (the family is
not due). For them, the session proof uses the next formation date: Zhan on
2026-10-30 (last session of October) and Heston on 2026-10-16 or 2026-11-20.

## Rollback

Redeploy `1efac180b66d2c521b22058e10cc74c2939a29f2` to both services. Restore
the cron schedule to `*/10 13-20 * * 1-5` if the dashboard value was replaced.
No migration or data rollback is needed: the release only adds rows, and the
deferral rows are ordinary typed latest-state rows that the previous release
reads without change. Rows already written for strategies the previous
release does not register (Zhan, Heston, SCS) remain in latest state; this
is harmless.

## Residuals (disclosed, not blocking)

1. Extra ticks from 21:00 to 21:50 UTC also run the fixed-subject option and
   SPY benchmark refreshes after the close: about 7 subjects per tick, up to 6
   extra ticks per weekday. Follow-up: gate those refreshes to session slots.
2. A missed formation (no successful after-close tick on the formation date)
   is not written as a typed row. The previous rows simply age.
3. The complete-family claim is taken before the rows are written. A
   persistence failure part-way is not retried that day.

## Post-deploy observation 1 — 2026-10-02 (release `392948d`)

Verified live (read-only API):
- `/api/v1/version` `release_sha` = `392948d546bc76237ddd4e07c0cd41a96f361805`.
- `/api/v1/health` returns ok, and `/api/v1/capabilities` lists all seven strategies.
- The cron service is on the release. GXZ, now on the claim path, wrote 414 typed rows today alongside the cohort strategies.

**Defect found (ASA-owned, fixed in the follow-up corrective PR).** PUT, PUTY,
BXM and SCS on SPX all persisted `subject_preparation_failed`:
- BXM (35-day) and SCS (7-day) declare distinct `INDEX_SETTLEMENT_VALUE_V1` lookbacks on the shared SPX subject.
- No reducer was registered for that capability, so sealing raised and the whole SPX subject failed preparation.
- This was reproduced in-process with the production composition root. It is independent of provider responses; no provider serves settlement values today.
- Fix: a generic `reduce_index_settlement_results` (widest-window deterministic representative, all attempts retained), registered with the shadow capability reducers.
- Regression: the fixed-SPX root with every provider unreachable persists typed per-strategy reasons, never `subject_preparation_failed`. It fails without the fix.

Session 2026-10-02 therefore does **not** satisfy closure: four strategies show an ASA defect. Closure requires redeploying `main` with the fix, then observing one complete session on that release.

Zhan and Heston: 2026-10-02 is neither a month-end nor a monthly-expiration session, so both families are correctly not due and write no rows.

Residual noted: BXM's expansion reuses the PUT expiration-selection helper, so
an expiration-evidence gap carries the PUT gate code `G_PUT_STRIKE_EXISTS_UNKNOWN`
on BXM rows. This is typed and pre-existing (released with #522), not a runtime leak.

## Post-deploy observation 2 — 2026-10-02 (release `244b9aa`, #533)

The Founder redeployed `244b9aa` the same day. From then on, the SPX latest
rows stopped updating (last write 18:23 UTC), while the SPY fixed pairs kept
writing through the 21:53 UTC tick.

A run of the real fixed-subject root with provider-shaped Tradier SPX data
exposed two further ASA defects that #533's fix had unmasked:

1. **Lifecycle output contract.**
   - PUT, PUTY, BXM and SCS returned not-due `NO_SIGNAL` without `opportunity_id`/`lifecycle_stage`, though each declares `OutputKind.LIFECYCLE`.
   - `validate_result` raised, so every pair failed and persisted no row.
   - Zhan and Heston had the same latent gap on their non-pass paths.
   - Fixed at the adapters. As GXZ and Earnings Calendar already do, a completed evaluation now carries the subject opportunity; the lifecycle stage is `identified`, as in GXZ.
2. **Optional rate demand.**
   - SCS's rate demands defaulted to `required=True`.
   - With no enabled rate provider, the registry raised and failed the whole SPX subject.
   - They are now `required=False`, matching Zhan and SCS's own typed-missing evaluation.

Regressions: the fixed-SPX root with provider-shaped data, run with the rate provider disabled, must persist an evaluated row with lifecycle fields for every index strategy. It fails without either fix. Zhan and Heston non-pass rows must satisfy `validate_result`.

Closure therefore requires another redeploy and one complete session on that release.

## Post-deploy observation 3 — 2026-10-05 (release `b87fbf7`)

`b87fbf7` (#537, test-only) is runtime-identical to `2dfaa2d` (#534).

Railway read-only checks:
- Both services ran `b87fbf7` all session, matching `/api/v1/version`.
- The cron service uses `/railway.cron.json` with `*/10 13-21 * * 1-5`.
- `ASA_US_TREASURY_ENABLED=true` is set on both services.

Cron evidence: all 54 ticks from 13:01 to 21:51 UTC emitted a `bounded_run_cohort` artifact.
- No selected-strategy result has a non-null `error`.
- No `*_refresh_failed` warning appears.
- The SPX pairs for PUT, PUTY, BXM and SCS appear on every tick with `error: null`:
  - `no_signal` in 50 ticks;
  - typed `missing_data` in 4 ticks.

The session still fails closure because of one ASA defect: 150 tracebacks.

- **Symptom.** Every tick logged `execution_readiness_projection_failed` with a traceback three times:
  - twice from the Cboe PUT adapter (PUT and PUTY);
  - once from SCS.
- **Root cause.** The not-due SPX results reached the execution-readiness projection. Their assessment builders raised `ValueError` on a non-passing decision. The scheduler caught and logged the error, so no row was lost, but this is an unexplained strategy exception.
- **Fix.** For a result that selected no structure, the PUT/PUTY, SCS and GXZ builders now return a typed `UNKNOWN` assessment with `reason_code=strategy_did_not_select_structure`. Skew Momentum already does the same.
- **Regression.** The fixed-SPX root with provider-shaped Tradier data, run with a lifecycle repository, must project typed readiness for PUT, PUTY and SCS and log no projection failure. Before the fix it reproduces exactly the three production warnings.

Classifier (`45e5c1c`, the #538 capture commit, which leaves runtime identical; window 13:30 to 21:55 UTC):

| Strategy | Class |
|---|---|
| GXZ | `LIVE_TYPED_DATA_BLOCKER` (503 rows) |
| PUT, PUTY, BXM, SCS | `LIVE_TYPED_DATA_BLOCKER` (`G_CBOE_SPX_REF_BEFORE_1100_UNKNOWN`) |
| Zhan, Heston | `NOT_DUE` |

There are no exception rows. The 1.0.0 classifier returned `pass` because it never read `Traceback` lines, the hardening follow-up the hand-off listed. Version 1.1.0, in the same PR, fails the proof on any logged traceback, so this session now classifies as `fail` (`cron_tracebacks:150`).

Same PR: `test_tradier_option_chain_live_run_completes_instead_of_crashing` used "yesterday" as a daily-bar date. That date is not a session on a Monday, so the test failed. It now uses the previous session date, which keeps `full_suite_green`.

Closure requires deploying this fix and observing one complete session on that release.
