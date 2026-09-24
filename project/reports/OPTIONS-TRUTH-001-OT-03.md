# OPTIONS-TRUTH-001 — OT-03 earnings cohort proof

Baseline: `main@9ede0224b8e70776c93861115e270a3b4b415809`  
Operational issue: [#461](https://github.com/jaiaFoster/ASA/issues/461)

## Implementation state

`tools/options_truth/earnings_cohort.py` is the bounded, deterministic capture
command. It verifies `/version` against the requested exact SHA, traverses the
complete active Earnings Calendar latest-state page set, selects the nearest
recent/next events and a bounded sample with missing event evidence, then joins
each row to its OT-02 option funnel.

The sanitized artifact records event/expiration/gap evidence, demand-level
acquisition and missing reasons, gate outcomes, verdict, structure status,
terminal state, classification totals, and a deterministic cohort checksum.
It never records the API token, raw provider payloads, or broker data.

## Closed classification

Each candidate is classified as exactly one of:

1. `asa_defect`
2. `provider_entitlement_or_coverage`
3. `legitimate_temporal_or_policy_absence`
4. `genuinely_unknown_or_unannounced_event`
5. `true_strategy_rejection`
6. `structure_or_market_unavailability`
7. `actionable_opportunity`
8. `legitimate_unknown`

## Observation state

Implementation is complete. Actual cohort capture requires deployment of an
exact main SHA containing OT-02 and this collector. Deployment remains
Founder-only under the program. Until that proof runs, OT-03 remains
`IMPLEMENTATION_COMPLETE_AWAITING_OBSERVATION`; no production result is claimed.
