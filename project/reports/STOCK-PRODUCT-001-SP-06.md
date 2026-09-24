# STOCK-PRODUCT-001 — SP-06 observation and sprint state

State: `OBSERVATION_PASS` → `CLOSED`
Production SHA observed: `df000e97cebbe161ae580d85f72a715f6a0541e7` (#485; verified via `/api/v1/version`)
Captured: `2026-09-24T17:05:34Z`, regular US equity session
Artifact: [`STOCK-PRODUCT-001-SP-06.json`](STOCK-PRODUCT-001-SP-06.json)

## Method

`tools/stock_product/stock_observation.py` pins the deployed SHA. It selects
every strategy whose declared structure is `none` from `/capabilities`, pages
its active results, and fetches each stock proposal. It checks each proposal
against the program's stock "done" contract: instrument, strategy,
action or typed absence, evidence time and freshness, allocation or typed
absence, typed unknown reasons, rationale, and invalidation. It is read-only.
A replay test runs the same collector through the real application.

## Result

| Strategy | Instrument | Status | Action | Evidence | Unknown reason |
|---|---|---|---|---|---|
| B001@1.0.0 | SPY | actionable | BUY | fresh, 161 s | — |
| B002@1.0.0 | SPY | unknown | none (`evaluation_incomplete`) | fresh, 162 s | `unusable_historical_bars` |

Zero defects. Verdict: `actionable_stock_path_observed`.

The production Intelligence Console was also rendered headlessly, read-only:

- Stocks → Stock strategies now lists B001/SPY and B002/SPY. Before #485 it
  reported "No persisted stock-benchmark results yet".
- `#/results/B001/SPY` shows the stock card: "SPY · BUY", strategy
  B001@1.0.0, freshness, "Allocation none (not_defined_by_strategy)", price,
  rationale, invalidation, snapshot provenance, and the no-sizing/no-returns
  disclosure.

## Acceptance

At least one options strategy (Earnings Calendar; OPTIONS-PRODUCT-001 OP-07)
and one stock/ETF strategy (B001) traverse end-to-end user-facing paths from
shared evidence to an understandable current proposal. There is no broker
mutation and no false economic claim.

B002's typed unknown is the documented external adjusted-close entitlement
limit (STOCK-RUNTIME-001 STK-01). It is not an ASA defect, and procurement is
not escalated: B002 remains truthfully unknown, and the product path is
proven by B001.

## Transition

STOCK-PRODUCT-001 is closed. Under the program transition rule,
STRATEGY-LIBRARY-001 may begin now: one options strategy and one stock
strategy traverse their full user-facing path.
