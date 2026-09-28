# STRATEGY-PRODUCTION-001 — SP-05A

Primary ticket: `SP-05A` — generic P10/P12 portfolio structures.

## Outcome

P10 is an immutable exact option leg plus a static signed underlying hedge.
The hedge delegates to the registered `DF-DELTA-NEUTRAL-HEDGE-QUANTITY@1.0.0`
formula and preserves exact option-leg identity; missing delta remains typed
UNKNOWN.

P12 is a point-in-time cross-sectional portfolio over arbitrary immutable
position identities. It delegates ranking and ties to
`DF-XS-QUANTILE-ASSIGNMENT@1.1.0` / `RA-XS-01`, excludes UNKNOWN inputs rather
than treating them as losses, and supports either equal weights or normalized
source-defined value weights. Evidence time, evidence identity, quantile
policy, exact member positions, quantiles, and weights all participate in the
deterministic portfolio identity.

Generic fixtures prove the same P12 owner accepts P10 Zhan positions and P03
Heston positions. No strategy ID, provider, acquisition, or private financial
formula is present in the generic owner.
