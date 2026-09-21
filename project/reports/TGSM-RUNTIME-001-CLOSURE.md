# TGSM-RUNTIME-001 closure

Status: CLOSED / MERGED-MAIN PASS.

Implementation verification SHA: `104c075da61a4b8a5a3bac8f794e967a93890dae`.
The subsequent closure-record merge changes documentation/status only; GitHub
is the operational source for that final merge identity.

## Delivered semantics

- Strategy: `S001@1.0.0`, Trend-Gated Sector Momentum.
- Universe: effective-dated Select Sector SPDR membership; members are excluded
  before inception. State Street membership/inception references are preserved.
- Evidence: completed-month split-and-dividend-adjusted closes only. Raw and
  split-only evidence fail closed.
- Derived facts: `trailing_12m_total_return@1.0.0` over thirteen completed
  month ends and reused `sma_10m_completed_months@1.0.0`.
- Ranking: descending, common effective time, canonical-instrument tie break;
  unknown subjects are not economically ranked.
- Trend: latest eligible completed-month total-return-equivalent observation
  strictly greater than SMA10M; equality fails; unavailable evidence is UNKNOWN.
- Selection: rank first, take top three, then independently trend-test each.
- Target: three exact rational `1/3` sleeves. A failed selected sleeve alone
  targets `research_asset:us_3_month_treasury_total_return`; other sleeves are
  not redistributed. Defensive substitution requires canonical total-return
  fact evidence and accepts no ETF/cash/yield proxy.
- Temporal rule: decision uses finalized evidence; effective time is injected
  by the trading-session authority and must be strictly later.
- Identity/replay: immutable decision identity covers strategy version,
  decision/effective times, universe, ranking, exact targets/weights, trend
  states, and material fact identities. Canonical serialization, an append-only
  ledger, and provider-free replay reject tampering and identity collision.

## Architecture and reuse

The final implementation follows the S001-01 REUSE/EXTEND/NEW matrix. Existing
owners remain authoritative for effective universe membership, historical
market evidence, canonical facts, analytics registration/materialization,
universal strategy registration/execution, and injected clocks. The only
generic additions are deterministic cross-sectional ranking, immutable sealed
cohort composition, and an append-only decision ledger. S001 owns only its
interpretation and target policy.

There is no strategy-ID branch in generic runtime, no duplicate market-data
authority, no strategy provider access, no option resolver, no lifecycle,
no broker call or mutation, no order, no leverage/shorting, and no silent
fallback. B001/B002 and existing option strategies are unchanged.

## Verification

- Merged gates: PRs #428–#433 (S001-01 through S001-05).
- S001-06 candidate adds the integrated universal-runtime → target-decision →
  ledger → canonical serialization → provider-free replay regression.
- Full Python suite on exact merged main `104c075d`: **3,403 passed, 48 skipped**.
- Architecture and focused TGSM regression: green.
- Frontend: 7 tests passed; lint, typecheck, and production build green.
- Legacy UI: 14 tests passed; JavaScript syntax/lint green.
- Lean pre-push, governance integrity, entrypoints, and diff checks: green.
- Changed-scope Ruff and mypy: green. Repository-wide Ruff/mypy retain known
  pre-existing failures outside this sprint and were not weakened or repaired.

## Known external limitations and deferred work

Production evaluation depends on a provider source that truthfully supplies
split-and-dividend-adjusted history and on an authorized canonical source for
three-month Treasury total return. Missing source evidence remains typed
UNKNOWN; the runtime never substitutes raw close, BIL, cash, or yield. No
deployment is authorized by this sprint. Broad empirical validation,
optimization, ablations, costs, and investment-performance conclusions remain
TGSM-RESEARCH-001 work.

## Recovery

All additions are additive. Reversion removes S001 registration/bindings,
ranking/cohort integration, and decision-ledger records without altering the
existing production strategy, provider, portfolio, or broker paths.
