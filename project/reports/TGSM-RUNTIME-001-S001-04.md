# TGSM-RUNTIME-001 — S001-04 composition

Base: `main@f3aaf18` (S001-03 and the Founder-merged TGSM merge-gate correction).
Ticket: S001-04. Assigned Worker: implementation-worker. Manager stop status: CLEAR.

## Outcome

S001@1.0.0 declares only historical bars and two named derived facts under
`StructureKind.NONE`. Its provider-neutral historical demand uses the existing
subject planner. The binding projects sealed historical series and the latest
completed-month observation as canonical facts, then materializes
`trailing_12m_total_return@1.0.0` and
`sma_10m_completed_months@1.0.0` through the existing generic fact composer.
Split-only, raw, incomplete, or unusable total-return evidence remains typed
UNKNOWN; no alternative price is substituted.

The generic cohort seam accepts already-prepared read-only subject knowledge
at one decision time. The S001 adapter validates that its payload matches the
sealed canonical and named/versioned derived facts, then ranks the eligible
point-in-time sector cohort before applying strict trend eligibility to the
top three. A missing eligible return cannot be assigned an economic rank.
The adapter is registered with the existing `StrategyRegistry` and runs via
`run_strategies()` over the universe subject. It closes over knowledge only,
not provider, fulfillment, retry, transport, or broker authority. No generic
runtime strategy-ID branch or option resolver was added.

This gate produces selection and trend state, **not** target sleeves,
persistence, production scheduling, or a broker action. Target/defensive
semantics and ledger are S001-05; integrated closure is S001-06. The current
canonical adjustment basis is treated as total-return-capable evidence, not
as a claim that every provider's adjusted-close implementation is equivalent
to an independently verified reinvested total-return index. Production source
fitness remains fail-closed and subject to the existing entitlement boundary.

## Evidence and recovery

- Focused S001 composition/knowledge tests: 9 passed.
- Strategy runtime, analytics, architecture, screening: 1,229 passed.
- Ruff and mypy: green; architecture boundaries: green.
- Replay: identical sealed snapshot yields identical canonical and derived
  knowledge; cohort ranking/selection is deterministic and provider-free.
- Recovery: remove S001 registration/bindings and the generic cohort seam;
  B001/B002 and option strategy production paths are unchanged.
