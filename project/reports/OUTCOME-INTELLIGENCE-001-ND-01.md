# OUTCOME-INTELLIGENCE-001 — ND-01 System-Actionable Enrollment

- **Decision:** `OUTCOME-INTELLIGENCE-001-ND-01-ARCHITECT-DECISION.md`, APPROVED-WITH-AMENDMENTS at R3.
- **Sequencing:** follows PR #493 and must not ride on it. The PR carries migration `0020`, and main auto-deploys and runs `alembic upgrade head`, so the **merge is Founder-only.**
- **Status:** implementation-complete and tested. The PR opens only after #493 is merged.

## What ships

| Layer | Change |
|---|---|
| Schema (`0020`) | `proposal_outcome_enrollments` and `enrolled_proposal_outcome_observations`. These are sibling tables with no update or delete path. The outcome table has FK `ON DELETE RESTRICT`, the status and observed-time CHECKs from 0019, and `enrolled_at >= evidence_observed_at`. Enrollments are UNIQUE on proposal identity and on the `(signal, version, symbol, session_date)` slot. Migrations 0016–0019 are untouched. |
| Freezing | `asa/application/proposal_freezing.freeze_proposal` is the single path used by both user tracking and system enrollment. The `TrackCandidateService` behaviour is unchanged. |
| Enrollment | `ProposalEnrollmentService` (`oi-enroll-v1`):<ul><li>enrolls only when the artifact's observation equals the authoritative row and the result is a canonical `OptionTradeProposal`;</li><li>the first proposal per New York session slot wins;</li><li>cap of 8 enrollments per session, taken in `(signal, symbol)` order;</li><li>an already-enrolled slot is reported as such, never as deferred by the cap;</li><li>no backfill.</li></ul> |
| Cron | `asa/scheduled_enrollment.py`, called in its own isolated `try` after the pair loop and before collection. It receives only qualifying pairs. The tick JSON is unchanged. |
| Collector | Generalized over `user_tracked` and `system_actionable` subjects. The subject cap is shared, user subjects are served first, and deferrals are reported per source. The content-identity payload is unchanged, so user outcomes replay idempotently. The collector still never reads latest state or readiness. |
| API | New read-only `GET /api/v1/forward-outcomes/system-enrollments`. Each row carries `enrollment_source` and a derived `also_tracked_by_user` flag. No portfolio endpoint or existing response model changes. |
| UI and OI-07 | The Outcomes view shows a system corpus and a user corpus; the OI-06 sample guard reports each source. The session capture and the data-value report keep the corpora separate. A capture taken before ND-01 reads as `not_captured`, never as zero. |

## Validation

- `tests/asa/test_proposal_enrollment.py` covers the Architect's §7 tests 1–11, including a real-Postgres test of insert-only behaviour, idempotency, the slot constraint, replay and conflict, and the RESTRICT FK.
- Migration `0019 → 0020 → 0019 → 0020` runs on Postgres 16.
- Full backend suite with a live DB: **3,641 passed / 2 skipped**.
- ui-tests: **23/23**. `tests/tools`: **36 passed**.
- ruff and mypy (`asa`) are clean.

## Operating notes

- If a cap deferral turns into a `missed` horizon on 3 or more of 10 sessions, stop and escalate. Budgets are never raised unilaterally.
- Downgrading `0020` in production destroys system forward evidence that cannot be regenerated, so it is Founder-only.

## Independent review (APPROVE-WITH-FIXES) and disposition

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | HIGH | Evidence was cached per symbol, so a second same-symbol subject with different expirations reused a chain that lacked its legs. The outcome was finalized as observed with unknown P&L. | **Fixed in #493** (`f72e73a`), because the defect is latent in OI-03 itself. The cache key is now `(symbol, frozen expirations)`. A test and a golden content-identity pin were added. |
| 2 | MEDIUM | §4 requires distinct opportunity and exact-leg-set counts. | **Fixed.** The system-enrollments API exposes `exact_leg_set`. The capture records it, and OI-07 reports `distinct_opportunities` and `distinct_exact_leg_sets` beside the row count. |
| 3 | MEDIUM | Enrollment was not tied to this tick's own result. | **Fixed.** `PairOutcome` carries `observation_id`. The service requires the authoritative row to equal that observation and to still be `pass`. |
| 4 | MEDIUM | One bad pair aborted the tick. | **Fixed.** Pairs are isolated (`enrollment_failed` is counted and logged). Clock skew is skipped as `evidence_after_clock`. |
| 5 | LOW | The closure gate pooled the two sources. | **Fixed.** The gate detail reports observed horizons per source. |
| 6 | LOW | The session cap was not atomic. | **Fixed.** A per-session `pg_advisory_xact_lock` plus a count check now run in the insert transaction. |
| 7 | LOW | The collector and API run one query per enrollment. | **Follow-up.** Growth is bounded at ≤ 8 enrollments per session, about 2,000 a year. Fully resolved subjects should be skipped before the corpus reaches that size. |
| 8 | LOW | No golden content identity was pinned. | **Fixed in #493** (`f72e73a`). |
| 9 | LOW | The scan was narrow, and `deferred_by_source` counts horizons. | **Fixed.** The scan now includes `asa/scheduled_enrollment.py`. The counter counts horizons deferred, matching `deferred_by_subject_cap`. |
