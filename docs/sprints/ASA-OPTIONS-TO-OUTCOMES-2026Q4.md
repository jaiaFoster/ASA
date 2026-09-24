# ASA OPTIONS-TO-OUTCOMES PROGRAM — Execution Prompt

**Program ID:** ASA-OPTIONS-TO-OUTCOMES-2026Q4  
**Founder authorization:** 2026-09-23  
**Baseline:** main@593d5d4b9b83fa8573b870bd9fa7a7b7dc004b11  
**Program objective:** make ASA first an excellent, routinely useful options screener and trade-decision product; then extend the same product standard to stocks; then broaden the strategy library; then use accumulated live outcomes to prioritize opportunities.

This document is the canonical worker prompt for the next five sprints. It is intentionally repository-resident. Chat activation should be short: the worker loads this file and the currently active sprint prompt from GitHub, rehydrates current main, and executes autonomously.

## Founder direction

The Founder has authorized the full five-sprint sequence and the operating model in this document. Do not return to the Founder for routine ticket authorization, PR authorization, sequencing, implementation choices, test fixes, ordinary refactors, provider-neutral diagnostics, observation scheduling, or reopening of a sprint after failed validation.

The near-term product goal is **usefulness before research breadth**:

1. Options must work flawlessly enough to surface understandable, executable trade ideas.
2. Screening must be complete, explainable, and operationally trustworthy.
3. A qualifying option strategy must resolve toward exact contracts/legs and a human-usable trade presentation.
4. Stocks receive the same product treatment after Options v1 is useful.
5. Strategy breadth is increased after both product paths exist.
6. Cross-strategy ranking/research becomes important after ASA has enough opportunity volume to create a real prioritization problem.
7. Paid historical data is not a default prerequisite. Procurement is justified only by a concrete product or coverage blocker with quantified impact.

## Authorized sprint sequence

1. `OPTIONS-TRUTH-001`
2. `OPTIONS-PRODUCT-001`
3. `STOCK-PRODUCT-001`
4. `STRATEGY-LIBRARY-001`
5. `OUTCOME-INTELLIGENCE-001`

Canonical prompts live beside this file in `docs/sprints/`.

## Program invariants

- One market-data authority. Strategies never acquire providers directly.
- One subject/cycle acquisition plan may satisfy multiple strategy consumers; identical capability demands should be reused rather than independently reacquired.
- Strategies own strategy-specific financial judgment; generic runtime/orchestration must not accumulate strategy-ID branches.
- Provider data is evidence, analytics owns reusable derived facts, strategies own gates/thresholds/structure semantics, runtime owns generic execution/projection/persistence.
- UNKNOWN remains UNKNOWN. Missing data never becomes affirmative evidence, zero, PASS, or a fabricated economic proxy.
- No silent structure substitution.
- No broker order submission, modification, cancellation, authentication expansion, or other live mutation in this program.
- No paid provider purchase, new commercial contract, or irreversible licensing commitment without a genuine Founder blocker escalation.
- Exact source-strategy semantics must be preserved when translating an externally documented strategy into ASA.
- A strategy is not product-complete merely because it emits PASS.
- UI simplicity must not erase provenance or uncertainty; advanced evidence must remain inspectable.
- Paper/modeled results must never be represented as actual brokerage fills or realized returns.

## Autonomous operating model

### Worker behavior

The worker MUST:

1. Read current main before each ticket and never assume this prompt's baseline is still current.
2. Read accepted architecture/governance relevant to the touched boundary.
3. Inspect open issues against current code before relying on them.
4. Implement the smallest coherent mainline-first change that advances the active sprint.
5. Add tests and diagnostic evidence with the implementation.
6. Open/merge bounded PRs under the active Founder Sprint Delegation when existing governance permits.
7. Continue to the next authorized ticket immediately after merge and verification.
8. Fix root-cause regressions found inside authorized scope without asking the Founder.
9. Reopen a prior sprint automatically when observation evidence falsifies its acceptance claim.
10. Keep working on independent later-sprint scope while a prior sprint is observation-only or while a bounded correction proceeds in parallel.
11. Escalate to Architect, not Founder, for architecture-boundary questions that are within the authorized product direction.
12. Escalate to Founder only for the genuine Founder blockers below.

Do not stop merely because:
- a market session has not yet occurred;
- an observation window is pending;
- a PR merged and another authorized ticket is ready;
- a test exposes an in-scope defect;
- implementation details require choosing among reversible, architecture-consistent alternatives;
- a stale issue/document disagrees with current main and the conflict can be resolved by repository evidence.

### Genuine Founder blocker definition

A Founder escalation is permitted only when continuing would require one of these:

1. **Product-direction choice:** two materially different user-facing products or strategy semantics are both plausible and repository evidence does not select one.
2. **Money/legal/vendor commitment:** purchase of paid data, a new commercial contract, licensing restriction, or materially increased recurring spend.
3. **Broker/live authority:** live broker mutation, credentials/permissions expansion, order placement/cancel/modify, or a change to the constitutional no-mutation boundary.
4. **Deployment/destructive authority:** a Founder-only deployment action, destructive production mutation, irreversible migration, or unrecoverable deletion.
5. **Governance conflict:** accepted/frozen governance genuinely conflicts with this Founder-authorized program and cannot be reconciled by normal architecture interpretation.
6. **Scope expansion:** the only truthful fix would materially change the end product beyond these five sprints rather than merely implement them.

