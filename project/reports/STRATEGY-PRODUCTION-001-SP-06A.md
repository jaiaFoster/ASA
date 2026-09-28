# STRATEGY-PRODUCTION-001 — SP-06A

Primary ticket: `SP-06A` — P09 generic underlying-exposure overlay.

## Outcome

P09 now represents one canonical economic underlying exposure plus exact option
overlay legs. An `index_total_return` exposure must carry a canonical INDEX
instrument and is explicitly non-broker-executable. A `tradable_underlying`
exposure must be non-index and explicitly executable. The contract therefore
cannot silently turn SPX into SPY, a future, or an orderable index holding.

Overlay identity includes canonical instrument identity, exposure semantics,
quantity, executability, and every exact option leg. Leg ordering is canonical.
Analytical reference value uses the supplied canonical underlying value and
exact option midpoints; absent inputs remain typed UNKNOWN. It performs no
acquisition, proposal construction, or broker action.

A non-BXM tradable-underlying fixture proves the primitive is generic and has
no strategy-ID runtime branch.
