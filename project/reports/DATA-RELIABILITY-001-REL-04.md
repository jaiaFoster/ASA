# DATA-RELIABILITY-001 — REL-04 bounded root-cause corrections

REL-01 enumerated two active, evidenced ASA-owned semantic defects. Both are
corrected at their earliest owners:

1. False freshness (`#436`) — REL-02 now derives current read-time freshness
   from immutable evidence time and market-session semantics. Persistence or
   projection recency cannot make prior-session evidence current.
2. Earnings UNKNOWN presented as clearance (`#437`) — REL-03 preserves the
   frozen Forward Factor signal while independently making execution readiness
   fail closed. Confirmed inside-window evidence is `NOT_CONSTRUCTIBLE`;
   unknown or stale evidence is `UNKNOWN`; only confirmed outside-window
   evidence may resolve exact legs.

Regression coverage includes same-session, weekend, holiday, after-hours and
stale latest-known-good freshness, plus confirmed-outside,
confirmed-inside, unknown/unconfirmed, and production-root provider-failure
earnings states. The production-root regression proves a mathematical signal
can remain evaluated while its executable assessment is explicitly unresolved.

No further software defect was enumerated by REL-01. Provider `NO_DATA` remains
external/unresolved unless authoritative absence is established, and incomplete
diagnostics remain an ASA diagnostic gap rather than being relabeled as
legitimate absence. A current quantitative production remeasurement is deferred
to REL-05's authorized production evidence boundary; this repository is not
linked to the production Railway project and no count is fabricated.

No strategy formula, threshold, provider, acquisition policy, market-data
authority, broker behavior, or fallback changed.
