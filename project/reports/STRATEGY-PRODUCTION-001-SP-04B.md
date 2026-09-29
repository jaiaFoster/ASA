# STRATEGY-PRODUCTION-001 — SP-04B

Primary ticket: `SP-04B` — Santa-Clara/Saretto production strategy.

## Outcome

`index_short_vol_scs_near_atm_straddle@1.0.0` is registered as a provider-blind,
SPX-only production strategy. It enters only on the first eligible trading day
of the month and selects the unique standard monthly expiration closest to 45
calendar days. Equal-distance expirations and equal-distance ATM strikes remain
typed `AMBIGUOUS_SELECTION`; neither is resolved arbitrarily.

The exact same-strike AM-settled SPX call/put pair is projected through shared
P03 as two unit short legs with canonical contract identities. Source quote
filters, IV bounds, and arbitrage bounds fail closed. Missing canonical rate or
SPX dividend-yield evidence remains `G_SCS_QUOTE_FILTERS_UNKNOWN`; allocation is
not invented. Settlement remains lifecycle evidence rather than a fabricated
exit value.

## Research assumption

`RA-SV-01` limits the implementation to standard monthly SPX expirations. The
assumption is identity-bearing in the pinned manifest and disclosed in result
metrics. Changing it requires a strategy semantic-version change.

## Production wiring

The universal registry, subject-preparation registry, catalog, resolution
policy, and fixed-subject scheduler all consume the same manifest and contract.
The strategy contains no provider access, strategy-local acquisition, or
strategy-ID branch in generic runtime code.
