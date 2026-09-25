# ND-01 Architect Decision: auto-enrolling system proposals into forward outcomes

ROLE-ARCH (independent reviewer instance) · OUTCOME-INTELLIGENCE-001 · 2026-09-25 · read-only review of branch `claude/asa-options-product-handoff-per43n` @ ae16792 (PR #493 on main d52146f)

**Verdict: APPROVED-WITH-AMENDMENTS.** Auto-enrollment is approved. It must not reuse `tracked_candidates`. It ships as a separate R3 PR after #493 merges. The amendments below are binding.

## 1. Facts relied on

- **The user-only corpus cannot reach the sample guard.** The collector walks only `lifecycle.candidates()` (`asa/application/forward_outcomes.py:144`). The OI-06 guard needs 30 outcomes with P&L per strategy (`asa/ui/static/prioritize.js`). Production has one tracked candidate, and its d1/d5/d10 horizons will be recorded as `missed`.
- **Reusing `tracked_candidates` would mix system records into the user's portfolio:**
  - Reconciliation writes a lifecycle observation for every candidate (`asa/application/portfolio_lifecycle.py:109,117-140`).
  - `GET /portfolio/tracked-candidates` lists every candidate.
  - The candidate id is `uuid5(observation_id)` and inserts use `ON CONFLICT (originating_observation_id) DO NOTHING`. A user who later tracks a proposal that was already auto-enrolled would silently get the system row back, with the system's `tracked_at`. That falsifies the user's tracking record.
- **`execution_readiness_artifacts` holds only the latest proposal.** It has one row per `(signal_id, symbol)` and is overwritten each cycle. It is safe to read only in the same tick that wrote it, and only while its observation id matches.
- **Proposal identity changes every cycle.** It includes the originating result identity (`strategy_runtime/trade_proposal.py:119-136`), so deduplicating on identity alone would inflate the corpus with near-duplicates.
- **The ledger is tied to tracked candidates:** it is foreign-keyed to `tracked_candidates` with `ON DELETE RESTRICT` (migration 0019).
- **Horizons are generic.** They are anchored on the New York session date of `evidence_observed_at` (`strategy_runtime/forward_outcome.py`).

## 2. Source semantics (binding)

- There are two sources:
  - `user_tracked`: the existing tables, unchanged.
  - `system_actionable`: new tables.
- The source is structural (determined by which table a record is in), not a flag column.
- System enrollments never appear in portfolio or tracking endpoints. They are never reconciled and never get lifecycle observations.
- Outcome read models label every row `enrollment_source`. The label "paper/modeled, not brokerage fill" stays.
- **Selection-bias disclosure:** `system_actionable` covers every proposal ASA itself judged actionable (under the §4 sampling rule); `user_tracked` covers the user's choices. OI-05, OI-06 and OI-07 report the two sources separately and never pool them silently.

## 3. Schema (migration `0020`; Founder merge)

- **`proposal_outcome_enrollments`**
  - Primary key: `id` = `uuid5("asa:enrolled:" + resolved_proposal_identity)`.
  - Columns:
    - `enrollment_policy_version` (`oi-enroll-v1`)
    - `originating_observation_id`, `opportunity_id` (nullable)
    - `signal_id`, `signal_version`, `symbol`
    - `session_date`, `evidence_observed_at`, `enrolled_at`
    - `resolved_proposal_identity`: NOT NULL, UNIQUE
    - `resolved_proposal_json`: NOT NULL
  - Constraints: UNIQUE `(signal_id, signal_version, symbol, session_date)`; CHECK `enrolled_at >= evidence_observed_at`.
- **`enrolled_proposal_outcome_observations`**
  - Same columns and CHECKs as 0019, with primary key `(enrollment_id, horizon_id)`.
  - FK to `proposal_outcome_enrollments` with `ON DELETE RESTRICT`.
- No update or delete path exists for either table, and 0016–0019 are not altered.
- Downgrade drops only the system corpus. That evidence cannot be regenerated, so running a downgrade in production is Founder-only.
- Sibling tables were chosen over re-keying 0019. Re-keying would reopen an approved R3 ledger and, after merge, force a data migration of evidence that cannot be regenerated.

## 4. Enrollment

- **Where:** a new use case, `asa/application/proposal_enrollment.py`, invoked in `asa/scheduled_screening.py` after the pair loop. It runs in its own isolated `try`, before `run_scheduled_outcome_collection()`. The tick JSON is unchanged.
- **Input:** enroll only when:
  - `artifact.originating_observation_id == row.observation_id`; and
  - `build_option_trade_proposal` returns an `OptionTradeProposal` (`CONSTRUCTIBLE_AS_INTENDED`).
  - Stock and unavailable proposals are not enrolled.
  - Nothing branches on a strategy ID, and no manifest field is added.
- **Freezing:** extract the freezing code in `portfolio_lifecycle.py:49-72` into one pure function shared by tracking and enrollment, so both produce byte-identical frozen JSON and identity.
- **Sampling (`oi-enroll-v1`):**
  - Enroll the first actionable proposal per `(signal_id, signal_version, symbol, New York session_date)`.
  - At most 8 new enrollments per session, in deterministic `(signal_id, symbol)` order. Enrollments over the cap are logged as `enrollment_deferred_by_cap`.
  - Re-enrollment on later sessions is allowed. Reports must show distinct `opportunity_id` and exact-leg-set counts next to the row count.
- **Timing:** `enrolled_at` is the tick clock and the anchor is `evidence_observed_at`. Horizons due before enrollment are recorded as `not_observable_before_tracking`. There is no backfill.
- **When both sources hold the same proposal**, both series are kept. Corpus statistics use the system series. The "also tracked by user" flag is derived by a join, not stored.

## 5. Collector changes

- Generalize the collector over a subject tuple `(key, symbol, anchor, start_at, frozen structure)` with a repository per source.
- All look-ahead invariants from the OI-02/04 decision apply unchanged.
- **Budget:**
  - Keep `DEFAULT_MAXIMUM_SUBJECTS_PER_TICK = 10`, shared across both sources.
  - `user_tracked` subjects are served first.
  - `deferred_by_subject_cap` is reported per source.
  - If a cap deferral turns into a `missed` on 3 or more sessions within 10, stop and escalate. Nobody raises budgets unilaterally.

## 6. Risk and sequencing

- **R3.** It adds a data set that cannot be regenerated, a new cron write path, and demand on the shared provider budget.
- **Must follow #493; it may not ride on it.** The merge applies a migration automatically, so it is Founder-only.
- **Stop and escalate** if the implementation touches 0016–0019 or an existing response model, needs a manifest field, acquires data outside `market_data`, branches on a strategy ID, or calls a broker.

## 7. Tests required

1. System enrollments never appear in tracked-candidate endpoints or reconciliation.
2. A user tracking an already-enrolled proposal gets their own row with their own `tracked_at`.
3. Freezing parity between tracking and enrollment.
4. Stale artifacts and unavailable proposals are not enrolled.
5. Only the first proposal per session is enrolled, the cap is enforced, and replay is idempotent.
6. Horizons before enrollment are recorded as `not_observable_before_tracking`.
7. The subject cap is shared, user subjects go first, and deferrals are counted per source.
8. The collector never reads latest-state tables (scan).
9. No update or delete path exists; replay versus conflict behaves as in 0019.
10. No strategy-ID literals (scan).
11. Read models label the source, and the sample guard reports the sources separately.

## 8. Out of scope

Backfill or historical enrollment; stock or unavailable proposals; OI-06 empirical weighting; fills and broker P&L; paid data.
