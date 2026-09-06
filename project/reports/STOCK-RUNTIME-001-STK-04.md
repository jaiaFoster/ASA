# STOCK-RUNTIME-001 — STK-04 reuse-gap audit and bounded delta

## Audit summary

ASA already has a substantial, Founder-authorized portfolio subsystem from a
prior sprint (`PORTFOLIO-LIFECYCLE-001`, `docs/sprints/PORTFOLIO-LIFECYCLE-001.yaml`,
PRs #367-#384, all merged to main). Its own Gate 10 (production
verification) is recorded as still open pending separate Founder-authorized
deployment. Auditing against STK-04's desired semantics found:

**Already present, no gap:**
- Multi-account holdings (`PortfolioSnapshot.accounts: tuple[BrokerAccount, ...]`,
  each position carrying its own `account_id`).
- Normalized account type (`individual`, `roth_ira`, `traditional_ira`, ... —
  `asa/integrations/providers/robinhood.py`'s `_BROKERAGE_ACCOUNT_TYPE_MAP`).
- Per-position symbol, quantity, average cost basis.
- A failed broker fetch never masquerades as an empty portfolio: an
  exception anywhere in acquire/normalize/validate/publish always produces
  `RunStatus.FAILED` and preserves the prior successful publication
  (`RunPortfolioIntelligence.execute`, pinned by
  `tests/asa/test_portfolio_acceptance.py`).
- Latest-known-good fallback serving (`serving_last_success`) already
  exists and is already wired through the API.

**Real gaps, addressed by this ticket's bounded delta:**
- Raw Robinhood account numbers were exposed verbatim in the
  `/api/v1/portfolio` API response and in application logs
  (`RunPortfolioIntelligence._log_step`'s `account_id` extra field) — a
  genuine violation of "never expose raw account numbers... in API/UI."
  Internal Postgres persistence of the real value is unchanged (needed for
  cross-run account correlation; it is not an external-facing surface).
- No explicit typed outcome distinguishing SUCCESS / SUCCESS_EMPTY /
  stale-serving-last-known-good, and no *per-account* freshness at all —
  `PublishedPortfolioQuery.current()` only ever produced one freshness
  value for the entire portfolio, even though each `BrokerAccount` already
  carries its own `observed_at`.

**Explicitly not a gap — a different Founder-ratified boundary, flagged
below rather than crossed:**
- Current price, market value, and unrealized P&L (absolute or %) are
  deliberately typed `UNKNOWN` for every position today
  (`asa/application/portfolio_valuation.py`). This is not an oversight:
  `PORTFOLIO-LIFECYCLE-001`'s own governing YAML states
  `duplicate_live_market_data_pipeline: prohibited`, and its reuse-decision
  doc explicitly lists "Live quote acquisition for portfolio rendering"
  under behavior deliberately rejected. See **Blocker** below.

## What was implemented

- `asa/contracts/portfolio.py` — `mask_account_identifier()` (keeps at
  most the last four characters of a broker account identifier),
  `AccountHoldingsStatus` (`SUCCESS` / `SUCCESS_EMPTY` / `STALE_FALLBACK` /
  `STALE`), `AccountHoldingsSummary`, and `account_holdings_status()` — a
  pure derivation from already-known evidence (that account's own
  `observed_at`, whether it currently holds any position, and the
  portfolio-level `serving_last_success` flag), never a new acquisition
  and never fabricated per-account failure isolation the underlying
  single broker-call architecture doesn't actually support (Robinhood
  fetch is one call returning every account at once — a genuinely
  per-account-independent `FAILED` state does not exist prior to any
  first success, at which point there are no accounts to enumerate a
  status for at all; that case remains a portfolio-level 404, unchanged).
- `asa/application/portfolio_use_cases.py` — `PublishedPortfolioQuery.current()`
  now computes one `AccountHoldingsSummary` per account and exposes it via
  a new `PublishedPortfolioView.account_holdings` mapping; `_acquire()`
  masks the account identifier before it ever reaches `_log_step`'s log
  line.
- `asa/api/models.py` — `AccountResponse.external_account_id` is now
  always the masked value; two new fields, `holdings_status` and
  `holdings_as_of`, surface the per-account status and timestamp.
  `PortfolioEnvelope.from_view` now builds each `AccountResponse`
  explicitly (field by field) instead of a blind
  `model_validate(account, from_attributes=True)`, since the response now
  intentionally diverges from the domain object's own raw shape.

## Verification

- `tests/asa/test_portfolio_domain.py` — new tests for
  `mask_account_identifier` (normal and short/exact-length inputs), all
  four `account_holdings_status` branches, and a genuine two-account
  scenario (one funded, one empty) proving `SUCCESS` and `SUCCESS_EMPTY`
  are correctly distinguished per account. 13/13 passed (6 pre-existing +
  7 new).
- `ruff check asa tests/asa` and `mypy asa` (both run exactly as CI's
  `backend` job does): clean.
- Full local regression: `tests/asa/test_portfolio_domain.py`,
  `test_portfolio_valuation.py`, `test_portfolio_structures.py`, and the
  full `tests/architecture/` suite (579 passed; the only failures are the
  pre-existing, unrelated Windows-locale `test_market_data_platform_contract.py`
  encoding issue already documented in STK-03's own report).
  `test_portfolio_acceptance.py` and `test_portfolio_lifecycle.py`
  (Postgres-backed acceptance tests) and `test_robinhood_provider.py`
  could not run locally on this Windows machine (pre-existing, unrelated
  local-environment gaps: no local Postgres/`.env`, and a POSIX-only file
  permission assertion) — unaffected by inspection, since neither test
  asserts on `external_account_id`'s API-response value or constructs
  `PublishedPortfolioView` directly, and `robinhood.py` itself was not
  touched. These will run for real in CI (real Postgres, Linux).

## Blocker — pricing authority requires explicit Founder re-authorization

STK-04's own brief states: *"ASA canonical market-data authority owns
current price where available."* Implementing that — computing real
current price, market value, or unrealized P&L for portfolio positions —
means wiring `market_data`/`strategy_runtime`'s canonical pricing into the
portfolio valuation path. `PORTFOLIO-LIFECYCLE-001` (Founder-ratified,
`AMD-013-PORTFOLIO-LIFECYCLE-001-V1.0`) explicitly prohibits exactly that:
`duplicate_live_market_data_pipeline: prohibited`, with "Live quote
acquisition for portfolio rendering" named as deliberately rejected
behavior when that sprint considered and declined the same idea.

This is a genuine cross-sprint governance conflict, not an implementation
gap — proceeding either way without explicit sign-off risks either
silently violating a standing Founder-ratified invariant, or silently
dropping a semantic STK-04 explicitly asked for. Per STOCK-RUNTIME-001's
own blocker criteria ("scope/governance/risk boundary must expand"),
raising this for an explicit decision rather than choosing unilaterally.

Everything else STK-04 asked for (account-aware holdings, normalized
account type, quantity, average cost, SUCCESS/SUCCESS_EMPTY, latest-known-
good fallback, per-account provenance with a timestamp, and never exposing
raw account numbers) is complete above and does not depend on this
decision.
