# STRATEGY-PRODUCTION-001 — SP-08A Founder deployment packet

- Ticket: `SP-08A` (Founder-only action: production deployment)
- Release: exact `main` at the merge commit of this SP-08A PR (`RELEASE_SHA`, reported on the PR and in the Founder handoff). SP-08A adds only a read-only tool and this packet; runtime content is identical to `e987af9` (SP-07B).
- Currently deployed: `1efac180b66d2c521b22058e10cc74c2939a29f2` (SP-06B, #522)
- Database migrations between deployed and release: none

## Contents since the deployed release

| PR | Ticket | Production effect |
|---|---|---|
| #527 | SP-05C | Zhan cross-sectional strategy registered, cataloged, cut over |
| #528 | SP-05D | Heston straddle-momentum strategy registered, cataloged, cut over |
| #529 | SP-07A | Seven-strategy convergence: GXZ on the production claim path; complete-family (Zhan/Heston) atomic scheduling with persisted typed deferral; SCS cut over; cron covers after-close formation ticks |
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
   public, credential-free US Treasury bill-rate provider (no vendor, no cost)
   that PUT, PUTY and BXM need. While it is unset, those strategies report a
   typed rate blocker.

## Health and readiness after deploy

- `/api/v1/version` `release_sha` equals `RELEASE_SHA` on the web service.
- `/api/v1/health` is green, and `/api/v1/screening/operations` shows the
  scheduler ticking.
- `/api/v1/capabilities` lists all seven strategies.

## Real-session observation (worker, after deploy)

Run after the first full post-deploy session:

```
python -m tools.strategy_production.release_classification \
  --base-url <prod> --production-sha RELEASE_SHA \
  --window-start <session open, ISO-8601> --window-end <session close + 1h> \
  --output project/reports/STRATEGY-PRODUCTION-001-SP-08A-session.json
```

Closure requires all seven classified `LIVE_EVALUABLE`,
`LIVE_TYPED_DATA_BLOCKER` or `NOT_DUE`, zero exceptions, and the deployed SHA
equal to the release.

Expected outcomes, stated before observation:

| Strategy | Expected class | Why |
|---|---|---|
| GXZ | `NOT_DUE` or `LIVE_TYPED_DATA_BLOCKER` | Event strategy, due only inside its pre-earnings window |
| PUT / PUTY / BXM | `NOT_DUE` off roll dates; `LIVE_EVALUABLE` or typed blocker on roll | Monthly roll strategies |
| SCS | `NOT_DUE` or `LIVE_EVALUABLE` | Monthly fixed-SPX |
| Zhan | `LIVE_TYPED_DATA_BLOCKER` on month-end formation (`CAPACITY_DEFERRED_INCOMPLETE_COHORT`); otherwise not written | 503 members > ceiling of 30 |
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
reads without change.

## Residuals (disclosed, not blocking)

1. Extra ticks from 21:00 to 21:50 UTC also run the fixed-subject option and
   SPY benchmark refreshes after the close: about 7 subjects per tick, up to 6
   extra ticks per weekday. Follow-up: gate those refreshes to session slots.
2. A missed formation (no successful after-close tick on the formation date)
   is not written as a typed row. The previous rows simply age.
3. The complete-family claim is taken before the rows are written. A
   persistence failure part-way is not retried that day.
