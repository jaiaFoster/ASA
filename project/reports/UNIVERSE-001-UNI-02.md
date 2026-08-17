# UNIVERSE-001 / UNI-02 — Root-Cause Scale Correction

## Failed scale gate

UNI-01 measured 2,515 option-chain calls for a naive 503-subject, all-three-strategy
cycle. The established 30-subject control uses 150 option calls.

## Root cause and owner

Forward Factor and Skew Momentum legitimately require option evidence to evaluate.
Removing those requests with a generic prefilter would alter strategy semantics; no
declared cheap eligibility rule can prove those subjects ineligible. Earnings Calendar
already avoids phase-two contract acquisition when its declared earnings/expiration
requirements reject a subject.

The defect is therefore a cycle-capacity/fairness problem owned by generic screening
scheduling, not a strategy, provider, or option normalizer.

## Correction

`screening.universe_cohorts.plan_universe_cohort` deterministically partitions the
effective-dated membership into bounded, symbol-sorted cohorts. A full sweep covers each
member exactly once. Cohort selection carries the membership source revision and is replay
stable; it contains no strategy identity, score, threshold, provider, or heuristic ranking.

At the current proven capacity of 30 subjects:

- 503 members become 17 cohorts (16 × 30, 1 × 23);
- a cycle remains bounded at at most 270 provider calls / 150 option calls under the
  UNI-01 production-equivalent topology;
- naive one-cycle acquisition is avoided without fabricating evaluations or changing
  strategy policy;
- total full-sweep work is preserved honestly rather than hidden.

Production activation is deliberately deferred to UNI-03. The existing 30-symbol
production universe remains unchanged in this ticket.
