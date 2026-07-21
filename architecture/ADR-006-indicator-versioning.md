<!-- Repository path: architecture/ADR-006-indicator-versioning.md -->

# ADR-006: Indicator Versioning and Immutability

**Status:** Accepted
**Date:** 2026-07-20

## Context

`CONSTITUTION.md` Law 3 ("one calculation, one home") establishes Indicators as shared, single-implementation calculations, and Law 7 requires deterministic, reproducible evaluation through the Strategy Layer. ADR-001 established that Canonical Facts are versioned and immutable specifically so that historical replay and reproducibility hold. ADR-003 requires a Strategy's "Supporting Indicators" to reference the Canonical Fact version(s) an Indicator value was computed from, but neither ADR-001 nor ADR-003 states whether an **Indicator value itself** is versioned and immutable, or recomputed in place against whatever Canonical Fact is currently considered "current." Left unresolved, this creates a real reproducibility gap: two Opportunities produced at different times could cite the "same" Indicator by name while it silently meant different underlying values, which is precisely the non-reproducibility ADR-001's replay model was built to prevent one layer down. This ADR closes that gap.

## Decision

An **Indicator value** is versioned and immutable, using the same discipline ADR-001 applies to Canonical Facts. An Indicator version is produced whenever either of its two possible triggers occurs:

- one or more of its underlying Canonical Fact versions changes (a new Canonical Fact version is written that this Indicator depends on), or
- the Indicator's own calculation logic changes (a new implementation or formula version is deployed).

Each Indicator version references the exact Canonical Fact version(s) it was computed from and the exact calculation-logic version that computed it, mirroring how a Canonical Fact version references the Observations it was reconciled from (ADR-001). Once written, an Indicator version is never mutated or silently recomputed; a change in either trigger produces a new version, and prior versions remain part of the historical record.

**What a Strategy or Guardrail actually references.** When ADR-003 requires a Strategy's "Supporting Indicators" to reference Canonical Fact versions, that requirement is now understood as flowing through this ADR: a Strategy (or Guardrail, per ADR-005) pins to a specific **Indicator version**, and that Indicator version in turn pins to the Canonical Fact version(s) beneath it. A Strategy or Guardrail evaluation is reproducible only if every Indicator it used is identifiable by version, not merely by name plus "whatever the value was at the time" — the latter is exactly the ambiguity this ADR removes.

**Recomputation timing is not fixed here.** Whether an Indicator recomputes synchronously the moment a dependency's Canonical Fact version changes, or lazily the next time a Strategy or Guardrail requests it, is an operational/engineering decision, not an architectural one — the versioning and immutability discipline above holds either way, because correctness depends only on "a given Indicator version is always computed from the same, cited Fact versions and logic version," not on when that computation happens.

## Alternatives Considered

1. **Indicators as pure functions, recomputed on demand from "current" Canonical Facts, with no persisted version.** Rejected: this is exactly the gap that motivated this ADR — two Strategy or Guardrail evaluations referencing the same Indicator name at different times could silently operate on different underlying values if the dependent Canonical Fact changed in between, breaking reproducibility (Constitution Law 7) without anything in the Opportunity record revealing that this happened.
2. **Indicators versioned only when calculation logic changes, not when underlying Facts change.** Rejected: this would still allow the same Indicator version to silently mean different values as Facts are revised underneath it, which is the more common and more consequential case (Facts change far more often than calculation logic does) and is the specific failure mode this ADR exists to close.
3. **Indicators versioned and immutable on both triggers, referencing both dependency Fact versions and calculation-logic version (chosen).** Matches ADR-001's existing, already-accepted model one layer up, and closes the reproducibility gap completely: any two references to "this Indicator version" are guaranteed to mean the same value, unconditionally.

## Consequences

- Indicator storage now requires a version history, not just a current-value cache, mirroring the storage cost ADR-001 already accepted for Canonical Facts. This is an explicit, accepted cost of maintaining Law 7 reproducibility through the Indicator Layer, not an oversight.
- Every Strategy and Guardrail implementation must resolve and cite a specific Indicator version at evaluation time, rather than reading a mutable "current" value — this is a discipline requirement on Strategy and Guardrail authors, in addition to the Evidence/Assumptions discipline ADR-003 and ADR-005 already impose.
- A change to an Indicator's calculation logic is now, by this ADR, an event that must produce a new Indicator version rather than silently altering the meaning of an existing one — this makes Indicator logic changes auditable in the same way Canonical Fact reconciliation-logic changes already are under ADR-001.
- Because recomputation timing (eager vs. lazy) is left unspecified, two different valid implementations could have different latency characteristics for "how fresh is the Indicator a Strategy sees," without either one being architecturally incorrect — this is intentional, but worth knowing before implementation starts (see Open Questions).

## Open Questions

- Recomputation timing (synchronous on Fact-version change vs. lazy on request) is left to engineering judgment, per this ADR. If the two approaches turn out to produce materially different Strategy behavior in practice (for example, a Strategy evaluated against a stale Indicator version because recomputation hadn't yet occurred), that would warrant a follow-up decision fixing the timing — not a change to the versioning/immutability model itself.
- Retention policy for Indicator version history is not addressed here and inherits the same open question already flagged in ADR-001 for Observation and Canonical Fact retention.
- Whether an Indicator version should also record which Strategies or Guardrails actually consumed it (a reverse reference, for impact analysis when an Indicator's logic changes) is not decided here and is left as a possible future refinement.

## Documentation Impact

Recommend a clarifying cross-reference be added to `DOMAIN_GLOSSARY.md`'s **Indicator** entry noting that Indicator values are versioned and immutable per this ADR, to prevent a future reader from assuming Indicators are simple mutable current-value calculations the way the entry's current wording could otherwise be read. No change to `ARCHITECTURE_VISION.md` or `CONSTITUTION.md` is required; this ADR applies existing Law 3 and Law 7 discipline to a layer that had not yet received it, rather than introducing new principles.

## References

- `CONSTITUTION.md`, Laws 3, 7
- `ARCHITECTURE_VISION.md`, "Current Principles" (shared Indicators; deterministic Strategy evaluation)
- `DOMAIN_GLOSSARY.md`: Indicator, Canonical Fact
- ADR-001 (Canonical Fact versioning and immutability model, extended here to Indicators)
- ADR-003 (Strategy "Supporting Indicators" requirement, now understood as pinning to Indicator versions)
- ADR-005 (Guardrails also consume Indicators and inherit this versioning requirement)
