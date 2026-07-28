# ASA Stonk Strategy Library

Version `1.0.0` is ASA's first official extracted Strategy Library. It is an
immutable, deterministically ordered catalog of canonical Strategy Manifests;
it does not dispatch legacy service code.

| Strategy ID | Version | Component dependencies | Purpose |
|---|---:|---|---|
| `earnings_calendar` | `1.1.0` | shared + options | confirmed-event calendar targeting a 30-day gap with liquidity and coarse volume evidence |
| `forward_factor` | `1.2.0` | shared + options | earnings-excluded forward-volatility double-calendar candidate |
| `skew_momentum` | `1.0.0` | shared + options | skew/momentum vertical candidate |
| `asa.stonk.stock_momentum` | `1.0.0` | shared | deterministic equity momentum candidate set |

## Use

```python
from strategies import STONK_STRATEGY_LIBRARY

manifest = STONK_STRATEGY_LIBRARY.get("earnings_calendar")
```

Compile `manifest` with the existing Component Registry and Graph Runtime. The
library performs no execution, provider lookup, portfolio evaluation, dynamic
discovery, or mutation. Its identity is derived from its version and ordered
manifest content identities, so catalog drift is visible and replayable.

Detailed parameters and graph ownership are documented in
`docs/migration/stonk-strategy-manifests.md`; behavioral evidence is in
`docs/migration/stonk-behavioral-equivalence.md`.
