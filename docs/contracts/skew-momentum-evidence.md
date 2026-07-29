# Skew Momentum canonical evidence

WS5 consumes provider-neutral evidence. Provider payloads, universe selection,
lookback selection, and verdict policy are not part of these contracts.

## Canonical inputs

- `HistoricalSkewObservation` records normalized call and put skew for one
  canonical instrument at one effective time with evidence references.
- `HistoricalSkewObservations` is a deterministic, single-instrument series.
  The caller supplies the approved lookback; the contract does not choose one.
- `CanonicalReturnObservation` records one exact return, its period, effective
  time, canonical instrument, and evidence.
- `ComparisonUniverseReturns` contains an explicit, same-period comparison
  universe. It never infers peers from symbols.
- `SectorReferenceReturns` contains explicit same-period sector members and a
  normalized sector identifier. It never infers sector membership.

All contracts are frozen, immutable, provider-neutral, deterministically
ordered, and provenance-bearing.

## Policy-free derived facts

- historical call and put skew percentile;
- historical call and put skew z-score;
- cross-sectional return percentile;
- sector-relative return versus the equally weighted supplied reference.

Both historical-stretch methods are calculated so the Founder can select the
binding strategy method after reviewing distributions. Neither method is a
PASS/WATCH/FAIL decision.

Capability declarations remain provider-neutral:

- skew history derives from `option_chain_v1`;
- comparison and sector returns derive from `historical_bars_v1`.

The orchestration layer must supply already-selected histories and comparison
members. Strategy adapters must not choose lookbacks, peer universes, sector
members, thresholds, or weights.

## Deterministic distribution vectors

The regression fixture deliberately contains four skew observations:

| Quantity | Current | Distribution result |
|---|---:|---:|
| call skew | 0.18 | percentile 0.75; z-score 0.9838699100999074664200364142417615 |
| put skew | 0.18 | percentile 0.25; z-score -0.8049844718999242907073025207432594 |
| subject return | 0.05 | cross-sectional percentile 0.6666… |
| subject return | 0.07 | sector-relative return 0.02 |

These vectors validate direction and reproducibility only. They do not
establish strategy thresholds.
