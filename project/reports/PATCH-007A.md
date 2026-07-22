# PATCH-007A — Tradier Expiration-Aware Option-Chain Acquisition

Status: Implementation complete, **founder_verification_pending**. Per this patch's own
`docs/sprints/PATCH-007A.yaml` (Founder Sprint Delegation, GOV-AMD-001-013 / GOV-007A, #158),
Founder verification is requested before this patch is treated as closed.

Validation time (UTC): 2026-07-22 (code); live validation 2026-07-22T21:00–21:08 UTC
Repository commit (pre-merge): `4b39176` (`main`, through PR #161)

## 1. Root cause

`screening/live_adapters.py`'s live adapters (LIVE-002) assumed one `OPTION_CHAIN_V1`
request returns contracts for every expiration at once -- true for the offline
`deterministic_fixture` provider, false for real Tradier, whose real endpoint
(`market_data/tradier.py:253`) requires a specific `expiration` query value per request,
looked up via `subject.projection_for("tradier", "expiration", ...)`.
`screening/live_context.py::build_capability_subject()` never attached that projection, so
every real live option-chain acquisition raised `DomainInvariantError: MarketDataSubject
requires one effective provider projection` -- discovered during SPRINT-007's LIVE-003 live
validation (`project/reports/SPRINT-007.md` section 7) and filed as
[#156](https://github.com/jaiaFoster/ASA/issues/156).

## 2. Implementation summary

Four tickets, each a self-contained, independently-tested layer:

- **TRADIER-PATCH-001** (`screening/live_context.py::acquire_expirations()`): canonical
  expiration discovery, normalizing two legitimate provider response shapes (Tradier's
  real per-expiration-observation shape; a fixture's single-chain-covers-everything shape)
  into one deterministic `tuple[ExpirationCycle, ...]`.
- **TRADIER-PATCH-002** (`build_capability_subject(..., expiration=...)`): attaches an
  explicit `"expiration"`-address-type `ProviderAddressProjection` per known provider,
  separate from the existing `"symbol"` projection -- proven end to end against the real,
  unmodified `TradierProvider` class with a fake transport.
- **TRADIER-PATCH-003** (`screening/live_adapters.py` + `combine_option_chains()`):
  rewires all three live adapters into a two-step flow -- discover expirations, select via
  the same canonical DTE-policy functions already used, acquire one chain per selected
  expiration, combine into one chain for strategies needing two (Forward Factor, Earnings
  Calendar).
- **TRADIER-PATCH-004** (`classify_domain_invariant_error()`): splits the single, ambiguous
  `DomainInvariantError` catch in `_acquire_or_raise()`/`acquire_expirations()` into two
  distinct, accurately-labeled outcomes -- "no enabled provider declares or satisfies this
  capability" versus "a provider was selected, but the canonical request subject was
  incomplete or invalid" -- plus a third, pre-existing category ("a valid request could not
  be completed or normalized") for genuine post-selection acquisition failures. Then
  validated the complete repaired path with real Tradier credentials.

## 3. Files changed

- `screening/live_context.py`: `acquire_expirations()`, `combine_option_chains()`,
  `classify_domain_invariant_error()`, `build_capability_subject()` extended with
  `required_fields`/`expiration` overrides.
- `screening/live_adapters.py`: `_acquire_or_raise()` extended with `expiration` parameter
  and narrowed exception handling; new `_acquire_combined_chain()`; all three
  `build_live_*_adapter()` factories rewired to the two-step flow.
- `tests/screening/test_live_context_expirations.py`,
  `test_live_context_expiration_aware_subjects.py`,
  `test_live_context_error_classification.py` (new); `test_live_adapters.py` (extended with
  a `TradierShapedMultiExpirationProvider` double and end-to-end classification tests).
- No changes to `market_data/tradier.py`, `strategies/`, `screening/adapters.py`
  (fixture-backed path), `analytics/`, governance, or workflow files, per this patch's own
  `must_not_modify`/`explicit_exclusions`.

## 4. Regression results

- `pytest tests/` (full repository): **2201 passed, 2 skipped** (pre-existing, unrelated).
- `pytest tests/screening/ tests/architecture/`: all green throughout every ticket.
- `ruff check screening/ tests/screening/`: clean throughout every ticket.
- `mypy screening/live_context.py screening/live_adapters.py screening/live_acquisition.py
  screening/cli.py`: zero errors attributed to this patch's own files.
- `tools/pos/lean/check_integrity.py` / `check_entrypoints.py` / `pre_push_check.py`: all
  green throughout every ticket.
- All 7 of LIVE-002's original fixture-backed tests (`MultiExpirationFixtureProvider`,
  which -- like the offline fixture -- ignores requested expirations and always returns
  everything at once) pass unchanged after the two-step rewrite, confirmed by
  `combine_option_chains()`'s contract deduplication -- proves fixture-backed behavior was
  preserved, not just that the new code compiles.

## 5. Live validation

Executed via `railway run -- python -m screening --live --universe
AAPL,MSFT,NVDA,AMD,SPY,QQQ --json` against Railway's `ASA` production service, real Tradier
credentials injected directly into the subprocess environment -- no credential value was
ever read, printed, or handled by the implementing agent at any point across this patch's
live validation.

**Acceptance criteria evidence:**

- **The previous missing-expiration-projection error is not reproduced.** Confirmed --
  zero occurrences of `"MarketDataSubject requires one effective provider projection"`
  anywhere in the full 18-result CLI run or either targeted diagnostic below.
- **Tradier receives real expiration-list and expiration-specific option-chain requests.**
  Confirmed directly (a targeted diagnostic script wrapping the injected transport to log
  request paths/queries and response status/contract-counts, never credential values):
  - `GET /v1/markets/options/expirations?includeAllRoots=false&symbol=AAPL` -> `200`,
    24 real expirations returned, correctly normalized by `acquire_expirations()`.
  - `GET /v1/markets/options/chains?expiration=2026-08-21&greeks=true&symbol=AAPL` -> `200`,
    **178 real contracts returned** -- the exact expiration selected by
    `acquire_expirations()`'s output was the exact expiration Tradier's real endpoint
    received, definitively proving #156's root cause is fixed.
- **Results do not falsely report "no provider offers the capability" when a provider was
  selected.** Confirmed -- the full CLI run's 18 results use only the new, accurate
  `"could not be completed or normalized"` (`provider_acquisition_failure`) message class;
  zero occurrences of the old, misleading `"no enabled live provider offers"` text.
- **Forward Factor and Skew Momentum reach a valid strategy evaluation outcome (PASS,
  NO_SIGNAL, or a genuine data-quality failure).** Reached a genuine data-quality failure,
  not the previous structural bug: this validation ran ~65 minutes after the 2026-07-22 US
  market close, and real-time quote/option-chain freshness checks (`market_data/tradier.py`'s
  own effective-time computation, pre-existing and unrelated to this patch) rejected the
  otherwise-valid, current data as `STALE_DATA`. Confirmed via the same diagnostic that a
  real chain request scoped to the correct expiration returned 178 real contracts at
  `200 OK` -- the rejection happens *after* successful, correctly-scoped acquisition, at an
  unrelated freshness gate. Filed as
  [#162](https://github.com/jaiaFoster/ASA/issues/162), explicitly out of this patch's scope
  (`explicit_exclusions: broad_option_surface_redesign`) -- a full PASS/NO_SIGNAL run
  requires re-validating during market hours, which this patch's own live-validation window
  did not happen to fall within.
- **Raw credentials and secret values do not appear in logs or reports.** Confirmed --
  secret scan clean on every file this patch touched; every diagnostic script used printed
  only request paths, query parameters, and response bodies (public market data), never
  headers or credential material.
- **Request budgets remain enforced.** Confirmed via real Tradier rate-limit response
  headers observed during validation (`x-ratelimit-allowed: 120`,
  `x-ratelimit-available: 119` after one request, `x-ratelimit-used: 1`) -- consistent,
  bounded usage; `RequestBudgetManager`'s own ceiling (unchanged by this patch) was never
  approached, let alone exceeded.
- **The live run exits cleanly with isolated results.** Confirmed -- `python -m screening
  --live --universe AAPL,MSFT,NVDA,AMD,SPY,QQQ` exit code `0`, 18/18 results (6 symbols x 3
  strategies), zero crashes, zero `STRATEGY_EXCEPTION`, every failure cleanly isolated and
  accurately attributed.

## 6. Per-symbol strategy outcomes (full CLI run)

All 18 results: `missing_data`. Breakdown by root cause:

| Strategy | Blocker | Classification |
|---|---|---|
| `forward_factor` (all 6 symbols) | Real-time quote rejected as `STALE_DATA` (post-market-close, #162) -- acquisition never reaches the option-chain step | `provider_acquisition_failure` |
| `skew_momentum` (all 6 symbols) | Same as above | `provider_acquisition_failure` |
| `earnings_calendar` (all 6 symbols) | Earnings acquisition failure, root cause unconfirmed (independent of #156/#162, noted in SPRINT-007's own report section 7/10) | `provider_acquisition_failure` |

Independently, via targeted diagnostic (bypassing the quote step): AAPL's option-chain
acquisition for its 2026-08-21 expiration succeeded at the HTTP layer (200 OK, 178 real
contracts, correctly scoped), rejected only by the separate freshness gate (#162) -- direct
proof the #156 fix itself works against real Tradier data.

## 7. Provider request counts

Full CLI run (6 symbols x 3 strategies): each `forward_factor`/`skew_momentum` run attempted
1 quote request (failed at `STALE_DATA`, acquisition stopped there); each `earnings_calendar`
run attempted 1 earnings request (failed). Targeted diagnostics: 1 expirations-list request
(200, 24 expirations) + 1 expiration-specific chain request (200, 178 contracts) for AAPL.
No request exceeded Tradier's real, observed rate-limit ceiling (120/window).

## 8. Request budget evidence

Real Tradier `x-ratelimit-*` response headers observed during validation:
`x-ratelimit-allowed=120`, `x-ratelimit-available=119` (after 1 request in that window),
`x-ratelimit-used=1`. `RequestBudgetManager`'s own configured ceiling per provider was never
approached across any run in this patch's validation -- consistent with the sprint-level
request-budget guarantees already proven in SPRINT-007/LIVE-001's own tests.

## 9. Discovered and resolved defects

1. **The original defect (#156)**: fixed across TRADIER-PATCH-001/002/003, confirmed live
   in Section 5/6 above.
2. **`combine_option_chains()`'s duplicate-contract collision** (TRADIER-PATCH-003):
   discovered while writing tests, not assumed -- fixed with contract-identity
   deduplication before the existing fixture-backed tests would pass.
3. **Ambiguous `DomainInvariantError` classification** (TRADIER-PATCH-004, this ticket's
   own primary deliverable): `_acquire_or_raise()`'s single broad exception handler
   conflated "no provider offers this capability" with "a provider was selected but the
   subject was invalid" under one misleading message. Split into three accurately-labeled
   classes, with `acquire_expirations()` extended the same way (a related, closely
   analogous gap discovered during this ticket's own work, not previously covered by
   TRADIER-PATCH-001).

## 10. Remaining non-blocking issues

- **#147** (carried over) -- CI doesn't run root-level mypy or trigger reliably on every
  relevant path; confirmed again this patch (all four tickets' PRs triggered zero CI
  checks, resolved each time via local verification, matching the established
  resolution first confirmed for SPRINT-007's ANALYTICS-002).
- **#162** (new this patch) -- real option-chain/quote freshness computation
  (`market_data/tradier.py`) uses a possibly-illiquid contract's own last-trade time (chain)
  or the underlying's own last-trade time (quote) as a proxy for the whole observation's
  freshness, rejecting otherwise-valid, current data as `STALE_DATA` outside active trading
  hours. Explicitly out of this patch's scope (`explicit_exclusions:
  broad_option_surface_redesign`); a genuine follow-up.
- **`earnings_calendar`'s live acquisition failure** (carried over from SPRINT-007's own
  report) still has an unconfirmed root cause, independent of both #156 and #162.

## 11. Recommendations

1. Address #162 (freshness computation) before expecting a live run to produce a real
   PASS/NO_SIGNAL verdict reliably, especially for validation windows outside market hours.
2. Re-run `python -m screening --live` during active market hours to obtain the first real
   PASS/NO_SIGNAL evidence for Forward Factor and Skew Momentum against live Tradier data,
   now that #156 is fixed.
3. Investigate `earnings_calendar`'s separate, still-unconfirmed live acquisition failure.
4. Address #147 (CI coverage) as a Founder-reviewed `.github/workflows/` change, still
   independent of any sprint's or patch's own work items.

## 12. Confirmation: no secrets exposed

Secret scan (`grep -riE "token|secret|password|api[_-]?key|bearer"`) against every file this
patch changed: zero matches in source/test files; only descriptive requirement text in the
governance activation file (`docs/sprints/PATCH-007A.yaml`). Every live validation and
diagnostic script used `railway run`'s environment injection or a wrapped transport that
logs only request paths, query parameters, and response bodies (public market data) --
never headers, never credential values. No credential was read, printed, exported, or
committed at any point in this patch's work.

## 13. Deliverables

- `project/reports/PATCH-007A.md` / `.json` -- this report.
- `screening/live_context.py`: `acquire_expirations()`, `combine_option_chains()`,
  `classify_domain_invariant_error()`, extended `build_capability_subject()`.
- `screening/live_adapters.py`: two-step live adapter orchestration, narrowed exception
  handling.
- `tests/screening/`: four new/extended test files covering expiration discovery,
  expiration-aware subjects (proven against the real `TradierProvider` class), two-step
  acquisition (proven against a Tradier-shaped provider double), and error classification.
- `docs/sprints/PATCH-007A.yaml`: the Founder Sprint Delegation record (#158).
- Issues [#156](https://github.com/jaiaFoster/ASA/issues/156) (closed by this patch) and
  [#162](https://github.com/jaiaFoster/ASA/issues/162) (new, logged for follow-up).
