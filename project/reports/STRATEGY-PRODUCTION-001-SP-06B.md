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
uses the registered `windowed_option_trade_vwap@1.0.0` formula and never a quote
midpoint or last-trade substitute. Its 11:30–13:30 window is explicitly New
York time, and a tape resolves entry price only when its exact contract identity
matches the selected short call. Dividend and SOQ facts resolve only for the
same SPX instrument and the selected holding/settlement period.

`DF-CBOE-BUYWRITE-DAILY-RETURN@1.0.0` implements both the source non-roll
close-to-close formula and the three compounded roll-day segments. The live
adapter consumes that named formula. Until the sealed evidence boundary also
contains prior close/call marks and S_VWAV, the return remains the explicit
typed `missing_cboe_buywrite_daily_return_input`; a raw dividend observation is
not reported as completed BXM return accounting.

## Verification

Pinned vectors cover manifest-authority mutation, exact strike/root/settlement
selection, verdict precedence, non-roll and roll return equations, typed missing
return inputs, P09 identity/executability, optional lifecycle-capability planning,
generic typed no-provider deferral, production registry/catalog/scheduler wiring,
and existing fixed-subject option orchestration.
