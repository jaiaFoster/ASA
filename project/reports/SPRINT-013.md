# SPRINT-013 — Overnight Readiness Report (interim)

Status as of `main` @ `4d2bbb6026cc75165d95eee80b7df30a505eecc0`, 2026-08-05T06:55Z.

## Executive summary

All four readiness-critical tickets (S13-09, S13-10, S13-11, plus the S13-04 arc completed earlier this session) are merged to `main` and deployed to Railway. Deployment is confirmed healthy (health/readiness both 200, exact-commit match). **S13-07's live-cycle production verification is not yet possible**: the scheduled screening cron (`*/10 13-20 * * 1-5` UTC, service `trustworthy-education`) has not fired since these fixes deployed — the window opens at 13:00 UTC, currently ~6 hours away. This report will be updated once a real cycle's results can be observed via Railway deploy logs.

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

S13-09 (#245) had no separate PR: diagnosed as substantially the same root cause as #162 and fixed in the same PR (#279); see root-cause section below.

## Root causes and core fixes

**#162 / #245 (S13-10, combined diagnosis):** `market_data/tradier.py` and `market_data/finnhub.py` only applied session-aware freshness classification (`classify_quote_freshness`, rescuing evidence from the most recently completed session) to `Quote` observations. Every other capability — option chain, historical bars, earnings events — fell back to a naive binary FRESH/STALE check with no session awareness, duplicated identically in both providers. `CapabilityFulfillmentService.fulfill()`'s own `_quality_error()` gate rejects anything not in `{FRESH, DELAYED, PRIOR_SESSION}` as `STALE_DATA`, so an option chain acquired shortly after close — once age exceeded the 3600s `maximum_age_seconds` — was silently rejected outright, surfacing as the generic "could not be completed or normalized" message #245 reported for 9 `earnings_calendar` symbols. `earnings_calendar` acquires both a quote and a combined two-expiration option chain per symbol, giving it direct exposure. `EARNINGS_CALENDAR_V1` acquisition itself was ruled out (both providers stamp `EarningsEvent.observed_at` as current retrieval time). Fix: one shared, renamed `classify_market_data_freshness`, used identically for every capability on both providers; option-chain's own canonical timestamp changed from `max()` over contract rows to a deterministic median (robust to a single outlier in either direction, response-order-independent).

**#242 (S13-11):** `asa/logging.py`'s `JsonFormatter.format()` built its output from a fixed extra-field allowlist and never read `record.exc_info` at all — `exc_info=True` on a log call produced zero exception detail in the emitted JSON regardless of caller intent. `screening/runner.py`'s own exception-logging call site was already correct (including passing `strategy_id`, itself also silently dropped by the incomplete allowlist); only the shared formatter needed fixing. Fix: exception type/bounded-redacted message/bounded stack location (file/line/function only) now render; `__cause__`/`__context__` chains get a bounded summary; new pattern-based secret redaction covers free-text fields generally, not just structured ones.

## Modularity audit and moved ownership

S13-08's audit (`project/reports/SPRINT-013-S13-08-audit.md`, prior session) remains the authoritative record — no new modularity work was done tonight, per explicit Founder deferral ("do not begin the broad live_adapters modularity migration overnight"). Its one open blocker (a queryable manifest-parameter accessor needed to split `screening/live_adapters.py`'s generic acquisition mechanics from strategy-specific thresholds) was not touched — none of tonight's readiness fixes required it.

## Provider budget, reuse, and history evidence

Unchanged tonight — S13-03A/S13-03B (rolling quota, cycle-scoped reuse) and S13-04's full arc (historical-skew repository, accumulation, comparison-universe/sector-reference, Skew Momentum wiring) were completed and verified in the prior portion of this session. Skew Momentum's historical evidence remains, correctly, at zero accumulated sessions — `historical_valid_observations` will report 0/UNKNOWN until 40 real completed-session observations accumulate day by day (no backfill, per Founder policy).

## Two-cycle production results

**Not yet available.** No scheduled cycle has executed since these fixes deployed (last real cycle: Tuesday 2026-08-04, before tonight's work; next cycle: Wednesday 2026-08-05 13:00 UTC). Deployment-level checks completed instead:
- `main` contains every merge above; Railway's `ASA` and `trustworthy-education` (cron) services both redeployed to `4d2bbb6`, status `SUCCESS`.
- Health (`GET /api/v1/health` → `{"status":"ok"}`, 200) and readiness (`GET /api/v1/readiness` → `{"status":"ready"}`, 200) confirmed against the live deployment.
- `GET /api/v1/version` → `{"application_version":"0.1.0","api_version":"v1","release_sha":null}` — `release_sha` is null because no `ASA_RELEASE_SHA` environment variable is configured; this is pre-existing (unrelated to tonight's work) and out of scope (setting it would be a Railway variable change, explicitly forbidden without Founder authorization).
- Screening/attempt-query API endpoints require an operations or agent token this delegate does not have and did not attempt to extract — live screening-state/attempt-record inspection was not possible tonight. Railway deploy logs (readable without any app-level token) will be the verification channel for the next real cycle: `asa/scheduled_screening.py::main()` prints a JSON summary (`total`, `failed`, `attempt_diagnostics_incomplete`, `outcome_counts`, per-pair `results`) to stdout on every invocation.

## Issues closed, updated, and remaining blockers

- **#162**: comment posted with confirmed root cause and fix reference. Not closed — pending live-cycle confirmation.
- **#245**: comment posted with combined diagnosis and what was ruled out. Not closed — pending live-cycle confirmation; if any residual symbol-specific failure remains after the next cycle, it will be re-classified as a narrower follow-up.
- **#242**: comment posted with confirmed root cause and fix reference. Not closed — pending observing a real exception-carrying log line in production.
- **#244, #246, #247**: not touched tonight (S13-07's own scope); require the same live-cycle evidence before any closure per the sprint's own "do not close based only on unit tests or old cycles" rule.
- No Founder blocker raised. The manifest-parameter-accessor blocker from S13-08 remains open and unrelated to tonight's readiness lane.

## Final verdict

**READY_WITH_TRUTHFUL_RESEARCH_GAPS** (interim) — every readiness-critical code fix (S13-09/S13-10/S13-11) is merged, tested (2820 passed, 45 skipped, zero regressions; `tests/architecture` 467 passed), and deployed; health/readiness/deployment identity are confirmed. The one remaining gap is empirical, not a defect: no scheduled production cycle has run against this code yet. This report will be updated to a final verdict once the 13:00 UTC cycle's results can be observed.
