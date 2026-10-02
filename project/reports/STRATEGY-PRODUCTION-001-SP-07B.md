# STRATEGY-PRODUCTION-001 — SP-07B capacity release gate

- Ticket: `SP-07B`
- Basis: production-equivalent fixture transport through the real scheduled
  composition root and the complete configured seven-strategy topology.
- Safety: no live provider calls, credentials, payload retention, or deployment.

## Measured cycle

Re-measured at the merged SP-07A topology through the real scheduled
composition root (`run_scheduled_refresh(enforce_schedule=True)`, the 30-subject
oldest-first claim path that production runs each tick), with
production-equivalent fixture transport. Reproduction:
`scheduled_screening` cycle summary `cycle_capacity_release_summary`.

| Measure | Production claimed-cohort tick | Legacy approved universe |
|---|---:|---:|
| Due strategy/subject pairs | 120 (30 subjects × 4 cohort strategies) | 104 |
| Attempted / completed / failed | 120 / 120 / 0 | 104 / 104 / 0 |
| Declared strategy capability demands | 570 | 498 |
| Unique planned fact requests | 270 | 262 |
| Deduplicated equivalent demands | 300 | 236 |
| Provider requests | 270 | 262 |
| Provider capacity deferrals | 0 | 0 |
| Unique option-chain requests | 150 | 150 |
| Unique historical-panel requests | 0 | 0 |
| Local fixture cycle duration | 7.247 s | 7.270 s |

- Cohort strategies are Forward Factor, Skew Momentum, Earnings Calendar and
  GXZ (GXZ now rides the production claim path via the shared
  `SP500_COHORT_STRATEGY_IDS` declaration). GXZ returns typed
  `missing_data` under the fixture (no due earnings event), not an exception.
- Historical-panel requests are 0 because no cohort strategy declares
  `HISTORICAL_OPTION_PANEL_V1`; Heston is the only consumer and runs only on the
  complete-family path, which is capacity-deferred (below).
- The fixed-SPX invocation (PUT, PUTY, BXM, SCS, plus the SPY put credit
  spread) is a separate isolated call per tick; the fixture transport models
  equity subjects only, so its request volume (5 pairs, at most one SPX/SPY
  chain set) is not part of this measurement and is observed in SP-08A.
- Durations are local fixture evidence, not provider-latency claims.

## Atomic complete-family gate

| Measure | Result |
|---|---:|
| Active point-in-time membership | 503 subjects |
| Safe per-cycle admission ceiling | 30 subjects |
| Zhan formation pairs admitted / deferred | 0 / 503 |
| Heston formation pairs admitted / deferred | 0 / 503 |
| Provider requests before typed deferral | 0 |
| Partial family materializations | 0 |
| Persisted typed rows per due family | 503 (`MISSING_DATA`, `CAPACITY_DEFERRED_INCOMPLETE_COHORT`) |
| Processing per formation date | once (claim on family + New York formation date) |

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
503 typed Zhan deferrals persisted as rows, and zero provider requests.
`test_production_universe_topology_has_no_universal_preparation_failure` and
`test_default_scheduled_cycle_uses_bounded_sp500_cohort` assert the cycle
summary and the four-strategy claim path. The Heston due-date path
uses the same registry-driven gate. Existing rolling-window tests still prove
generic request-level refusal and recovery for admitted work.

## Disposition

SP-07B safety gate passes: the configured per-tick cohort completes within
measured capacity with zero deferrals, and complete families take the generic
typed deferral. Current capacity does not authorize a source-invalid
partial cross-sectional result: Zhan/Heston truthfully defer until an atomic
full-membership run is admitted. Real provider/session behavior and any raised
atomic ceiling remain part of the Founder-only SP-08A production proof.
