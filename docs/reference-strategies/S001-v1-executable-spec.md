# S001 v1 executable specification

`S001@1.0.0` evaluates a point-in-time eligible set of U.S. sector ETFs at a
common finalized month-end decision time. It ranks valid trailing twelve-month
total returns descending with a deterministic canonical-instrument tie-breaker,
selects the first three, then independently requires each selected ETF's
eligible total-return-equivalent observation to be strictly greater than its
ten-completed-month SMA.

The target decision contains exactly three one-third sleeves. A passing sleeve
targets its selected sector ETF. A failing sleeve targets the canonical
three-month-Treasury-total-return research asset. Failed sleeves are never
redistributed. Missing universe, total-return, trend, ranking, defensive, or
temporal evidence is `UNKNOWN`; it is neither an economic loss nor permission
to fabricate a target.

The decision becomes effective no earlier than the next eligible trading
session after all month-end inputs are finalized. It contains no leverage,
short, option, lifecycle, sizing, order, or broker semantics. Its immutable
identity includes strategy version, decision/effective times, eligible universe,
ranked facts, trend facts, targets, and input evidence identities. Replay reads
that sealed evidence only.

## Evidence semantics

S001 requires split-and-dividend-adjusted evidence or another canonical fact
whose contract explicitly represents reinvested total return. Split-only and raw
close series cannot satisfy the strategy. An adapter's provider provenance does
not change this rule. The defensive input is a canonical research fact for
three-month Treasury total return; an ETF, cash return, or raw yield is not an
equivalent substitute.

