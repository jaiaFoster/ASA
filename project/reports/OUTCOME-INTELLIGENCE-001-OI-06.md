# OUTCOME-INTELLIGENCE-001 — OI-06 Transparent Prioritization

- **Ticket:** OI-06 (Founder Sprint Delegation, `implementation-worker`)
- **Risk:** R1 (read-only UI ordering/filtering; no backend, contract, or schema change)
- **Status:** implementation-complete (sorting/filtering shipped; empirical weighting deferred by the sprint's own sparse-volume rule)

## Volume check (why no empirical weighting)

Production at `d52146f` on 2026-09-25 (read-only `GET /api/v1/screening?active_only=true`):
- **1,512** active latest-state rows;
- **6** qualifying (`evaluation_state = pass`) rows:
  - `spy_put_credit_spread/SPY`
  - `B001/SPY`
  - `earnings_calendar/{CI, PSX, VLO}`
  - `forward_factor/GOOG`
- **3** of those carry a complete proposal.

The forward-outcome corpus is **n = 0** in production. The ledger ships with #493, which awaits the Founder merge.

The sprint says: "If volume is still sparse, ship sorting/filtering and defer empirical weighting." Volume is sparse, so that is what shipped.

## What shipped

`#/opportunities` view (`asa/ui/static/prioritize.js`, `opportunitiesView` in `render.js`):

- **Scope:** lists only qualifying rows. It joins each row to its option trade proposal or stock proposal, loaded read-only from the existing endpoints. A missing proposal is shown as "qualifying signal, no complete proposal" and is never guessed.
- **Ordering:** lexicographic over displayed keys, in this order. Every key is shown on its row.
  1. actionability (complete proposal first);
  2. evidence trusted (usable and live/fresh first);
  3. evidence age (newest `observed_at` first);
  4. deterministic tie-break on strategy, then symbol.
- **No numeric score, and no strategy-quality ranking.** Strategy identity enters only as the alphabetical tie-break.
- **Filters:** asset class, strategy, complete proposals only, stated maximum loss only (defined risk). Maximum loss and liquidity are displayed but not used as sort keys. That avoids an implicit cross-asset ranking: stocks state no maximum loss.
- **Forward-outcome sample guard:**
  - per-strategy tracked count and `n` with modeled P&L, with `MINIMUM_OUTCOME_SAMPLE = 30`;
  - below the guard it reads "not used in ordering";
  - at or above it, this version still reads "not used in ordering (weighting not implemented)";
  - absent data or an error is shown explicitly and never treated as zero.

## Validation

- **ui-tests: 22/22.** Two new tests:
  - key order, input-order independence, and each filter;
  - the guard text, explicit n=0, and a rendered table row carrying its keys.
- **`tests/asa/test_ui_routes.py`: 11 passed.** `prioritize.js` is added to the packaged-asset check and to the strategy-ID scan.
- **Live read-only render** of the local UI against production data (Chromium; API calls proxied with the agent token). It listed the 6 qualifying rows in this order:
  1. PCS/SPY (complete, max loss 3540.50);
  2. B001/SPY (complete);
  3. earnings_calendar/CI (complete, 515.00);
  4. forward_factor/GOOG, earnings_calendar/VLO, earnings_calendar/PSX (no complete proposal).

  The outcome panel showed the production 404 truthfully, because the endpoint arrives with #493.

## Deferred (explicit)

Empirical weighting from forward outcomes is deferred until a strategy's observed sample reaches the guard. Even then it needs a separate reviewed design. Portfolio fit is not used, because there is no trustworthy per-proposal portfolio-fit quantity today.
