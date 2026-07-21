# STONK-003 — Strategy Manifest Migration

Four production Stonk strategies are represented by canonical ASA Strategy Manifests.
The source behaviors are pinned to Stonk revision
`5f3fec846f70e9739cf3f15695fd587f0604344c`; no legacy runtime path is invoked.

| Manifest ID | Version | Graph ownership |
|---|---:|---|
| `asa.stonk.earnings_calendar` | `1.0.0` | confirmed event window, expiration pair, nearest common strike calendar, debit, bounded score and verdict |
| `asa.stonk.skew_momentum_vertical` | `1.0.0` | delta-selected vertical, observed leg liquidity, debit, bounded score and verdict |
| `asa.stonk.forward_factor_calendar` | `1.0.0` | DTE pair, source-qualified forward factor, put/call double calendar and verdict |
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
