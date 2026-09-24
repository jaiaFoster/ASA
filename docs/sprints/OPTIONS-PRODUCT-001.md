# OPTIONS-PRODUCT-001 — Autonomous Sprint Prompt

**Purpose:** turn trustworthy option-strategy results into complete, understandable trade proposals a user can act on without separately reconstructing the position.

Read the program prompt first. OPTIONS-TRUTH-001 may still be observation-pending or in bounded correction.

## Product standard

The default experience answers **“What trade is ASA proposing?”**  
The expandable experience answers **“Why?”**

A PASS without a resolvable, truthful structure is not a complete user-facing trade proposal.

## Work packages

### OP-01 — Canonical trade proposal contract
Build on existing `ExecutableStructureAssessment`, exact legs, modeled entry economics, and P&L capabilities. Define the minimum provider-neutral presentation contract for an options trade:
- underlying;
- strategy/version;
- structure;
- exact leg identities;
- buy/sell;
- call/put;
- strike;
- expiration;
- quantity/ratio;
- bid/ask/mid and quote time;
- modeled net debit/credit;
- capital/max loss/max profit/breakeven only when mathematically supportable;
- constructibility/liquidity;
- evidence snapshot identity;
- assumptions/model version;
- plain-language rationale and risk/invalidation notes.

Do not duplicate financial truth into the UI.

### OP-02 — Payoff model
Provide a deterministic payoff/model API from the same exact legs. Distinguish:
- deterministic terminal-expiration payoff;
- model-dependent pre-expiration P&L;
- undefined/unbounded quantities.

Never label a model assumption as guaranteed return. Add pinned vectors for supported structures.

### OP-03 — Trade card UI
Replace/augment audit-first detail presentation with a user-first trade card. It must visibly show exact legs and modeled economics. Advanced evidence remains one interaction away.

### OP-04 — Payoff visualization
Render a clear payoff diagram from the canonical model output. Include current underlying/entry reference where useful and label assumptions. Accessibility and non-graph textual values are required.

### OP-05 — Failure experience
For a promising result that cannot become a trade, show the exact blocker:
- missing quote/IV/Greek;
- no eligible expiration;
- no matching strike/delta;
- spread/liquidity;
- stale evidence;
- earnings uncertainty;
- unsupported structure.

Do not show a misleading “PASS” as if executable when structure readiness says otherwise. Preserve signal semantics separately from execution readiness.

### OP-06 — Trade tracking affordance
Add a non-broker-mutating “track” action or equivalent immutable watch record if architecture permits within existing persistence. Tracking is not an order and must not imply fill.

### OP-07 — Founder-utility observation
On real current results, prove at least the complete trade-card path for constructible opportunities and typed failure presentation for nonconstructible ones. If the market yields no qualifying opportunity during the window, fixture/replay proof remains necessary but the sprint stays observation-pending until a real qualifying opportunity traverses the path or the program records a bounded no-signal observation.

## Acceptance

A user can open an actionable option result and determine the exact intended trade without another analytical application. The UI must make uncertainty obvious and retain full evidence drill-down.

No broker mutation. No invented return claims. No duplicated provider acquisition.

## Transition

When canonical trade proposal + UI + payoff path are merged and only live observation/usability evidence remains, begin STOCK-PRODUCT-001. Reopen in parallel if observation reveals a correctness defect.
