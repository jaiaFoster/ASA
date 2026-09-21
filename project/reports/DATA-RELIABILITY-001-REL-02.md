# DATA-RELIABILITY-001 — REL-02 freshness correctness

Root cause: screening-result freshness was stored as a point-in-time decision
and later reused unchanged by API filtering and projection. `age_seconds` came
from persisted temporal metadata, while `freshness_status`/usability could still
say live/usable. A Friday result could therefore be read or reprojected Monday
with a small stored age and pass the public `fresh` filter.

Correction: `strategy_runtime.result_freshness` projects read-time freshness
from immutable evidence `observed_at` plus the economic market-session date.
Persistence time remains an audit field only. A row is display-fresh only when
its evidence belongs to the current local trading session and its stored source
quality was fresh/live/delayed and usable. The public API response and freshness
filter use the same projection.

Pinned regressions cover same-session refresh, Friday-to-Monday carryover, a
holiday, same-session after-hours persistence, and latest-known-good stale
evidence. Stored results are not rewritten; replay/provenance remain intact.
