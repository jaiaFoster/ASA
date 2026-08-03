# Skew Momentum canonical evidence

WS5 consumes provider-neutral evidence. Provider payloads and universe
acquisition are not part of these contracts.

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
members. Strategy adapters must not choose peer universes or sector members.

## Research policy v2

The canonical manifest pins `2.0.1-research`. Historical stretch uses a
60-observation z-score window with at least 40 valid observations and requires
`z <= -2.0`. The ATM leg must be fair or cheap to realized volatility
(`ATM IV - RV <= 0`); the wing must be rich to both realized volatility and
ATM IV (`wing IV - RV > 0` and `wing IV - ATM IV > 0`).

Momentum uses a 20-session return, same-instrument-class cross-sectional
percentile from at least five configured screening-universe peers, and
GICS-sector-relative return against the Select Sector SPDR benchmark. Each
dimension has equal weight. Bullish alignment is respectively `> 0`, `>= 0.70`,
and `> 0`; bearish alignment is `< 0`, `<= 0.30`, and `< 0`. Two of three
dimensions are required for PASS.

Core-gate failure or absence of any explicitly true directional core gate is
FAIL. Passing core gates with conflicting or incomplete
momentum is WATCH. If both directional branches qualify, the result is WATCH.
Missing evidence is UNKNOWN and never replaced by a proxy. Unsupported ETFs and
missing-sector subjects therefore keep sector-relative evidence UNKNOWN.

The current live adapter computes available option-chain, volatility, and
20-session return facts. Until canonical history and configured-universe
orchestration supplies z-scores, peer percentiles, and sector-relative returns,
those inputs remain UNKNOWN; the adapter does not infer or fabricate them.

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
