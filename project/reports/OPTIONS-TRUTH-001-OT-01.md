# OPTIONS-TRUTH-001 — OT-01 source-semantics audit

Baseline: `main@7957fc7ba0ddd6b58a7bfc27f93445cf7e593fdb`  
Operational issue: [#457](https://github.com/jaiaFoster/ASA/issues/457)  
Pinned source: `jaiaFoster/Stonk@5f3fec846f70e9739cf3f15695fd587f0604344c`

The authoritative machine-readable discrepancy table is
[`OPTIONS-TRUTH-001-OT-01.json`](OPTIONS-TRUTH-001-OT-01.json). It covers all
eight required dimensions for Earnings Calendar `1.2.0`, Forward Factor
`1.3.0`, and Skew Momentum `2.0.1-research`.

## Result

- Clear implementation errors against accepted strategy definitions: **0**.
- Unresolved product-changing ambiguity: **0**.
- Runtime changes: **none**.
- Silent structure substitution: **none**.
- Invented lifecycle/exit policy: **none**.

The apparent source differences are governed refinements rather than defects:

- Earnings Calendar's 30 ± 5 day gap and coarse supplemental-volume treatment
  were frozen in Issue #236 and PR #254.
- Forward Factor's raw-front-IV naming plus confirmed-earnings exclusion was
  deliberately frozen in PR #253 because the source does not specify a
  reproducible earnings-premium removal method.
- Skew Momentum v2 research policy supersedes the legacy v1 score model under
  the Founder decision recorded in Issue #255.

Unspecified exit behavior remains fail-closed: Forward Factor and Skew Momentum
declare no lifecycle; Earnings Calendar declares only opportunity observation
states and no exit or brokerage action.

## Self-review

This ticket adds evidence and a regression guard only. It does not change a
strategy contract, manifest, formula, gate, provider path, runtime path, or
broker authority. The artifact pins source and accepted strategy revisions and
contains no credentials or provider payloads.
