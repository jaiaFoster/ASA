# STRATEGY-PRODUCTION-001 — SP-06B

Primary ticket: `SP-06B` — Cboe BXM production strategy.

## Outcome

`index_buywrite_cboe_bxm@1.0.0` is registered through the universal manifest,
contract, subject-preparation, catalog, cutover, scheduler, and API-active
paths. It reuses the shared SPX quote/next-standard-month chain plan and monthly
roll precedence without provider access in strategy code. X05 option trade
tape, X07 index dividend points, and X01 settlement value are explicit optional
capability demands. When no enabled provider declares one, the generic
fulfillment owner records a typed `unsupported_capability` deferral without a
network call; required-capability misconfiguration still fails closed.

The manifest graph is the financial authority. Registered BXM components read
its reference/VWAP times, contract root, settlement style, expiration offset,
strike operator, and quantities. On the roll date the graph selects the minimum
standard AM-settled SPX call strike at or above the last disseminated SPX value
observed before 11:00 ET. Non-roll dates are `NO_ACTION`; absent/late reference
data, calendar, chain, or qualifying contract remains typed UNKNOWN. Pinned
tests prove changing manifest parameters changes selection and quantities
without editing Python policy.

Passing selection builds generic P09: one analytical, non-broker-executable S&P
500 index total-return exposure plus one exact short call. It never substitutes
SPY or futures and creates no order. X05 entry VWAP, X07 dividend points, and
SOQ evidence are projected from the sealed snapshot when authoritative evidence
exists. Otherwise each remains evidence-derived typed UNKNOWN. X05
uses exact eligible trade prints in its 11:30–13:30 New York window. When an
authoritative exact-contract tape proves no eligible trade, the sourced fallback
is the last exact-contract bid before 13:30 ET. Missing tape or timestamped quote
evidence remains typed UNKNOWN. Dividend and SOQ facts resolve only for the same
SPX instrument and the selected holding/settlement period.

X05 is post-selection acquisition: the manifest-selected exact call identity is
carried by `CapabilityDemand`, projected as the provider's explicit
`option_contract` address, and only that contract's sealed tape can materialize
entry VWAP. The reusable third-Friday roll date is composed before the BXM
binding, carried through immutable planning selections, and materialized as
`DF-THIRD-FRIDAY-ROLL-DATE@1.0.0`; the result adapter no longer owns calendar
interpretation.

`DF-CBOE-BUYWRITE-DAILY-RETURN@1.0.0` implements both the source non-roll
close-to-close formula and the three compounded roll-day segments. Historical
index observations and the provider-neutral historical option panel supply
source-faithful lifecycle inputs. `K_old` comes from the uniquely identified
expiring call, independently of the new selected strike. Exact held-call
identity is carried forward through the generic persisted lifecycle-position
metric and injected at both production composition roots; no expiration-only
inference remains. Prior/current call
closes are the exact contracts' last bid/ask means before 16:00 ET. `S_VWAV`
uses index values at the same timestamps and size weights as eligible call
trades after applying the manifest-owned OPRA exclusion set (A-H and f-t); it
never uses index-bar volume as a proxy. `S_{t-1}` and `S_t` resolve as the latest
valid index observations at/before each New York session close, never by list
position. Missing exact identity, timing, or alignment stays typed UNKNOWN.
Those inputs are projected as canonical facts and the named
return is materialized by the existing derived-fact owner. The live adapter
consumes only that materialized fact or its typed missing-input state.

## Verification

Pinned vectors cover manifest-authority mutation, exact strike/root/settlement
selection, post-selection exact-contract acquisition, verdict precedence,
non-roll and roll return equations, multiple same-expiry strikes with explicit
persisted held identity, intraday bars around explicit session closes,
pre-close quote selection, OPRA exclusions applied identically to call/index
weights, exact trade/index timestamp alignment, no-trade bid fallback, a
non-UNKNOWN materialized daily return,
matching/mismatched tape identity, relevant/irrelevant dividend and SOQ evidence,
P09 identity/executability, generic typed no-provider deferral, production
registry/catalog/scheduler wiring, and existing fixed-subject option orchestration.
