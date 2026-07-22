# SPRINT-007 — Derived Analytics & Live Screening ("Bounded Live Signals")

Status: Implementation complete, **founder_verification_pending**. Per this sprint's own
`docs/sprints/SPRINT-007.yaml` (Founder Sprint Delegation, GOV-AMD-001-013 / GOV-007, #150),
Founder verification is required before a successor sprint (SPRINT-008) begins.

Validation time (UTC): 2026-07-22
Repository commit: `00f7980` (`main`, through PR #155)

## 1. Sprint summary

Extended SPRINT-006's fixture-backed screening framework with a canonical derived-analytics
subsystem and real, bounded live execution. `analytics/` was introduced as a reusable,
provider-neutral framework (ANALYTICS-001) and then given real Forward Factor math --
implied forward volatility and DTE computation, closing SPRINT-006's own recorded gap
(ANALYTICS-002). Strategy-specific execution-context builders were added on top of it
(ANALYTICS-003). `screening/` was then wired to the existing Market Data Platform for
canonical, provider-independent live capability acquisition (LIVE-001), and
`python -m screening --live` was made real: it now runs all three target strategies against
real, network-connected providers across an explicit six-symbol validation universe, force-
disabling the fixture provider and failing closed if no real provider is enabled, so it can
never silently substitute offline data for live data (LIVE-002). Finally, LIVE-003 ran that
live path against real Tradier credentials configured in Railway's `ASA` production service
and confirmed the definition of done's actual requirement: deterministic, request-budget-
compliant, failure-isolated execution -- not a guarantee that every strategy produces a
trading signal on the first real run.

That last run surfaced a genuine, previously-undiscovered integration gap (Section 9):
Tradier's real option-chain endpoint requires a specific expiration per request, which
`screening/live_context.py`'s subject construction never supplies, so `forward_factor` and
`skew_momentum` cannot yet produce a live signal against Tradier. Per explicit Founder
decision, this is logged as a known issue (#156) rather than expanding LIVE-003's scope into
a live-execution redesign.

## 2. Completed tickets

| Ticket | Title | PR |
|---|---|---|
| GOV-007 | Activate SPRINT-007 Founder Sprint Delegation | #150 |
| ANALYTICS-001 | Canonical Derived Analytics Framework | #151 |
| ANALYTICS-002 | Forward Factor Derived Analytics | #152 |
| ANALYTICS-003 | Strategy Input Builders | #153 |
| LIVE-001 | Live Market Data Integration | #154 |
| LIVE-002 | Live Screening Runner | #155 |
| LIVE-003 | Operational Live Validation | this PR |

## 3. Delegated merged pull requests

#151, #152, #153, #154, #155 were merged under the active Founder Sprint Delegation
(Amendment 013, activated by the Founder's merge of #150) after all required gates passed.
#150 was merged by the Founder directly, per the delegation's own activation sequencing
(delegation cannot be self-activated). This PR (LIVE-003) is merged under the same active
delegation, following the Founder's explicit confirmation to proceed with the first real
run against live provider credentials, per `live_execution_policy`'s own gate.

## 4. Validation results

- `pytest tests/` (full repository): **2180 passed, 2 skipped** (pre-existing skips,
  unrelated to this sprint).
- `pytest tests/architecture/ tests/market_data/ tests/screening/ tests/analytics/`:
  **706 passed, 1 skipped** (pre-existing).
- `pytest tests/strategies/ tests/architecture/test_stonk_decommissioning.py` (existing
  strategy regression, re-run unmodified): **259 passed** -- identical to SPRINT-006's
  baseline, confirming zero strategy semantic drift across the whole sprint.
- `ruff check` (every touched package): clean throughout every ticket.
- `mypy` (every new/modified file, every ticket): zero errors attributed to this sprint's
  own files. The same 22 pre-existing `strategies`/`indicators` findings (tracked in #147,
  filed during SPRINT-006) continue to surface transitively; not fixed here, unrelated-
  refactoring risk to code this sprint must not touch.
- `tools/pos/lean/check_integrity.py`, `check_entrypoints.py`, `pre_push_check.py`: all
  green throughout every ticket.
- `tools/pos/lean/generate.py current-state` vs. `CURRENT_STATE.md`: only the pinned
  `Generated:` timestamp line differs (expected); no content drift.
- `git status --short` after every merge: worktree clean, no drift.
- CI: `Validate Architecture` (the only workflow whose path filters this sprint's changes
  ever matched) green on every PR that touched `market_data/**` or `tests/architecture/**`.
  `Product CI` and `Validate POS` never triggered -- this sprint touched none of their
  path filters (`backend/`, `frontend/`, `governance/`, `project/`, `tools/pos/`), matching
  the same non-triggering pattern already seen in SPRINT-006/#147.

## 5. Architecture and governance verification

- `analytics/` and `screening/` each carry their own architecture boundary suite
  (`tests/architecture/test_analytics_boundaries.py`,
  `tests/architecture/test_screening_boundaries.py`); both stayed green all sprint, extended
  only when a genuinely new, real import appeared (e.g. `screening/cli.py` importing
  `market_data.live_transport`), never loosened speculatively.
- `screening/`'s boundary suite forbids it from importing `urllib` or performing network I/O
  directly. This was actually caught in practice: `market_data/live_transport.py`'s stdlib
  `urllib` transport implementation was first written inside `screening/` during LIVE-002,
  failed the boundary tests immediately, and was relocated to `market_data/` (which carries
  no such restriction) before merging -- the gate did what it's for.
- No strategy's threshold, formula, entry logic, or scoring changed -- confirmed by the
  unchanged 259-test regression count and by inspection (zero lines touched under
  `strategies/` all sprint). `analytics/expiration_selection.py`'s earnings-relative pairing
  and `screening/live_adapters.py`'s adapters independently reimplement, rather than import,
  the same selection semantics `strategies/stonk_components.py` already uses privately --
  the one-directional dependency rule (`strategies/` cannot import `screening/` or
  `analytics/`) was never violated.
- Founder Sprint Delegation (Amendment 013) was used exactly as designed: activation
  required a Founder merge (#150) before any delegated merge occurred; every delegated
  merge passed its full required-gate list first; `.github/` and `governance/frozen/` were
  never touched; the `live_execution_policy` gate on LIVE-003 was honored precisely --
  every ticket up to and including LIVE-002 proceeded under standing delegation, but the
  first real run against live provider credentials stopped and required, and received,
  explicit Founder confirmation before executing.
- One ambiguous-gate check-in occurred (ANALYTICS-002, PR #152: CI never triggered at all
  for a root-level Python change with no matching workflow path filter); resolved by the
  Founder choosing "merge now, based on local verification" rather than being decided
  unilaterally.

## 6. Derived analytics catalog

| Module | Function | Purpose |
|---|---|---|
| `analytics/forward_factor.py` | `compute_days_to_expiration` | Calendar-day DTE from `as_of` to an expiration date. |
| `analytics/forward_factor.py` | `compute_option_implied_volatility` | Extracts the canonical `implied_volatility` field verbatim from a matching `OptionContract` -- no Black-Scholes solving, the field is already populated live by `market_data/tradier.py`. |
| `analytics/expiration_selection.py` | `select_expiration_pair` | DTE-window+gap based front/back pair selection (Forward Factor's policy). |
| `analytics/expiration_selection.py` | `select_earnings_relative_expiration_pair` | Earnings-relative front/back pairing: front strictly before the earnings date, back strictly after, each within its own DTE window (Earnings Calendar's policy). |
| `analytics/atm_selection.py` | `select_atm_strike` | Standard closest-strike ATM selection, ties broken toward the lower strike. |

All five are registered, tested in isolation, and proven against the real, frozen
`FORWARD_FACTOR_CALENDAR_MANIFEST` with zero additional math
(`tests/analytics/test_forward_factor_manifest_integration.py`).

## 7. Live validation results per symbol

`python -m screening --live --json`, executed 2026-07-22T20:00 UTC against Railway's `ASA`
production service (`railway run`, real Tradier credentials injected directly into the
subprocess environment -- no credential value was ever read, printed, or handled by the
implementing agent). Full six-symbol `validation_universe`, all three target strategies,
`--as-of` defaulted to the real clock:

| Symbol | forward_factor | earnings_calendar | skew_momentum |
|---|---|---|---|
| AAPL | missing_data (option chain -- #156) | missing_data (earnings acquisition) | missing_data (option chain -- #156) |
| MSFT | missing_data (option chain -- #156) | missing_data (earnings acquisition) | missing_data (option chain -- #156) |
| NVDA | missing_data (option chain -- #156) | missing_data (earnings acquisition) | missing_data (option chain -- #156) |
| AMD | missing_data (option chain -- #156) | missing_data (earnings acquisition) | missing_data (option chain -- #156) |
| SPY | missing_data (option chain -- #156) | missing_data (earnings acquisition) | missing_data (option chain -- #156) |
| QQQ | missing_data (option chain -- #156) | missing_data (earnings acquisition) | missing_data (option chain -- #156) |

18/18 results: zero crashes, zero `STRATEGY_EXCEPTION`, zero unhandled exceptions escaping
the CLI. Every failure is isolated, deterministic in structure, and correctly attributed a
`failure_detail`. This is what the sprint's own `definition_of_done` actually asks for --
`python -m screening --live` "executes successfully ... with deterministic, request-budget-
compliant, failure-isolated output" -- not that every strategy produces a live PASS/NO_SIGNAL
verdict on its first real run. The specific blocker preventing `forward_factor`/
`skew_momentum` from producing a real signal is a confirmed, well-understood, non-blocking
code gap (#156), not a live-data-availability or crash problem.

`earnings_calendar`'s failure (a plain "could not acquire live earnings_calendar_v1"
`FulfillmentStatus`, not the `DomainInvariantError` behind #156) has an unconfirmed root
cause -- possibly no live Finnhub/Alpha Vantage credential enabled in this environment,
possibly a genuine empty provider response for these symbols on this date. Not investigated
further this sprint since it's independent of #156's confirmed cause; noted in Section 10.

## 8. Request budget evidence

The live run above made real acquisition requests against Tradier for all six symbols
without any `RequestBudgetPolicy` rejection surfacing in the output -- `screening/
live_acquisition.py::build_request_budget_manager` derives each enabled provider's ceiling
directly from its own `ProviderConfig.request_budget` (never widened by this sprint's CLI
wiring), and one `RequestBudgetManager` instance is shared across every provider dependency
for the whole run, exactly as LIVE-001 built and tested it
(`tests/market_data/test_sprint_005b_integration.py::test_request_budget_is_enforced_within_the_same_clock_tick`).
`screening/cli.py::_live_only_config()` additionally force-disables the always-enabled-by-
default `deterministic_fixture` provider for `--live`, and fails closed with a clear error
if that leaves zero enabled providers -- verified by dedicated tests
(`tests/screening/test_cli.py::TestLive`) using a network-free injected transport, so this
sprint never needed real credentials to prove that specific behavior; only this section's
live run exercised real credentials at all.

## 9. Discovered and resolved defects

1. **`_acquire_or_raise` let a raw `DomainInvariantError` escape as `STRATEGY_EXCEPTION`
   instead of the documented `MISSING_DATA` contract.** Found during LIVE-002's own test
   development (not the live run): when no enabled provider declares a requested capability
   at all, `CapabilityRegistry.lookup()` raises rather than returning a not-fulfilled
   result. Fixed in `screening/live_adapters.py::_acquire_or_raise` before LIVE-002 merged,
   with a dedicated regression test
   (`tests/screening/test_live_adapters.py::TestCapabilityNotOfferedByAnyEnabledProvider`).
2. **`market_data/live_transport.py` initially violated `screening/`'s own architecture
   boundary.** Found immediately by `tests/architecture/test_screening_boundaries.py` when
   first written inside `screening/`; relocated to `market_data/` before LIVE-002 merged.
   No defect reached `main`.
3. **Tradier option-chain acquisition never succeeds against real Tradier data (#156).**
   Found in this ticket's own live run, described in full in Section 7 and the linked
   issue. By explicit Founder decision, logged as a known issue rather than fixed as part
   of this sprint -- fixing it means restructuring already-merged LIVE-002 adapters into a
   two-step acquisition flow, a real design change, not a small patch.

## 10. Remaining non-blocking issues

- **#147** (carried over from SPRINT-006, still open) -- CI doesn't run root-level mypy or
  trigger reliably on every relevant path.
- **#156** (new this sprint) -- Tradier's real option-chain endpoint requires a specific
  expiration per request; `screening/live_context.py` never supplies one, so
  `forward_factor`/`skew_momentum` cannot yet produce a live signal against Tradier.
  Directly related to and informed by the already-merged fix for the same bug class in
  `backend/`'s independent validation path (#139).
- **`earnings_calendar`'s live acquisition failure has an unconfirmed root cause** (Section
  7) -- worth a short, separate investigation before or alongside #156's fix, since fixing
  #156 alone won't necessarily make `earnings_calendar` produce a live signal too.

No other open issues were created this sprint.

## 11. Recommendations for SPRINT-008

1. Resolve #156 (Tradier's two-step expiration-then-chain acquisition flow) and confirm
   `earnings_calendar`'s separate live-acquisition failure before treating any of the three
   target strategies as genuinely live-signal-capable.
2. Once #156 is fixed, re-run `python -m screening --live` against the same six-symbol
   validation universe and confirm at least one real `PASS`/`NO_SIGNAL` verdict per
   strategy, not just clean failure isolation.
3. Decide the `Opportunity`/`ranking` bridge (deferred since SPRINT-006's #143 decision) --
   now that live signals are close to real, this is likely the next natural blocker.
4. Address #147 (CI coverage) as a Founder-reviewed `.github/workflows/` change, still
   independent of any sprint's own work items.

## 12. Deliverables

- `project/reports/SPRINT-007.md` / `.json` -- this report.
- `analytics/` package additions: `atm_selection.py`,
  `expiration_selection.py::select_earnings_relative_expiration_pair`, plus ANALYTICS-001's
  original framework (`registry.py`, `features.py`, `engine.py`) and ANALYTICS-002's Forward
  Factor math (`forward_factor.py`).
- `screening/live_acquisition.py`, `screening/live_context.py`,
  `screening/live_adapters.py`, `screening/context_builders.py`: live capability acquisition,
  subject/context bridging, and the three live target-strategy adapters.
- `market_data/live_transport.py`: stdlib `urllib` live transport implementation.
- `screening/cli.py`: real `--live` wiring, bounded live universe support.
- `tests/analytics/`, `tests/screening/`: this sprint's new and extended test suites.
- `docs/sprints/SPRINT-007.yaml`: the Founder Sprint Delegation record (#150).
- Issue #156: Tradier live option-chain acquisition gap, logged for SPRINT-008.
