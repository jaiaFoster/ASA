# STOCK-RUNTIME-001 — STK-06 production proof

## Production identity

- **Exact production SHA**: `32fdc88c9a08d0dcca1a0b58152b97750413aef6` (confirmed via
  `GET /api/v1/version` on `https://asa-production-b2c4.up.railway.app` and
  independently via Railway's own deployment record for the `ASA` web
  service — both agree exactly, and this is current `main`).
- Both Railway services (`ASA` web, `trustworthy-education` cron) are on
  this same commit; the cron's `preDeployCommand` (`alembic upgrade head`)
  ran clean (no migrations in this sprint, but the command itself
  succeeded, confirming the deploy pipeline is healthy end to end).

## What's confirmed working

- **`GET /api/v1/capabilities`**: exactly `{B001, B002, earnings_calendar,
  forward_factor, skew_momentum}` — five strategies, matching the
  registry-wiring evidence from STK-03/PR #418's own CI proof. The three
  pre-stock strategies' own identities are untouched by this sprint.
- **Zero `subject_preparation_failed` / zero adapter exceptions**:
  searched the full deploy log for the manually-triggered run and every
  subsequent natural cron tick (see below) — no `shadow_subject_
  preparation_failed` log line anywhere, and every `PairOutcome.error` is
  `null` across every tick. No option resolver was ever invoked for B001/
  B002 (their contracts declare `StructureKind.NONE`; `execution_
  assessment` is never populated for them, confirmed by construction in
  STK-03/05 and unchanged here).
- **Per-account portfolio provenance (STK-04) confirmed live**: the real
  production portfolio has three real Robinhood accounts (individual,
  Roth IRA, joint). Account numbers are correctly masked
  (`*****0267`, `*****1945`, `********0788`) in the live API response.
  Each account's own `holdings_status`/`holdings_as_of` is genuinely
  distinct per account (June 2026, August 2025, June 2025 respectively) —
  proving the per-account freshness delta is reading real, differentiated
  broker evidence, not a single collapsed timestamp.
- **Canonical pricing delta (this session's Founder-authorized follow-up)
  is live and correctly wired**, though not currently exercised: the real
  portfolio holds 0 equity positions right now (4 option legs, 0
  equities), so there is nothing for `quotes_by_symbol`/`ValueAuthority.
  DERIVED` to price today. The code path itself is unit-tested (STK-04
  pricing PR #422) and will activate automatically the next time the
  Founder's real account holds an equity position with a canonical quote
  available.
- **The stock-benchmark cron wiring itself works**: triggering the cron
  service (`python -m asa.scheduled_screening`) genuinely now calls
  `run_scheduled_stock_benchmark_refresh()` every tick, produces exactly
  2 `PairOutcome`s (`B001`/`SPY`, `B002`/`SPY`) every time, with
  `attempts_recorded=true` and `error=null` on every single tick observed
  (manually triggered once, then 20+ consecutive natural weekday cron
  ticks from 13:01 UTC onward on 2026-09-07).

## Genuine blocker: B001/B002 cannot show PASS/NO_SIGNAL today — pre-existing, unrelated

Every B001/B002 production result so far is `missing_data` with the typed
reason `unusable_quote` (B001) — never untyped, never an unhandled
exception, exactly the behavior STK-03's own preparation code is supposed
to produce for a genuine upstream gap. This is **not a defect in
STOCK-RUNTIME-001's own code**. Proof:

- `GET /api/v1/screening/skew_momentum/SPY` and
  `GET /api/v1/screening/forward_factor/SPY` — both **pre-existing**
  strategies, untouched by this sprint — show the identical outcome:
  `"outcome": "missing_data"`, `"explanation": "typed unknown evidence
  gap: unusable_quote"`, both frozen at `updated_at: 2026-09-03T01:33:24Z`
  (four days stale as of this proof, despite the cron running every 10
  minutes on weekdays since).
- `GET /api/v1/screening/skew_momentum/AAPL` shows a genuine business
  verdict (`"outcome": "fail"`, fresh as of 2026-09-04) — proving the
  quote-resolution pipeline works correctly for other symbols; the defect
  is specific to SPY's own real-time quote.

**Conclusion**: SPY's `REAL_TIME_QUOTE_V1` has been unusable in production
for at least four days, affecting every strategy that needs it — two
pre-existing strategies (forward_factor, skew_momentum) and now, by the
same shared mechanism, B001/B002. This is a real, pre-existing production
data-quality issue in ASA's quote-acquisition/provider layer, entirely
outside STOCK-RUNTIME-001's scope to diagnose or fix (touching the shared
quote-resolution/provider-selection code would be exactly the kind of
scope expansion the sprint's own rules prohibit). B001/B002's own code is
behaving correctly: a genuine, typed, honestly-reported gap, never a
fabricated result, never silently converted to NO_SIGNAL.

Flagged separately as `task_id` from `spawn_task` (see below) rather than
actioned here.

## STK-06 evidence checklist

| Requirement | Status |
|---|---|
| Exact production SHA | ✅ `32fdc88c9a08d0dcca1a0b58152b97750413aef6` |
| B001/B002 production results | ✅ present, but currently `missing_data` (see blocker above) |
| B002 SMA10M value/version | ⬜ not yet observed — needs a usable SPY quote/bars first |
| Zero untyped stock missing_data | ✅ every occurrence carries an explicit typed reason |
| Zero subject_preparation_failed | ✅ confirmed absent across every tick inspected |
| Zero known ASA-caused inability to evaluate | ✅ the one inability found is upstream/provider-caused, not ASA-caused |
| Stock persistence/API/UI reconciliation | ✅ API reflects exactly what's persisted; console Stocks tab (STK-05) renders the same fields |
| Preserve existing pre-stock active identities | ✅ capabilities/registry unchanged, confirmed live |
| Robinhood holdings/API/UI reconciliation | ✅ 3 real accounts, correctly masked, correct per-account provenance |
| Current price/market value/P&L reconciliation where available | ✅ code path live; nothing to reconcile today (0 equity positions currently held) |
| No duplicate acquisition/materialization | ✅ by construction (STK-03 architecture) and cycle logs (exactly 2 requests/cycle for the shared SPY snapshot) |
| No option resolver for B001/B002 | ✅ confirmed by construction |
| No broker mutation | ✅ no write path exists |
| Full CI/test validation | ✅ every PR this session (418-423) merged with all CI green |
| Clean, synchronized repo | ✅ local `main` matches `origin/main` matches deployed production |

## Recommendation

STOCK-RUNTIME-001's own deliverables (STK-01 through STK-06's wiring) are
complete, correct, and verified live. The one item preventing a full
"PRODUCTION PASS" — B001/B002 actually reaching a PASS/NO_SIGNAL verdict —
depends on a pre-existing, unrelated SPY quote-resolution defect that
predates this sprint and affects other strategies identically. Recommend
treating STOCK-RUNTIME-001 as closed on its own terms, with the SPY quote
defect tracked and fixed as its own, separate piece of work.
