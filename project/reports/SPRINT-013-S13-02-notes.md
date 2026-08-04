# SPRINT-013 S13-02 — Outcome Vocabulary Fold Notes

`market_data/attempts.py`'s `AcquisitionOutcome` is the 11-value closed vocabulary the sprint defines. The existing `ProviderErrorCode` has 17 values, so 3 groupings are not 1-to-1. Recorded here for review, not silently decided:

| Existing codes | Folded to | Rationale |
|---|---|---|
| `ENTITLEMENT_MISSING`, `AUTHORIZATION_FAILED`, `AUTHENTICATION_FAILED` | `entitlement_unavailable` | All three mean "we lack valid credentialed access to this capability from this provider" — distinct from a transient network problem. |
| `TIMEOUT`, `PROVIDER_UNAVAILABLE`, `TRANSPORT_ERROR`, `CONFIGURATION_ERROR`, `INVALID_REQUEST`, `UNKNOWN_PROVIDER_ERROR` | `transport_failure` | The first three are literal transport-shaped failures. The last three (config/invalid-request/unknown) don't cleanly fit any of the 11 buckets — they're internal-defect-shaped, not data-availability-shaped — and are folded here as the closest available bucket ("we could not successfully complete a request/response cycle with this provider"), rather than adding a 12th value outside the ticket's defined vocabulary. If this masks a real distinction operators need (e.g. `CONFIGURATION_ERROR` should page differently than a genuine timeout), flag it and we'll add a dedicated bucket in a follow-up rather than silently living with the fold. |
| `UNSUPPORTED_CAPABILITY`, `UNSUPPORTED_SYMBOL` | `no_matching_data` | Both mean "this provider has no data offering matching the request," which is exactly what `no_matching_data` already means for `NO_DATA`. |

`fallback_exhausted` is never returned by the per-attempt mapping (`normalize_acquisition_outcome`) — no single attempt's own error code means "every candidate was exhausted." It's a pair-evaluation-level signal, computed by `summary_outcome_for(result)`: `FALLBACK_EXHAUSTED` when `CapabilityFulfillmentResult.status is FulfillmentStatus.FAILED`, `SUCCESS` otherwise. `fulfillment_status` (FULFILLED/DEGRADED/FAILED) is persisted on every attempt record, which is what actually satisfies `fallback_success_and_failure_are_distinct` — DEGRADED means a fallback candidate succeeded, FAILED means fallback was exhausted.

## Diagnostic losslessness (Founder review, added after initial draft)

The aggregate `AcquisitionOutcome` fold above is useful for reporting and dashboards, but folding e.g. `TIMEOUT`/`PROVIDER_UNAVAILABLE`/`TRANSPORT_ERROR`/`CONFIGURATION_ERROR`/`INVALID_REQUEST`/`UNKNOWN_PROVIDER_ERROR` all onto `transport_failure` would erase the specific cause needed for root-cause analysis if that were the only thing persisted. `AcquisitionAttemptRecord` therefore always carries both: `outcome` (the aggregate bucket) and `diagnostic_code` (the original `ProviderErrorCode` it was folded from — still a safe, closed, generic enum, not raw exception text). A record's `__post_init__` enforces that `diagnostic_code` is present iff `outcome is not SUCCESS`, and that it actually folds onto the record's own `outcome` (can't attach a mismatched pair). Nothing is lost; the aggregate is additive, not a replacement.

## Cycle identity (Founder review, added after initial draft)

The original draft derived `screening_cycle_id` from raw wall-clock time alone. Replaced with a deterministic hash of a canonical `(invocation_type, slot_id, scope_id)` tuple:
- `slot_id`: for scheduled runs, the existing `ScheduledRefreshSlot.slot_id` (`market_data/session_schedule.py`) — itself already a deterministic hash of `(session_date, ordinal, scheduled_at)`. For manual/on-demand runs with no schedule slot, `manual_invocation_slot_id(now)` substitutes a UTC-normalized-then-hashed timestamp — never used alone, always as one component of the tuple.
- `scope_id`: `scope_identity(universe)`, an order-independent hash of the (strategy_id, subject) pairs the cycle covers.
- `invocation_type`: caller-supplied (e.g. `"scheduled"` vs `"manual"`), so two overlapping invocations of different kinds over the same slot/scope can never collide.

Same tuple always yields the same `cycle_id` — reprocessing the same due slot (e.g. after a claim-repository retry) is therefore idempotent at the cycle level, which is a deliberate property, not an accident. `pair_evaluation_id` stays a readable composite of `cycle_id:strategy_id:subject_identity` (not hashed) for operator/query readability; `:` is rejected in every component so two distinct pairs can never collide onto the same composite string.
