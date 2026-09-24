# OPTIONS-TRUTH-001 — Autonomous Sprint Prompt

**Purpose:** prove and repair the complete production options funnel so ASA can explain exactly why every candidate does or does not become an actionable options opportunity.

Read `docs/sprints/ASA-OPTIONS-TO-OUTCOMES-2026Q4.md` first. Its autonomy, semi-parallel, escalation, invariants, and no-lull rules are binding for this sprint.

## Product question

**Why is ASA not routinely putting valid option trades in front of the Founder, especially around real earnings events?**

Current production strategies in scope:
- `forward_factor`
- `skew_momentum`
- `earnings_calendar`

Earnings Calendar is the priority diagnostic because observed product usefulness does not match expectations. Do not assume the absence of trades is correct merely because current tests pass.

## Required end-to-end funnel

Every candidate must terminate in a typed, inspectable state:

```
universe
  -> acquisition attempted/reused
  -> required evidence available or typed unavailable
  -> strategy evaluated
  -> gate-by-gate result
  -> qualifying signal or explicit rejection
  -> exact structure resolution
  -> liquidity/constructibility assessment
  -> actionable opportunity OR typed terminal reason
```

No candidate may silently disappear between stages.

## Work packages

### OT-01 — Source-semantics audit
For each current strategy, reconstruct the intended/source methodology from repository evidence and the strategy's already-recorded source material. Compare:
- entry/gating conditions;
- expiration rules;
- strike/delta selection;
- earnings treatment;
- IV/skew/forward-vol formulas;
- liquidity filters;
- structure substitution policy;
- lifecycle/exit semantics where present.

Produce a machine-reviewable discrepancy table. Fix only discrepancies that are clearly errors relative to the accepted strategy definition. If source material is ambiguous in a way that changes the end product, that is a genuine Founder blocker; otherwise choose the narrowest faithful interpretation and record it.

### OT-02 — Funnel observability
Add a provider-neutral funnel/diagnostic model or extend existing typed diagnostics so every pair/candidate records:
- candidate inclusion reason;
- declared capability demands;
- acquisition result and reuse;
- missing/unknown reason by capability;
- gate outcomes;
- signal verdict;
- structure resolution;
- constructibility/liquidity terminal state.

Avoid a second persistence authority. Reuse existing result/attempt/evidence storage where possible.

### OT-03 — Earnings cohort proof
Build a bounded real-market cohort around recent/next eligible earnings events. For each symbol, prove:
- whether event evidence existed;
- whether the strategy evaluated;
- which rule failed if rejected;
- whether required expirations/contracts existed;
- whether a structure could be built;
- whether liquidity blocked it.

The artifact must distinguish:
1. ASA defect;
2. provider entitlement/coverage;
3. legitimate temporal/policy absence;
4. genuinely unknown/unannounced event;
5. true strategy rejection;
6. structure/market unavailability.

### OT-04 — Root-cause corrections
Repair in-scope defects uncovered by OT-01–03. Favor generic capability/analytics/runtime fixes when the defect is generic. Do not add strategy-ID branches to generic runtime. Do not loosen financial gates merely to manufacture PASS results.

### OT-05 — Shared-query proof
Prove current same-subject strategies share one subject acquisition plan per cycle and that identical capability requests are reused. Add regression coverage for success and failure reuse. Report provider calls per subject/cycle before/after only if a correction changes them.

### OT-06 — Market-session validation
On exact merged main, collect the next eligible market-session evidence automatically where possible. Produce funnel counts by strategy and terminal reason, with zero unexplained drops.

## Acceptance

Deterministic/local:
- current option strategies have source-semantics discrepancy evidence;
- every candidate path terminates with a typed outcome;
- shared acquisition remains one authority;
- no generic strategy-ID branches;
- tests/CI green for touched boundaries.

Observation:
- bounded live/recent cohort proves complete funnel traceability;
- Earnings Calendar behavior is explainable on actual relevant earnings candidates;
- zero unexplained candidate loss.

## Observation transition

Once OT-01–05 are merged and only a market-session capture remains, mark sprint `IMPLEMENTATION_COMPLETE_AWAITING_OBSERVATION` and immediately begin OPTIONS-PRODUCT-001. If OT-06 fails, reopen this sprint in parallel.

## Procurement rule

Do not buy data. If an external provider gap blocks otherwise-qualified opportunities, quantify:
- affected symbols/opportunities;
- required missing capability;
- current provider evidence;
- expected product impact;
- candidate provider requirement.

Escalate procurement only when that quantified blocker is material.

## Closure artifact

Record exact main SHA, cohort, timestamps, funnel counts, discrepancies fixed/not fixed, typed external blockers, tests, and any reopened corrections.
