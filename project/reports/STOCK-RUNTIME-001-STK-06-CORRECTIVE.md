# STOCK-RUNTIME-001 — STK-06 continuation

## Reuse-gap audit

The existing portfolio valuation owner already combined broker quantity/cost basis with a
read-only canonical quote. It lacked input lineage, computation identity/time, percentage P&L,
and any holdings rendering in the Stocks product surface. The existing Railway ten-minute cron
ran screening and B001/B002 but never refreshed the portfolio; portfolio publication was manual.

The corrective delta keeps those owners. It adds immutable lineage references to the valuation
contract, projects them additively through `/api/v1/positions`, renders holdings with one generic
fact inspector, and invokes the existing broker runner from the existing production cron. It adds
no provider, quote acquisition path, scheduler, broker operation, or account identifier exposure.

## B002 causality

The B002 demand declared only raw `close` completeness. Provider selection could therefore accept
a raw-only historical series, after which the derived-fact owner correctly rejected it as
`insufficient_adjusted_history`. This was an ASA request-contract defect, not proof of upstream
absence. B002 now requests `adjusted_close`; provider completeness requires both adjusted value and
typed adjustment basis. Raw OHLC remains backward compatible and is never substituted. If no
enabled/entitled provider supplies that evidence, the resulting typed missing data is then a
truthful external limitation.

## Preserved boundaries

- Broker: account identity/type, quantity, and average cost.
- Canonical market data: current security price and its provider/acquisition provenance.
- Portfolio projection: versioned derived market value and unrealized P&L formulas.
- Scheduling: existing external Railway ten-minute cron; no in-process scheduler.
- Safety: read-only broker surface; no orders, sizing, lifecycle, or strategy-policy changes.

