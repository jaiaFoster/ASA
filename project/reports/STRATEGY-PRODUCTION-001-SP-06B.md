# STRATEGY-PRODUCTION-001 — SP-06B

Primary ticket: `SP-06B` — Cboe BXM production strategy.

## Outcome

`index_buywrite_cboe_bxm@1.0.0` is registered through the universal manifest,
contract, subject-preparation, catalog, cutover, scheduler, and API-active
paths. It reuses the shared SPX quote/next-standard-month chain plan and monthly
roll precedence without provider access in strategy code.

On the roll date, BXM selects the minimum standard AM-settled SPX call strike
at or above the last disseminated SPX value observed before 11:00 ET. Non-roll
dates are `NO_ACTION`; absent/late reference data, calendar, chain, or qualifying
contract remains typed UNKNOWN.

Passing selection builds generic P09: one analytical, non-broker-executable S&P
500 index total-return exposure plus one exact short call. It never substitutes
SPY or futures and creates no order. X05 entry VWAP, X07 dividend points, and
SOQ outcome accounting remain explicitly typed UNKNOWN until authoritative
evidence is materialized; they do not silently change proposal selection.

## Verification

Pinned vectors cover exact strike/root/settlement selection, verdict precedence,
P09 identity/executability, production registry/catalog/scheduler wiring, and
existing fixed-subject option orchestration.
