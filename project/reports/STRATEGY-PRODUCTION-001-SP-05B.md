# STRATEGY-PRODUCTION-001 — SP-05B

Primary ticket: `SP-05B` — A08 historical option panel and A17 option-return history.

## Outcome

A08 is a provider-neutral immutable panel of exact canonical option contracts,
grouped into chronological point-in-time snapshots. Observation time, ASA fetch
time, source evidence identity, contract identity, panel `as_of`, and panel
identity are preserved. Contracts cannot postdate their snapshot and snapshots
unavailable at `as_of` are rejected, preventing lookahead. Empty authoritative
history remains typed `historical_option_panel_unavailable`; no backfill or
provider is invented.

`HISTORICAL_OPTION_PANEL_V1` is a canonical `OPTION_UNDERLYING` capability:
strict canonical-instrument subject matching, observation content identity, market-data wire round-trip,
snapshot sealing, and provider-free replay use the existing canonical market
observation path. Snapshot identity hashes full observed option content rather
than natural contract identity, so quote, delta, and other observation changes
cannot collide. Exact contracts reuse canonical `OptionCollection` ordering, so
provider tuple order cannot change snapshot or panel identity.

A17 preserves monthly option-return value plus panel and exact-position
lineage. `DF-STRADDLE-MOMENTUM-FORMATION@1.0.0` computes the source-defined
simple mean of complete lags 2–12, skips lag 1, and returns typed
`insufficient_straddle_return_history` when any required month is absent.
Reconstructing from the same sealed observations produces identical panel and
return identities without provider access.