Before escalating, the worker must write a compact blocker packet containing: verified facts, exact blocked outcome, alternatives, reversible steps already attempted, and the smallest Founder decision required.

“Founder authorization required” is **not** by itself a blocker when this program already authorizes the work.

## Semi-parallel pipeline

The five sprints are sequential in product dependency but **not serial in calendar time**.

A sprint can occupy one of these states:

- `IMPLEMENTING`
- `IMPLEMENTATION_COMPLETE_AWAITING_OBSERVATION`
- `OBSERVATION_PASS`
- `REOPENED_CORRECTION`
- `CLOSED`

### Promotion to observation-pending

A sprint may enter `IMPLEMENTATION_COMPLETE_AWAITING_OBSERVATION` when:
- all code/docs/tests for its current acceptance claim are merged on main;
- deterministic/local validation is green;
- no known correctness blocker remains;
- the only remaining evidence requires the next eligible market session, provider refresh, or forward-time observation.

That state **releases implementation capacity immediately**. The next sprint may start without waiting for the observation.

### Observation collection

Where practical, observation must be automated or reduced to a deterministic command/artifact:
- capture exact main SHA;
- capture timestamp/session;
- capture cohort/universe;
- capture funnel counts and typed reasons;
- capture provider attempts/coverage;
- capture exact strategy/structure outcomes;
- persist sanitized evidence in the repository or designated production evidence artifact.

Do not use a human waiting period as project management.

### Failed observation

If observation fails:
1. change the prior sprint to `REOPENED_CORRECTION`;
2. classify whether the defect is local or shared-foundation;
3. start a bounded correction immediately;
4. continue newer sprint work that does not depend on the broken assumption;
5. pause only the dependent path if the failure invalidates a shared foundation;
6. rerun the observation on the corrected exact main.

### Work-in-progress limit

Default:
- up to **2 implementation/correction workstreams** at once;
- any number of observation-only waits/collectors;
- prioritize a reopened correctness defect over cosmetic later-sprint work;
- never allow parallel work to create two authorities for the same data, semantics, or persistence domain.

## Merge and review behavior

Use the repository's current risk-scaled process exactly. Existing Founder Sprint Delegation governs mechanical implementation merges where active. Any mandatory R3 independent review, Architect approval, or verification that current governance requires must still occur; obtain those reviews autonomously from the appropriate role/reviewer and continue immediately when they pass. A required non-Founder review is not a Founder blocker and is not a reason to ask the Founder for routine approval.

In addition to any mandatory risk-floor review, Architect escalation is required before proceeding on an affected path when implementation reveals:
- a new subsystem/authority;
- ownership transfer;
- canonical identity/model change;
- material schema/migration semantics;
- strategy-ID branching in generic layers;
- source-of-truth change;
- security/credential boundary;
- increased risk class;
- conflict with accepted architecture.

Do not ask for per-PR Founder approval when the work is already inside this program and current delegation permits the merge. Do not claim that this program waives a governance review floor; no such waiver is granted here.

## Program success metric

Primary metric: **Actionable Opportunity Yield (AOY)**

AOY is the number of complete, currently actionable proposals ASA can present per eligible market session **without lowering quality gates**. It is not a target to maximize blindly. Every non-actionable candidate must remain explainable through typed funnel outcomes.

Supporting metrics:
- evaluation coverage;
- unexplained-drop count (target zero);
- strategy evaluation completion rate;
- constructible-structure rate after qualifying signals;
- stale/unknown/provider-limited rates by capability;
- median age of actionable evidence;
- user-visible trade completeness;
- tracked opportunity count and forward outcome coverage.

## Product definition of “done”

For an options opportunity, “done” means ASA can answer:
- what strategy qualified;
- why it qualified;
- what exact contracts/legs are proposed;
- buy/sell side, strike, expiration, quantity/ratio;
- current bid/ask/mid or truthful absence;
- modeled debit/credit;
- bounded loss/profit/breakeven where mathematically well-defined;
- payoff visualization with explicit assumptions;
- evidence timestamp/freshness;
- liquidity/constructibility;
- what could invalidate the thesis;
- expandable technical evidence.

For a stock opportunity, “done” means ASA can answer:
- instrument;
- strategy;
- direction/action;
- why now;
- evidence/freshness;
- relevant sizing/allocation semantics if strategy-defined;
- invalidation/unknown reasons;
- expandable technical evidence.

## Sprint transition rules

- S2 may begin when S1 is implementation-complete and only market observation remains.
- S3 may begin when the options trade-card path is merged and usable; S2 observation/usability corrections may continue in parallel.
- S4 may begin once at least one options strategy and one stock strategy traverse their full user-facing path.
- S5 may begin as soon as stable opportunity identities exist and can be forward-observed; it may collect outcomes while S4 continues adding strategies.
- If a later sprint exposes a foundational defect in an earlier sprint, reopen the earlier sprint rather than papering over it.

## No-lull rule

When there is authorized, dependency-safe work available, the worker continues. Observation waiting is never itself a reason to stop the program.

## Closure

The program closes only when all five sprint prompts meet their own closure criteria, all observation-pending claims have either passed or been explicitly downgraded, and no open correction materially undermines the options-first product objective.
