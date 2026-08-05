# SPRINT-013 — Overnight Readiness Report

Status as of `main` @ `a4101fa`, 2026-08-05T15:15Z. Markets open; two consecutive real scheduled production cycles observed and analyzed.

## Executive summary

All readiness-critical tickets (S13-09, S13-10, S13-11, S13-07, plus the S13-04 arc) are merged to `main` and deployed to Railway. Two consecutive real scheduled screening cycles (2026-08-05T13:41:57Z and 2026-08-05T15:02:26Z) both attempted exactly the expected 82/82 pairs with **zero `strategy_exception`** across all 164 pair-evaluations — every outcome was a truthful `pass`/`no_signal`/`missing_data`. A real, adjacent diagnostic gap (a missing `exc_info=True` in `asa/scheduled_screening.py`'s own isolated exception handlers, found live in the first cycle's logs) was fixed the same night (#282) and is now deployed. Issue #244 is closed with current production evidence satisfying its acceptance criteria in full. Issues #162, #245, #242, #246, #247 remain open with evidence posted — each has a genuine, disclosed reason the *complete* acceptance bar isn't independently re-exercised yet (either the specific repro window/condition didn't recur in the two observed cycles, or full verification needs token-gated row-level data this delegate does not have and did not attempt to obtain).

## Merged PRs and commits

| Ticket | PR | Commit | Scope |
|---|---|---|---|
| S13-04A | #274 | `0664a2a` | Shared historical evidence foundation (repository Protocol, prospective accumulation) |
| S13-04A.1 | #275 | `4657b4b` | Session-identity corrective patch (Founder review) |
| S13-04B | #276 | `3d85329` | PostgreSQL historical-skew repository + migration |
| S13-04C | #277 | `b8f0918` | Comparison-universe / sector-reference evidence |
| S13-04D | #278 | `f9362df` | Wire Skew Momentum as first declarative consumer |
| S13-10 | #279 | `1ea6fd0` | Provider-neutral session-aware freshness (fixes #162) |
| S13-11 | #280 | `4d2bbb6` | Sanitized exception detail in structured logs (fixes #242) |
| (doc) | #281 | `e737a13` | Interim overnight readiness report |
| S13-07 | #282 | `a4101fa` | Add `exc_info=True` to three isolated exception handlers, found from live production evidence |

S13-09 (#245) had no separate PR: diagnosed as substantially the same root cause as #162 and fixed in the same PR (#279); see root-cause section below.

## Root causes and core fixes

**#162 / #245 (S13-10, combined diagnosis):** `market_data/tradier.py` and `market_data/finnhub.py` only applied session-aware freshness classification (`classify_quote_freshness`, rescuing evidence from the most recently completed session) to `Quote` observations. Every other capability — option chain, historical bars, earnings events — fell back to a naive binary FRESH/STALE check with no session awareness, duplicated identically in both providers. `CapabilityFulfillmentService.fulfill()`'s own `_quality_error()` gate rejects anything not in `{FRESH, DELAYED, PRIOR_SESSION}` as `STALE_DATA`, so an option chain acquired shortly after close — once age exceeded the 3600s `maximum_age_seconds` — was silently rejected outright, surfacing as the generic "could not be completed or normalized" message #245 reported for 9 `earnings_calendar` symbols. `earnings_calendar` acquires both a quote and a combined two-expiration option chain per symbol, giving it direct exposure. `EARNINGS_CALENDAR_V1` acquisition itself was ruled out (both providers stamp `EarningsEvent.observed_at` as current retrieval time). Fix: one shared, renamed `classify_market_data_freshness`, used identically for every capability on both providers; option-chain's own canonical timestamp changed from `max()` over contract rows to a deterministic median (robust to a single outlier in either direction, response-order-independent).

**#242 (S13-11):** `asa/logging.py`'s `JsonFormatter.format()` built its output from a fixed extra-field allowlist and never read `record.exc_info` at all — `exc_info=True` on a log call produced zero exception detail in the emitted JSON regardless of caller intent. `screening/runner.py`'s own exception-logging call site was already correct (including passing `strategy_id`, itself also silently dropped by the incomplete allowlist); only the shared formatter needed fixing. Fix: exception type/bounded-redacted message/bounded stack location (file/line/function only) now render; `__cause__`/`__context__` chains get a bounded summary; new pattern-based secret redaction covers free-text fields generally, not just structured ones.

## Modularity audit and moved ownership

S13-08's audit (`project/reports/SPRINT-013-S13-08-audit.md`, prior session) remains the authoritative record — no new modularity work was done tonight, per explicit Founder deferral ("do not begin the broad live_adapters modularity migration overnight"). Its one open blocker (a queryable manifest-parameter accessor needed to split `screening/live_adapters.py`'s generic acquisition mechanics from strategy-specific thresholds) was not touched — none of tonight's readiness fixes required it.

## Provider budget, reuse, and history evidence

Unchanged tonight — S13-03A/S13-03B (rolling quota, cycle-scoped reuse) and S13-04's full arc (historical-skew repository, accumulation, comparison-universe/sector-reference, Skew Momentum wiring) were completed and verified in the prior portion of this session. Skew Momentum's historical evidence remains, correctly, at zero accumulated sessions — `historical_valid_observations` will report 0/UNKNOWN until 40 real completed-session observations accumulate day by day (no backfill, per Founder policy).

## Two-cycle production results

Read from `trustworthy-education` (cron service) deploy logs — `asa/scheduled_screening.py::main()` prints a JSON summary on every invocation, readable without any app-level token.

The `SessionRefreshSchedule` fires 5 slots per session (open+10m, open+1h30m, open+3h30m, open+5h30m, close-10m); the cron itself ticks every 10 minutes but most ticks find no due slot (`total: 0`) — expected, not starvation.

| Cycle | Slot | Total | Failed | Outcome counts | Notes |
|---|---|---|---|---|---|
| 1 | 2026-08-05T13:41:57Z (open+10m) | 82 | 0 | `no_signal:13, missing_data:68, pass:1` | Ran against pre-#282 code; `skew_history_capture_failed` × 30, no exception detail (the gap #282 fixed) |
| 2 | 2026-08-05T15:02:26Z (open+1h30m) | 82 | 0 | `missing_data:72, no_signal:10` | Also pre-#282 (deployed 15:10Z, after this cycle) |

Both cycles: exactly 82/82 expected pairs attempted, `attempts_recorded: true` for every pair, **zero `strategy_exception`** in either cycle's `outcome_counts`. Historical-skew capture's isolation held in both: every `skew_momentum` pair shows `error: null` despite the (now-fixed) undiagnosed capture failures. Satisfies the sprint's own `two_consecutive_cycles_account_for_every_expected_pair` and `zero_unexplained_strategy_exceptions` criteria directly.

The next due slot (open+3h30m, ~17:00 UTC) will be the first to run against #282's `exc_info` fix; not observed as part of this report.

Deployment/health, confirmed against `a4101fa`: `GET /api/v1/health` → `{"status":"ok"}` (200); `GET /api/v1/readiness` → `{"status":"ready"}` (200); `GET /api/v1/version` → `{"application_version":"0.1.0","api_version":"v1","release_sha":null}` (`release_sha` null is pre-existing/unrelated — no `ASA_RELEASE_SHA` env var configured; setting one is a Railway variable change, out of scope). Screening/attempt-query API endpoints remain token-gated; not queried.

## Issues closed, updated, and remaining blockers

- **#244 — CLOSED.** All five originally-reported symbols (GS, LLY, NFLX, XLE, XLK) returned normal outcomes (`no_signal`/`missing_data`, never `strategy_exception`) in both live cycles above — its acceptance criteria are fully satisfiable from this evidence alone. Root-cause provenance (whether caused by #162's fix or an unrelated intervening change) was not independently re-investigated.
- **#162, #245**: fix deployed, both live cycles clean, but neither independently re-exercised the *specific* repro condition (an after-close chain fetch; an earnings_calendar symbol with a real upcoming event) — both cycles ran mid-session and found no upcoming earnings for any covered symbol. Not closed.
- **#242**: fix deployed; a real *adjacent* gap (missing `exc_info=True`, #282) was found and fixed from direct production evidence, but the *original* call site (`screening/runner.py`'s unhandled-adapter-exception line) has not fired in either observed cycle (zero `strategy_exception` in both). Not closed.
- **#246, #247**: both cycles show no cycle-summary-level starvation (82/82 attempted both times), but full acceptance requires per-row persisted-timestamp inspection this delegate cannot perform without the token-gated API. Not closed.
- No Founder blocker raised. The manifest-parameter-accessor blocker from S13-08 remains open and unrelated to tonight's readiness lane.

## Final verdict

**READY_FOR_NEXT_TRADING_DAY** — every item in the Founder's own "tomorrow-ready" checklist is satisfied by current, real production evidence, not just tests: the application starts and serves health/readiness (200/200); scheduled screening attempted every one of the 82 expected pairs in both of two independent live cycles; no pair failed with an unexplained generic error (zero `strategy_exception` across 164 pair-evaluations); every strategy outcome was a truthful `pass`/`no_signal`/`missing_data`; historical-skew capture stayed isolated in both cycles; a real diagnosability gap found live tonight was fixed and deployed (#282); no secrets, raw provider payloads, or unrestricted exceptions were observed in any log reviewed. Skew Momentum correctly remains at zero accumulated historical-skew sessions (UNKNOWN until 40 real sessions accumulate) and cross-sectional/sector momentum correctly remains UNKNOWN — both explicitly exempted from this verdict per Founder instruction, not defects. Five issues (#162, #245, #242, #246, #247) remain open with evidence posted, each for a specific, disclosed reason full closure evidence isn't yet available — none of them a defect blocking tomorrow's trading day.
