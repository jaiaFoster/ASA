# STOCK-PRODUCT-001 — Autonomous Sprint Prompt


## Founder Sprint Delegation record

- **Sprint:** `STOCK-PRODUCT-001`
- **Founder authorization:** explicit, 2026-09-23, as part of ASA-OPTIONS-TO-OUTCOMES-2026Q4
- **Governance mechanism:** GOV-AMD-001 Amendment 013 (Founder Sprint Delegation)
- **Delegate:** ROLE-WORKER, instance `implementation-worker`
- **Approved tickets:** `SP-01`, `SP-02`, `SP-03`, `SP-04`, `SP-05`, `SP-06`
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
**Purpose:** give stock/ETF strategies the same “actionable, understandable proposal” product treatment as options without forcing stocks into option-specific abstractions.

Read the program prompt first.

## Scope

Use existing stock foundations (including B001/B002 and S001/TGSM where operationally representable). Do not restart TGSM research. Missing historical research data does not block creating a truthful current product path.

## Work packages

### SP-01 — Stock proposal contract
Define/reuse a provider-neutral stock/ETF opportunity presentation contract:
- canonical instrument;
- strategy/version;
- action/direction;
- evidence time/freshness;
- relevant signal metrics;
- target/allocation semantics only when strategy-defined;
- invalidation/UNKNOWN reason;
- rationale;
- provenance.

Do not fabricate expected return or sizing if strategy semantics do not define them.

### SP-02 — Runtime/API projection
Expose stock strategy outcomes through generic runtime/API projection with no strategy-ID branches. Preserve asset-specific fields without contaminating option contracts.

### SP-03 — Stock UI
Create a stock opportunity experience parallel in usability to the options trade card:
- what instrument;
- what action;
- why now;
- what evidence;
- what would invalidate it;
- what allocation/weight if strategy legitimately emits one.

### SP-04 — Scheduled/current operation
Ensure authorized current stock strategies can run on an appropriate live/current schedule without creating a second acquisition authority. Keep data requirements capability-driven.

### SP-05 — Cross-asset shell
Present Options and Stocks as coherent ASA product surfaces with shared concepts (strategy, evidence, freshness, actionable state, explanation) and asset-specific execution detail.

### SP-06 — Observation
Capture current stock/ETF strategy outputs and verify complete proposal/typed-unknown behavior on exact main.

## Acceptance

At least one options strategy and one stock/ETF strategy traverse end-to-end user-facing paths from shared evidence to understandable current proposal. No broker mutation and no false economic claims.

## Transition

When this product parity is merged and current observation is the only remaining proof, begin STRATEGY-LIBRARY-001.
