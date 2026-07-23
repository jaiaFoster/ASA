# API-SPRINT-ISSUES — GitHub Issue Review & Reconciliation

Per `docs/sprints/SPRINT-008.yaml`'s `api_sprint_issues_ticket` (GOV-008C,
API-SPRINT-CONTINUATION, #188). Reviews every currently-open GitHub issue as
of 2026-07-23, plus relevant recently-closed issues for context.

## Summary

**13 open issues reviewed. None fall within API-002 through API-006's own
approved scope.** No implementation PRs are opened by this ticket, per its
own instruction to implement only issues genuinely within the API Sprint's
scope — zero qualifying issues is the correct outcome here, not a shortfall.
No duplicates found. No issue is recommended for closure without direct
evidence that it is resolved or superseded; none of the 13 met that bar, so
none are recommended for closure.

## Categorization

### Not API Sprint scope — pre-existing architecture backlog (10 issues)

All ten below are tagged `architecture, non-blocking` and concern
calibration, disambiguation, or provenance refinements in subsystems
API-002 through API-006 never touch (ranking weights, guardrail evidence
citation, reconciliation provenance/weighting, indicator/fact identity,
outcome-metric formulas). None reference the screening state repository,
the REST API surface, or anything ARCH-MONOREPO-001 touched. Recommend:
**keep open**, correctly out of this sprint's scope, no action from this
ticket.

| # | Title |
|---|---|
| 55 | Ranking v1 weights and normalization bounds require calibration |
| 54 | Opportunity contract lacks liquidity metric required for calibrated Ranking |
| 50 | Guardrail evidence citation is coarse — always cites full Opportunity evidence, not narrowed per check |
| 47 | reconciliation.engine.reconcile has the same stale-provenance pattern fixed in indicators (ASA-CORE-005 Phase 0) |
| 46 | Expected Outcome Metrics use uncalibrated placeholder formulas (fixed stop-loss, fixed time horizon) |
| 44 | Indicator repository grouping key cannot disambiguate configuration or subject |
| 43 | Indicator calculations hardcode a "price" field; no general fact-value projection contract |
| 41 | Canonical Fact identity can collide across versions on value oscillation |
| 40 | Canonical Fact grouping key has no subject/instrument disambiguation |
| 39 | Reconciliation v1 uses unweighted agreement, not ADR-001 provider priority |

### Not API Sprint scope — unrelated CI/lint backlog (2 issues)

- **#77** "Restore repository-wide Ruff baseline" — six pre-existing
  unused-import/unused-variable findings in `providers/`, `tests/facts/`,
  `tests/indicators/`, `tests/providers/`, `tests/strategies/`. None of
  those paths are touched by API-002 through API-006 or by
  ARCH-MONOREPO-001. A small, bounded, mechanical fix, but genuinely
  unrelated to this sprint. Recommend: **keep open**, not actionable here.
- **#147** "CI does not run tests/screening/ or root-level mypy" — a CI
  *coverage gap* (no workflow currently runs `tests/screening/` or
  root-level `mypy` on every PR), not a functional defect. Directly
  relevant context for this sprint (screening/ is what API-002 through
  API-006 build on) but not something this sprint needs to fix itself:
  `docs/sprints/SPRINT-008.yaml`'s own `validation.required_before_every_
  delegated_merge` already explicitly lists `pytest_tests_screening` as a
  required gate for every ticket in this sprint, independent of whatever
  the general-purpose CI workflows do or don't cover — the sprint's own
  process already compensates for this gap for its own work. Recommend:
  **keep open**, tracked, no new action from this ticket.

### Not API Sprint scope, but relevant context for API-004/API-006 (1 issue)

- **#162** "Live option-chain/quote freshness rejects after-hours data as
  STALE_DATA" — affects live provider acquisition's own freshness gating
  (`market_data/tradier.py`), discovered and filed during PATCH-007A. Not
  a defect in the API Sprint's own read/refresh contract logic, so it is
  out of API-004's implementation scope. It is directly relevant
  *documentation* context, though: API-004's refresh endpoint calls the
  same live acquisition path this issue affects, so a refresh request
  issued outside active market hours may legitimately return a
  data-quality failure rather than a fresh result — worth stating plainly
  in API-004's own response documentation and API-006's operational docs,
  not silently surprising an API consumer. Recommend: **keep open**, out
  of implementation scope, cross-referenced in API-004/API-006 below.

## Recently closed issues reviewed for context (no action needed)

- **#178** (closed 2026-07-23, this same work session) — Railpack's
  pip-mode install target not on the runtime `sys.path`. Closed with direct
  evidence: **directly** resolved by ARCH-MONOREPO-001's own consolidation
  work (not an indirect side effect of unrelated work — ARCH-MONOREPO-001
  was undertaken specifically because this issue existed), confirmed via a
  real successful live deployment. No further action.
- **#156** (closed 2026-07-22) — Tradier expiration projection defect,
  resolved by PATCH-007A. Unrelated to this sprint's own scope, no further
  action.
- All other recently-closed issues reviewed (#143, #119, #111, #103, #93,
  #81, #70, #67, #63, #61, #59, #57, #49) are historical governance/
  architecture blockers already resolved well before this sprint's
  resumption, with no bearing on API-002 through API-006.

## Recommendation

No issues recommended for closure. No duplicates identified. No stale
issues identified — every open issue's finding remains specific, current,
and not superseded by any completed work reviewed here. Proceed with
API-002 through API-006 as scoped; #162 should be cross-referenced (not
fixed) in API-004's and API-006's own documentation deliverables.
