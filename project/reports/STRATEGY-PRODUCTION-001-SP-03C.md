# STRATEGY-PRODUCTION-001 — SP-03C

Primary ticket: `SP-03C` — Cboe PUTY reuse strategy.

## Outcome

`index_putwrite_cboe_puty@1.0.0` is registered on fixed subject `SPX` through
the same provider-blind subject-first acquisition, knowledge, P01 resolution,
cash-collateral, API, tracking, and outcome stack as Cboe PUT. The economic
difference is manifest policy: select the highest standard AM-settled
next-month SPX put strike strictly below `0.98 × S_ref`.

Equality does not pass the strict source rule and remains typed
`G_PUTY_STRIKE_EXISTS_UNKNOWN` when no lower eligible strike exists. PUTY adds
no provider, formula, structure primitive, or generic strategy-ID branch.
X05 entry VWAP, Treasury sizing, and SOQ lifecycle inputs retain the explicit
typed UNKNOWN treatment established by PUT; no quote or data proxy is used.

## Verification

- PUT/PUTY truth tables and equality boundary: green.
- Registry, subject-first binding, fixed-subject scheduler, API/catalog, and
  acquisition-blindness regressions: green.
- Manifest semantic pin: `ee78c71289f1b431655c53b3fa0d5055ede6a392b7108924676f37960905d2aa`.
