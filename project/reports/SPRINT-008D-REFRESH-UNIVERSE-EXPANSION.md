# SPRINT-008D — PROD-005: Refresh Universe Expansion Strategy

Status: Complete. **Recommendation: do not expand `APPROVED_LIVE_UNIVERSE` yet.**

Sprint reference: `docs/sprints/SPRINT-008D.yaml`
Repository commit at evaluation time: `66d482c` (`main`)

## 1. Objective

Using real usage data and provider-budget evidence from PROD-002 and PROD-004, evaluate whether
and how `APPROVED_LIVE_UNIVERSE` should expand, and document a long-term expansion strategy,
while explicitly preserving the existing provider-request safety guarantees unchanged.

## 2. What evidence is actually available

This ticket's own objective calls for evaluating expansion using **real usage data** from
PROD-002. That data does not exist yet: PROD-002's first production run had not executed at the
time of this evaluation (`project/reports/SPRINT-008D-PRODUCTION-SCREENING.md`, Section 3 —
blocked on tooling, Founder action requested). This evaluation is therefore necessarily based on
code-level analysis and local test evidence, not real production telemetry, and says so
explicitly rather than presenting an estimate as if it were measured.

## 3. Provider capacity — not currently a constraint

`market_data.config.RequestBudgetConfig`'s own default ceiling is 100 requests per provider *per
run* (`market_data/config.py`), and `asa/scheduled_screening.py` builds a fresh budget per pair
(PROD-002), so this ceiling applies per pair, not across a batch. Each pair's actual live
acquisition uses roughly 2-4 requests (PROD-004's data-requirement audit: a spot quote, an
expiration lookup, one or more chain fetches). At the current 12-pair universe, one full
scheduled run uses on the order of 30-50 requests total against a *per-pair* ceiling of 100 —
there is no evidence of the current bound being anywhere near a provider-capacity limit. This
headroom would comfortably absorb a meaningfully larger symbol set from a pure request-volume
standpoint alone.

**This means provider capacity is not the reason to hold off expanding.** The reason is Section 4.

## 4. Why expansion is not recommended right now

1. **No real usage data exists yet** (Section 2) — this ticket's own evaluation method
   presupposes PROD-002 has run at least once. Expanding the universe before the *current* one
   has even completed a single production run would mean scaling up an untested workflow, not a
   validated one.
2. **`earnings_calendar` is still deferred** (PROD-001, pending PROD-004's Finnhub confirmation)
   — a second signal is already queued to join the *existing* six-symbol universe before any
   *symbol* expansion is considered. Symbol expansion and signal expansion are independent axes
   (PROD-001, Section 6), but taking on both at once compounds what a first production run needs
   to validate.
3. **The existing bound has institutional weight beyond this sprint**: `APPROVED_LIVE_UNIVERSE`
   is "the SPRINT-007 Founder-approved live validation_universe"
   (`screening/live_acquisition.py`'s own docstring) — a deliberate, explicit Founder decision,
   not an arbitrary default. Widening it is explicitly excluded from every ticket in this sprint
   that touches it (API-004's own ticket exclusions in SPRINT-008; this sprint's own
   `bounded_scope.out`). Recommending expansion without the real usage evidence Section 2
   describes would be asking the Founder to re-approve a risk-floor-adjacent boundary on the
   strength of a code-level estimate alone.

## 5. Long-term expansion strategy (for when real data exists)

Recorded here so a future evaluation has explicit criteria to apply, not a blank page:

1. **Trigger**: only after PROD-002 has produced a meaningful run history (the same criterion
   `docs/screening/cache-lifecycle.md`, PROD-003, already recorded as its own revisit trigger) —
   at minimum, several completed daily runs with real request-count and timing data, so any
   expansion decision is grounded in what the system actually does, not what it is estimated to
   do.
2. **Liquidity bar**: any candidate symbol must meet the same options-market-depth bar
   `project/reports/SPRINT-008D-SCREENING-UNIVERSE.md` (PROD-001, Section 5) already established
   for the current six — deep, liquid single-name or index-ETF options markets, not an arbitrary
   market-cap or popularity threshold. `forward_factor` and `skew_momentum` both select specific
   strikes/expirations from real chain depth; a thin chain degrades results regardless of code
   correctness.
3. **Approval path**: unchanged from today — a symbol addition to `APPROVED_LIVE_UNIVERSE`
   requires the same Founder-level approval its original SPRINT-007 approval did. This ticket
   does not propose a lighter-weight process for future changes; the bound's whole purpose is
   that it is not silently widened.
4. **Incremental, not wholesale**: expand in small increments (a handful of symbols at a time)
   with a production run cycle in between, rather than a single large jump — consistent with
   this sprint's own `quality.avoid: major_architectural_refactoring` applied to operational
   scope, not just code.

## 6. Provider safety guarantees — confirmed unweakened

Two structural guarantees exist independent of which symbols are in the universe, and neither is
touched by this evaluation or would be touched by a future expansion following Section 5:

- `screening.live_acquisition.live_only_config()`'s force-disable of the `deterministic_fixture`
  provider for any live acquisition — a code-level guarantee, not data-dependent.
- The per-pair `RequestBudgetManager` ceiling (Section 3) — applies identically regardless of
  universe size, since it is constructed fresh per pair, not shared across a batch.

Confirmed by direct inspection of `screening/live_acquisition.py`, unchanged by this ticket (no
code was modified). One small, directly related correction was made: `asa/scheduled_screening.py`
(PROD-002) previously hardcoded its own copy of the six symbols rather than importing
`APPROVED_LIVE_UNIVERSE` — fixed during this evaluation to reference it directly, so a future
Founder-approved expansion of the bound propagates automatically to the scheduled runner instead
of requiring a second, easy-to-forget edit. Verified: `tests/asa/test_scheduled_screening.py`
(9 tests including this change) and `tests/asa/test_boundaries.py` both still pass; `ruff` and
`mypy` clean.

## 7. Conclusion

No expansion of `APPROVED_LIVE_UNIVERSE` is recommended or made at this time. Provider capacity
is not the limiting factor — the absence of real production usage data is. Explicit criteria and
an approval path are recorded above for when that data exists. One small consistency fix
(referencing the existing universe constant instead of a duplicated copy) was applied to reduce
future drift risk, with no change to the universe's actual contents or to either provider safety
guarantee.
