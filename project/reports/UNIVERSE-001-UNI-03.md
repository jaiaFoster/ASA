# UNIVERSE-001 / UNI-03 — Staged S&P 500 Rollout

## Rollout state

Scheduled production now selects one deterministic S&P 500 cohort from the
effective-dated membership snapshot. Manual and explicitly supplied universes retain their
existing behavior, preserving the 30-symbol control and bounded test/diagnostic calls.

- Membership revision: `1369213082` (`2026-08-13T15:09:18Z`).
- Members: 503.
- Capacity: at most 30 subjects per scheduled cycle.
- Sweep: 17 cohorts; five normal-session slots advance five cohorts per trading day.
- Per cohort: all three production strategies; at most 90 strategy pairs.
- Selection: actual exchange-calendar slots, including holiday and early-close semantics.
- State: no database cursor; slot-to-cohort mapping is deterministic and replayable.
- Operational diagnostic: source revision, cohort ordinal/count, and subject count; no payloads.

The scheduler does not rank, filter, or infer strategy viability. It bounds required work fairly
and preserves every member exactly once per full sweep. Existing strategy-owned phase expansion
continues to avoid contract acquisition when declared evidence proves a subject ineligible.

## Pre-merge proof

- One production-composition cohort: 30 subjects / 90 pairs.
- Deterministic multi-capability fixture transport; real production orchestration unchanged.
- Result: 90 completed, zero exceptions, zero `missing_data`.
- Full scheduler, membership, cohort, and screening-boundary selection: 153 tests passed.
- Ruff, strict mypy, Lean integrity, Lean entrypoints, and diff validation passed.

## Remaining closure gate

After merge, validate the exact main SHA. Production deployment and a real scheduled-cycle proof
remain Founder-authorized actions. Russell 2000 remains blocked until the S&P 500 rollout passes.
