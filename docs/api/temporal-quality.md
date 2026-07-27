# Temporal quality contract

Screening responses preserve existing fields and also expose the timing and
quality of the evidence used to compute the result.

- `observed_at` is the newest source-effective time in the input snapshot.
- `received_at` is the latest provider-recorded receipt time.
- `evaluated_at` is when ASA evaluated the signal.
- `persisted_at` is when ASA prepared the canonical latest-state write.
- `market_session_date` and `market_session_status` use
  `America/New_York` exchange semantics.
- `freshness_status` is one of `live`, `delayed`, `prior_session`, `stale`,
  `unknown`, or `unavailable`.
- `usability_status` is `usable`, `usable_with_warning`, or `rejected`;
  `usability_reason` and `warning_codes` explain the decision.
- `input_time_skew_seconds` exposes the material time span among inputs.

Refresh responses additionally distinguish `provider_contacted`,
`data_advanced_on_last_refresh`, `result_changed`, and `refresh_failed`.
When a refresh fails after a prior successful write, ASA returns the persisted
last-known-good result with `refresh_failed: true`; the failure never erases it.

`next_refresh_at` is nullable until the session-relative scheduling policy has
selected the next eligible run.

Latest-state writes are monotonic by source `observed_at`. A late older
observation cannot replace newer data. Equal source times use observation
identity as a stable tie-breaker; append-only lifecycle history remains
independent and replayable.

The external scheduler invokes one-shot `python -m asa.scheduled_screening`
deliveries. ASA admits only the latest slot within a 20-minute catch-up window
and stores one PostgreSQL claim per slot, so duplicate cron delivery executes
once and restart never replays every missed slot. Normal sessions run at
open+10m, 11:00, 13:00, 15:00, and close-10m New York time. Early-close slots
are open+10m, one-third, two-thirds, and close-10m. Weekends and full holidays
have no provider cycle. On-demand refresh has a persisted 10-minute cooldown;
failure retry delays are bounded at 5, 15, then 30 minutes.
