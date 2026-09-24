# OUTCOME-INTELLIGENCE-001 — Autonomous Sprint Prompt


## Founder Sprint Delegation record

- **Sprint:** `OUTCOME-INTELLIGENCE-001`
- **Founder authorization:** explicit, 2026-09-23, as part of ASA-OPTIONS-TO-OUTCOMES-2026Q4
- **Governance mechanism:** GOV-AMD-001 Amendment 013 (Founder Sprint Delegation)
- **Delegate:** ROLE-WORKER, instance `implementation-worker`
- **Approved tickets:** `OI-01`, `OI-02`, `OI-03`, `OI-04`, `OI-05`, `OI-06`, `OI-07`
- **Effective when:** this sprint definition and the program prompt are on the default branch through Founder merge
- **Expires when:** sprint closes; sprint stops; Founder revokes; or scope/authority/risk materially changes
- **Deployment authority:** Founder only; not delegated
- **Broker/live mutation authority:** none
- **Paid-provider procurement authority:** none

Before every delegated merge, the Worker must record self-review and satisfy all validation/review gates required by current governance and the touched risk class, including required CI, architecture validation, deterministic replay/identity/immutable-contract/integrity checks where applicable, scope conformance, and no unresolved blocker. Branch-protection bypass and governance changes are not delegated.

### Stop conditions

Stop only the affected path and escalate to the appropriate role when:
- required validation or mandatory review fails and cannot be corrected in scope;
- implementation would create a new authority, source of truth, strategy-ID branch in generic runtime, or materially incompatible architecture;
- scope/risk/authority would expand beyond this sprint;
- a genuine Founder blocker from the program prompt is reached.

Independent in-scope work continues whenever isolation is safe.
**Purpose:** begin measuring what ASA’s opportunities subsequently do, creating a proprietary forward evidence set and a transparent prioritization layer only after real opportunity volume exists.

Read the program prompt first.

## Core principle

Do not purchase a large historical research dataset as a prerequisite. Start accumulating exact forward outcomes from ASA’s own timestamped proposals now.

This sprint measures **modeled/paper opportunity outcomes**, not actual brokerage performance unless actual fills are separately and truthfully imported in a future authorized program.

## Work packages

### OI-01 — Immutable opportunity identity
Ensure each trackable proposal has deterministic identity covering strategy/version, subject, evidence snapshot, exact structure/position, modeled entry reference, and decision time as appropriate. Replay/collision behavior must fail closed.

### OI-02 — Forward observation model
Define provider-neutral forward observations for configured horizons such as:
- next eligible session;
- D+1 / D+5 / D+10 where meaningful;
- strategy-specific lifecycle checkpoints;
- expiration/close horizon;
- maximum favorable/adverse excursion where computable;
- modeled mark-to-market under explicit pricing assumptions.

Asset/strategy semantics may choose appropriate horizons; generic storage must not hard-code financial judgment.

### OI-03 — Outcome collector
Implement externally schedulable, run-and-exit collection using the same market-data authority. No daemon requirement. Reuse current evidence acquisition and preserve timestamps/provenance.

### OI-04 — Outcome ledger/reporting
Persist immutable forward observations separately from current latest-state screening. Do not rewrite the original proposal to make later outcomes appear known at decision time.

### OI-05 — User outcome UI
Show:
- tracked/open proposals;
- closed/expired observations;
- modeled return/P&L where supportable;
- drawdown/MFE/MAE where supportable;
- counts by strategy;
- sample sizes;
- clear “paper/modeled, not brokerage fill” labeling.

### OI-06 — Transparent prioritization
Only if opportunity volume is sufficient, introduce an explainable prioritization layer based on currently trustworthy quantities such as:
- actionability;
- evidence completeness/freshness;
- liquidity;
- defined risk/payoff properties;
- portfolio fit if available;
- forward outcome evidence with sample-size guards.

Do not use opaque ML, optimize to tiny samples, or claim one strategy is superior without sufficient evidence. If volume is still sparse, ship sorting/filtering and defer empirical weighting.

### OI-07 — Decision point for deeper research/data
At sprint end, produce a data-value report:
- opportunity counts by strategy;
- lost opportunities attributable to provider capability;
- forward outcome sample sizes;
- which decisions cannot be made without more historical data;
- exact paid capability that would unlock each blocked product/research question.

This report informs a later Founder procurement decision; it does not itself purchase data.

## Acceptance

ASA continuously preserves its own forward opportunity evidence without look-ahead contamination and can show the Founder what prior ASA proposals subsequently did. Any prioritization is transparent, sample-aware, and subordinate to truthful evidence.

## Program closure

After observation passes for this sprint and no material reopened defect remains, close ASA-OPTIONS-TO-OUTCOMES-2026Q4 with a concise exact-main report covering:
- options funnel;
- executable trade UX;
- stock product path;
- strategy library breadth;
- AOY and coverage;
- forward outcome corpus;
- remaining quantified data/provider blockers;
- genuine next product decisions.
