# STONK-003 — Strategy Manifest Migration

Four production Stonk strategies are represented by canonical ASA Strategy Manifests.
The source behaviors are pinned to Stonk revision
`5f3fec846f70e9739cf3f15695fd587f0604344c`; no legacy runtime path is invoked.

| Manifest ID | Version | Graph ownership |
|---|---:|---|
| `earnings_calendar` | `1.1.0` | confirmed event window, nearest eligible 30-day expiration gap (±5 days), liquidity, coarse volume, calendar debit, score and gated verdict |
| `skew_momentum` | `2.0.0-research` | two-sided historical skew stretch, IV/RV value gates, three-dimensional momentum alignment, delta-selected vertical, liquidity, debit, and verdict |
| `forward_factor` | `1.2.0` | DTE pair, raw front IV, implied forward volatility, confirmed-earnings exclusion, liquidity-complete put/call double calendar, and gated verdict |
| `asa.stonk.stock_momentum` | `1.0.0` | deterministic candidate cap, bounded momentum score and verdict |

Every graph uses exact Component versions from `asa.stonk.shared`,
`asa.stonk.options`, or `asa.core`. Inputs that originate in market-data,
indicator, and canonical-fact layers enter as typed execution context; the manifests do
not acquire or parse them.

Effective thresholds from the pinned legacy defaults are explicit node parameters.
Provider/environment configuration, broker and portfolio state, caches, lifecycle state,
row presentation, and runtime strategy-ID dispatch were not migrated. Forward Factor
remains tagged `dry_run`; this is metadata, not an execution permission.

The manifests serialize through the existing canonical Manifest codec. Their identities,
compiled graph identities, outputs, traces, and replay results are pinned in tests.
Behavioral equivalence against legacy fixtures belongs to STONK-004.
