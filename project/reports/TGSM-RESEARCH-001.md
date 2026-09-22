# TGSM-RESEARCH-001 closure

Status: **CLOSED / DATA_LIMITED**.

## Frozen identities and semantics

- S001: `1.0.0`; implementation manifest
  `260e4e046cabe96a50a15a690f316eb3ee133351c8fbd71f0b491eed5ef38573`.
- Evidence qualification:
  `sha256:9d26184530d6a66ca4b107c54f695e7dbce54e49970bb7fab66338cb1dc35a45`.
- Preregistration:
  `sha256:39308729f78df5496d7103747c87211418bcd6f070120d21ea23bb1449dc4cef`.
- Intended period: 2001-01-01 through 2025-12-31, restricted only by
  qualified point-in-time evidence—not shortened after observing results.
- Temporal convention: finalized completed-month evidence, decision after
  availability, effective next eligible session, never same-close execution.
- Evidence: authoritative point-in-time membership; total-return-capable
  sector/SPY evidence; canonical three-month Treasury total return; qualified
  historical sessions. No raw-close, current-membership, ETF, cash, or yield
  substitution.
- Costs: 10 basis points per one-way unit of turnover. B0–B4/S1, H1–H5,
  metrics, robustness grid, and fixed 12-month walk-forward windows are frozen
  in the preregistration.

## Result

Evidence qualification is `DATA_LIMITED`. ASA lacks a sealed qualified corpus
covering authoritative historical sector membership, sector/SPY total returns,
canonical three-month Treasury total return, and historical exceptional
sessions. Consequently B0–B4/S1, robustness, and OOS experiments were not run;
H1–H5 are each `INCONCLUSIVE`. No performance or investment-superiority claim
is supported.

## Engineering proof

The minimal experiment contract records deterministic experiment and result
identities and replays canonically without provider access. The research seam
delegates target construction to the production S001 interpretation and
allocation functions. Identical sealed fixture inputs produce an identical
runtime/research target decision identity. There is no duplicate S001
implementation, provider access, strategy-ID runtime branch, alternate market
data authority, silent fallback, or broker mutation.

The exact closure merge and merged-main validation SHA are recorded by GitHub,
the operational authority, and in the sprint closure evidence after merge.

Closure-candidate validation: Python **3,432 passed / 48 skipped**; frontend 7
passed with generation/lint/type/build; legacy UI 14 passed with syntax/lint;
changed-scope Ruff and mypy green; Lean pre-push green.
