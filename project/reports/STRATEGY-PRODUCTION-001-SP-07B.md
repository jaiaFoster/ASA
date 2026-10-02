# STRATEGY-PRODUCTION-001 — SP-07B capacity release gate

- Ticket: `SP-07B`
- Basis: production-equivalent fixture transport through the real scheduled
  composition root and the complete configured seven-strategy topology.
- Safety: no live provider calls, credentials, payload retention, or deployment.

## Atomic complete-family gate

| Measure | Result |
|---|---:|
| Active point-in-time membership | 503 subjects |
| Safe per-cycle admission ceiling | 30 subjects |
| Zhan formation pairs admitted / deferred | 0 / 503 |
| Heston formation pairs admitted / deferred | 0 / 503 |
| Provider requests before typed deferral | 0 |
| Partial family materializations | 0 |

The gate compares the complete effective-dated membership before acquisition.
It never combines rotating cohorts or claims source-faithful deciles over a
partial universe. Increasing the ceiling remains a measured capacity decision.

## Release findings

- Complete cross-sectional families are admitted atomically or deferred atomically.
- Capacity refusal occurs before any provider request.
- Every deferred pair carries `CAPACITY_DEFERRED_INCOMPLETE_COHORT`.
- One sibling's missing optional evidence does not abort another strategy.
- Ordinary rotating strategies continue; no hidden family drop or partial ranking occurs.

## Automated proof

`test_complete_family_capacity_gate_defers_before_provider_calls` proves the
503-member point-in-time requirement, zero admission under the safe ceiling,
503 typed Zhan deferrals, and zero provider requests. The Heston due-date path
uses the same registry-driven gate. Existing rolling-window tests still prove
generic request-level refusal and recovery for admitted work.

## Disposition

SP-07B safety gate passes. Current capacity does not authorize a source-invalid
partial cross-sectional result: Zhan/Heston truthfully defer until an atomic
full-membership run is admitted. Real provider/session behavior and any raised
atomic ceiling remain part of the Founder-only SP-08A production proof.
