# OPTIONS-PRODUCT-001 — OP-07 Founder-utility observation

Production SHA observed: `d6d4c8d65ea45655a8a893b7ab0fa2df10328663` (OP-01 through OP-06 merged; verified via `/api/v1/version`)
Captured: `2026-09-24T16:24:32Z` during the regular US equity session
Operational issue: [#480](https://github.com/jaiaFoster/ASA/issues/480)  
Artifact: [`OPTIONS-PRODUCT-001-OP-07.json`](OPTIONS-PRODUCT-001-OP-07.json)

## Method

`tools/options_product/founder_utility.py` pins the deployed SHA. It pages every
active result for every registered signal and sends each qualifying
(`PASS`/`WATCH`) option result through the same read-only surfaces the
Intelligence Console renders: option funnel, canonical trade proposal, and
deterministic terminal payoff. It checks each result against the program's
options "done" contract: exact legs, buy/sell, call/put, strike, expiration,
quantity, quotes or truthful absence, modeled entry, typed quantity states,
evidence identity, rationale, and risk/invalidation notes. A qualifying result
that cannot render a card at all is a path defect.

A deterministic replay test (`tests/tools/test_founder_utility.py`) runs the
same collector through the real FastAPI application. The fixtures are a
constructible vertical, a constructible calendar, a nonconstructible calendar,
a non-qualifying row, and a stock benchmark.

## Real current results

| Signal | Symbol | Outcome | Detail |
|---|---|---|---|
| earnings_calendar | GILD, ICE, PCG, PPG, PSX | complete_trade_card | exact 2-leg calendar; terminal payoff truthfully refused: `MULTIPLE_EXPIRATIONS_REQUIRE_MODEL_DEPENDENT_VALUE` |
| earnings_calendar | VLO | typed_failure_presentation | `no_compatible_contract` / `contract_selection` |
| forward_factor | GOOG, SWKS | typed_failure_presentation | `earnings_clearance:unknown_unconfirmed` / `earnings_uncertainty` |

8 qualifying option results: 5 complete trade cards, 3 typed failures, 0
defects. Verdict: `complete_trade_card_path_observed`.

The production Intelligence Console was also rendered headlessly, read-only,
on the same SHA:

- `#/results/earnings_calendar/PSX` shows "Proposed trade · analytical, not an
  order": SELL 1 CALL 2026-10-02 strike 260 (bid/ask/mid 7 / 8.4 / 7.7), BUY 1
  CALL 2026-10-30 strike 260 (14.2 / 17.2 / 15.7), modeled entry 8.0
  (midpoint-v1), constructible_as_intended, liquidity acceptable, Track This
  with the no-order/no-fill disclosure, expandable rationale, and evidence
  snapshot.
- `#/results/forward_factor/GOOG` shows "Signal ≠ executable trade": verdict
  WATCH (unchanged), readiness unknown, category `earnings_uncertainty`, and
  exact blocker `earnings_clearance:unknown_unconfirmed`.

## Acceptance

A user can open an actionable option result and read the exact intended trade
without another analytical application: **observed on real results**.
Uncertainty is explicit, and nonconstructible signals are never shown as
executable.

## Usability finding → bounded correction OP-07-C1 ([#481](https://github.com/jaiaFoster/ASA/issues/481))

Every actionable card observed today is a same-strike long calendar. On all of
them, capital required, maximum loss, maximum profit, and breakeven render
`unknown` (`payoff_model_not_attached`), and no payoff diagram appears. This
is truthful, but for a same-strike, same-type debit calendar the maximum loss
at front expiration is bounded by the modeled net debit: the long back option
is American and worth at least its intrinsic value. That bound is
model-independent and belongs in the canonical payoff layer, not the UI.
Maximum profit and breakeven remain model-dependent and must stay non-supported.

This is an in-scope OP-02/OP-04 usability correction, not a signal or path
defect. It proceeds in parallel under the program's transition rule.

## Sprint state

`OPTIONS-PRODUCT-001`: path observation **passed**; bounded usability
correction OP-07-C1 open. The sprint closes when OP-07-C1 merges.
`STOCK-PRODUCT-001` begins now, because the options trade-card path is merged
and usable.
