# ASA-RELIABILITY-RESEARCH-001 closure candidate

## DATA-RELIABILITY-001

- REL-01 introduced demand-aware causal census attribution without pretending
  subject-scoped provider attempts are strategy-scoped.
- REL-02 fixed false freshness from persistence recency.
- REL-03 separated Forward Factor signal validity from earnings clearance and
  made execution readiness fail closed.
- REL-04 closed the bounded evidenced ASA-defect inventory.
- REL-05 classification: **INCONCLUSIVE** pending one authorized current
  production census. Historical 574/1,509 missing-data counts remain explicitly
  historical. The external capability matrix is recorded; no provider was
  purchased or integrated.

## TGSM-RESEARCH-001

- Evidence: **DATA_LIMITED**.
- Immutable preregistration and experiment identity/replay contracts exist.
- Production S001 logic is reused exactly; no second implementation exists.
- B0–B4/S1, robustness, and OOS: not run because evidence is unqualified.
- H1–H5: **INCONCLUSIVE**.

## Preserved invariants

Strategies remain provider-blind. Canonical evidence precedes named/versioned
facts. ASA retains one market-data authority. No strategy-ID runtime branch,
silent fallback, duplicate S001 implementation, production S001 semantic
change, or broker mutation was introduced.

The exact final merged-main SHA, complete validation totals, and any required
production remeasurement authorization are recorded after this closure
candidate merges and exact-main verification completes.

Candidate verification: Python **3,432 passed / 48 skipped**; frontend 7
passed plus generation/lint/type/build; legacy UI 14 passed plus syntax/lint;
changed-scope Ruff and mypy green; Lean pre-push green. Full-suite validation
also caught and corrected an initial package-placement error: research identity
and S001 reuse seams now live under `strategy_runtime`, not the restricted
portfolio `simulation` bounded context.
