# Opportunity history

Lifecycle-capable screening results are appended after their latest-state upsert. History is
separate, additive evidence: an append failure is logged with safe identifiers and never rolls
back or corrupts the canonical latest result.

`GET /api/v1/screening/opportunities/{opportunity_id}/history` returns one opportunity only,
oldest first, with bounded `limit`/`offset` pagination. Reads never call market-data providers.

An exact duplicate—same opportunity, signal, symbol, stage, verdict, action, and timestamp—is a
no-op. A later refresh with a different timestamp remains a new observation even when its stage
and verdict are unchanged. Screening records `no_action`; it observes analytical lifecycle state
but does not create an execution recommendation.
