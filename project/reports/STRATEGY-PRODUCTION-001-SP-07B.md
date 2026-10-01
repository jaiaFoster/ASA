# STRATEGY-PRODUCTION-001 — SP-07B capacity release gate

- Ticket: `SP-07B`
- Basis: production-equivalent fixture transport through the real scheduled
  composition root and the complete configured seven-strategy topology.
- Safety: no live provider calls, credentials, payload retention, or deployment.

## Measured cycle

| Measure | Result |
|---|---:|
| Due strategy/subject pairs | 164 |
| Attempted / completed / failed | 164 / 164 / 0 |
| Declared strategy capability demands | 738 |
| Unique planned fact requests | 382 |
| Deduplicated equivalent demands | 356 |
| Provider requests | 292 |
| Provider capacity deferrals | 0 |
| Unique option-chain requests | 150 |
| Unique historical-panel requests | 30 |
| Local fixture cycle duration | 2.802 seconds |

The duration is local fixture evidence, not a claim about provider latency.
The remaining difference between unique planned requests and provider requests
is typed unsupported optional capability evidence; it is not silently dropped.

## Release findings

- One subject plan owns acquisition for all strategies sharing that subject.
- Exact equivalent demands are deduplicated before provider acquisition.
- Provider budgets and rolling-window refusals remain generic and typed.
- Every due pair is attempted or receives an explicit typed evidence blocker.
- One sibling's missing optional evidence does not abort another strategy.
- No strategy-specific throttling, hidden strategy drop, or universal preparation
  exception is present.

## Automated proof

`test_production_universe_topology_has_no_universal_preparation_failure`
exercises the full configured topology and asserts the sanitized
`cycle_capacity_release_summary`. Existing rolling-window tests prove generic
capacity refusal and later-window recovery. The summary records per-capability
demand and unique-request counts without symbols, payloads, or secrets.

## Disposition

SP-07B release gate passes for the configured cohort under production-equivalent
transport. Real provider/session behavior remains the Founder-only SP-08A
deployment proof.
