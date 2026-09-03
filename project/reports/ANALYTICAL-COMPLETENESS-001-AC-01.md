# ANALYTICAL-COMPLETENESS-001 — AC-01 active-universe reconciliation

Captured at `2026-09-03T19:20:00.326157Z` against production
`1fe9dae2cc29ccddeeaa29d18b0322691fb60b7f`.

## Authorities and counts

The effective-dated `sp500` membership snapshot dated `2026-08-13` is the
current membership authority. It contains 503 symbols, therefore three active
production strategies produce 1,509 canonical active identities.

| Set | Count | SHA-256 |
|---|---:|---|
| canonical active identities | 1,509 | `8c97453675f859e2012528feeb4864cef25364e4f93d6fa1cdd80e236ee2f771` |
| persisted identities | 1,525 | `979a09c52b51811058a4dfd3f6a891a3112497fc5c236f63efb526ca900c9feb` |
| active intersection | 1,509 | `8c97453675f859e2012528feeb4864cef25364e4f93d6fa1cdd80e236ee2f771` |

Persistence contains all 1,509 active identities. Counts by strategy are 503
active identities each. Persisted counts are 503 Earnings Calendar, 511
Forward Factor, and 511 Skew Momentum.

## Retained non-active evidence

The 16 retained identities are Forward Factor and Skew Momentum rows for each
of `DIA`, `GLD`, `IWM`, `QQQ`, `SPY`, `XLE`, `XLF`, and `XLK`. These symbols
are the eight ETF members of the earlier bounded production universe declared
in `screening/live_acquisition.py`; they are not members of the effective-dated
S&P 500 snapshot. They are retained latest results, not active membership and
not corrupt rows.

No deletion or historical rewrite is required. Exact result reads continue to
support retained rows.

## Generic projection rule

The canonical membership symbol set is injected at the production composition
root. The generic screening surface can project `active_universe` without any
strategy-ID branch, while its existing default `all_latest` behavior remains
compatible. Envelopes state their scope and retained non-active count. Strategy
health and the Intelligence Console use active membership for current totals
and report retained rows separately.

This makes membership an input from the canonical universe owner; the latest
result repository remains storage authority and learns no universe semantics.
