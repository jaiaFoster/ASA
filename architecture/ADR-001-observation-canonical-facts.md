<!-- Repository path: docs/architecture/decisions/ADR-001-observation-canonical-facts.md -->

# ADR-001: Observation & Canonical Fact Model

**Status:** Accepted
**Date:** 2026-07-20

## Context

`ARCHITECTURE_VISION.md` establishes Observation and Canonical Fact as distinct architectural concepts and requires that ASA account for provider disagreement, confidence, and provenance rather than assume a single source of truth (see "Current Principles" and "Providers are not assumed to agree"). `CONSTITUTION.md` Law 1 ("Facts before opinions") and Law 2 ("Reality is uncertain") require these concepts to remain structurally distinct and require every held fact to carry confidence and provenance. `DOMAIN_GLOSSARY.md` already defines Observation, Canonical Fact, Confidence, and Provenance at a conceptual level; this ADR makes that model concrete enough to implement against.

No prior ADR exists for this decision. This is the foundational data model every layer above the Observation Layer depends on.

## Decision

**Observation** is an immutable, append-only record of what a specific Provider reported, at a specific time, about a specific real-world data point. An Observation is never edited or deleted once written. A correction from a Provider is represented as a new Observation, never as a mutation of an existing one.

Every Observation carries, at minimum:
- **Provider identity** (see ADR-002) — who reported this.
- **Effective time** — when, in the real world, the observed fact holds or held.
- **Recorded time** — when ASA received and stored this Observation.
- **Value** — the reported data point, already structurally normalized into ASA's schema for that Observation type (see ADR-002; this is a structural transform, not an interpretive one — the reported value itself is not altered).

**Canonical Fact** is ASA's current best-understanding record for a given real-world data point, derived by reconciling one or more Observations — potentially from multiple, disagreeing Providers, and potentially arriving over time. A Canonical Fact is **versioned**: each new reconciliation that changes the resolved value produces a new version, and prior versions are retained permanently. A Canonical Fact version is immutable once written; it is never recomputed after the fact, even if the reconciliation logic used to produce later versions subsequently changes (see Consequences).

**Reconciliation philosophy:** when Observations disagree, ASA resolves them deterministically using **provider priority combined with a confidence input**, not simple last-write-wins and not unweighted majority vote. Concretely:
- Each Provider carries a configured priority ranking, used as the primary tiebreaker among current, non-stale Observations.
- Each Canonical Fact version carries a Confidence value reflecting agreement across contributing Observations: multiple independent Providers agreeing raises confidence; a single-Provider or conflicting Observation set lowers it.
- The exact scoring formula and provider priority table are configuration, not architecture, and are intentionally not fixed by this ADR (see Open Questions) — but the *inputs* to the function (priority, agreement, staleness) and the *determinism requirement* (same Observation set always reconciles to the same Canonical Fact version) are fixed here and are binding.

**Provenance:** every Canonical Fact version references the specific Observation(s) that produced it, including their Provider identities. This is what makes reconciliation auditable.

**Confidence is internal; Provenance is external.** The Confidence value a Canonical Fact version carries is an **internal attribute of reconciliation**: it is an input to downstream evidence-confidence aggregation (ADR-003) and to reconciliation itself, not a number ASA presents to users as a standalone quality claim. **Provenance, by contrast, is a first-class, externally visible concept.** Any API that exposes a Canonical Fact or a Recommendation must expose that record's complete provenance, with drill-down capability showing, at minimum:

- the contributing Providers (every Provider whose Observations participated in reconciliation),
- the selected Provider (whose Observation the resolved value was taken from, where applicable),
- provider disagreements (which Providers reported conflicting values, and what they reported),
- the relevant timestamps (effective time, recorded time, and reconciliation time),
- reconciliation metadata (the priority/agreement/staleness inputs that drove the resolution).

"Externally visible" here binds future API design without designing any API in this ADR: whatever surface eventually exposes Facts or Recommendations must be able to answer "where did this number come from, who disagreed, and when" from the stored record alone. The domain model must therefore carry complete provenance structurally on every Canonical Fact version — this is not an optional annotation.

**Historical replay:** because both Observations and Canonical Fact versions are immutable and timestamped with both effective time and recorded time, ASA can reconstruct "what did we believe as of time T" for any past T. This is a required capability of the model, not an incidental byproduct — it is what makes Strategy evaluation reproducible over historical data (Constitution Law 7).

**Determinism is a write-time guarantee, not a re-derivation guarantee.** "Same Observation set always reconciles to the same Canonical Fact version" describes the reconciliation function at the moment it runs, given whatever provider-priority configuration and confidence inputs are in effect at that time. It does not mean that re-running reconciliation *today*, against *yesterday's* Observation set, is guaranteed to reproduce *yesterday's* stored Canonical Fact version — provider priority and confidence-scoring configuration are not versioned by this ADR (see Open Questions and ADR-002), so they may differ between "then" and "now." Historical replay does not depend on this kind of re-derivation matching: replay is a **lookup** of the Canonical Fact version that was actually stored at the relevant time, not a **recomputation** of reconciliation against current configuration. An implementer should not build a test that reconciles historical Observations under today's configuration and asserts the result matches the historically stored version — that test would fail on any configuration change and would not indicate a defect.

## Alternatives Considered

1. **Single mutable "Fact" table, no Observation/Canonical Fact split.** Rejected: conflates raw evidence with ASA's interpretation of it, directly violating Constitution Law 1, and destroys the ability to re-reconcile or audit disagreement after the fact.
2. **Observations only, with Canonical Fact computed on-the-fly at query time (no persisted version).** Rejected: if reconciliation logic changes later, historical queries would silently reconcile differently than they did at the time, breaking historical replay and making Strategy evaluation non-reproducible (Constitution Law 7). A persisted, immutable version is required for determinism.
3. **Last-write-wins reconciliation.** Rejected: "last" depends on arrival order, which is not guaranteed to be consistent across environments or replays, making reconciliation non-deterministic. Also fails to make use of Confidence or Provenance, which the Vision and Constitution both require to be meaningful, not decorative.
4. **Provider-priority-and-confidence-weighted reconciliation with immutable versioning (chosen).** Deterministic given a fixed Observation set and configuration; supports historical replay; gives Confidence and Provenance real architectural function rather than cosmetic fields.

## Consequences

- Every layer above Canonical Fact (Indicators, Strategies) must reference a specific Canonical Fact **version**, not "the current value," when reproducibility matters — this is what makes historical replay possible.
- Storage cost is higher than a mutable-fact model: both full Observation history and full Canonical Fact version history are retained indefinitely (retention policy is out of scope here — see Open Questions).
- A change to the reconciliation function itself is an architectural change (a new ADR), and per this ADR's immutability rule, it applies only to future reconciliations — it never retroactively rewrites already-written Canonical Fact versions. This preserves replay integrity across reconciliation-logic changes, at the cost of the historical record reflecting whatever reconciliation logic was in effect at the time.
- Provider priority configuration becomes a governance-relevant input (it can change which Provider "wins" a disagreement) even though it is not itself architecture; it should be tracked as configuration state, not buried in code.

## Open Questions

- The exact Confidence-scoring formula (specific weighting of agreement, priority, and staleness) is deliberately left unspecified here as configuration/implementation detail, provided it remains deterministic. A future engineering document, not an ADR, should specify the initial formula.
- Data retention policy for Observation and Canonical Fact history (how long is "permanently," in practice) has cost and possibly compliance implications and is not decided here; it may require Founder input if retention cost becomes material to the product's cost structure, rather than being a purely architectural decision.
- This ADR assumes reconciliation runs synchronously as new Observations arrive rather than in scheduled batches; the operational trigger for reconciliation is an implementation detail left to engineering, not fixed here.

## Documentation Impact

`ARCHITECTURE_VISION.md`'s Open Questions section currently asks: *"The precise mechanism by which the Canonical Fact Layer resolves disagreement between providers... has not been settled by an ADR."* This ADR settles it. Recommend removing that Open Question from `ARCHITECTURE_VISION.md` and replacing it with a reference to this ADR.

Recommend a minor clarifying edit to `DOMAIN_GLOSSARY.md`'s **Observation** entry: "raw provider evidence" should be understood as raw in *content* (the reported value is never altered) but structurally normalized into ASA's schema at the point of recording (see ADR-002). The current Glossary wording does not contradict this, but a reader could plausibly misread "raw" as "untransformed in every sense." Recommend appending a one-clause parenthetical to the existing definition rather than rewriting it.

## Revision note (ASA-CORE-001)

This ADR originally described Confidence and Provenance side by side without distinguishing their visibility. This amendment clarifies that reconciliation confidence is an internal attribute (consumed by reconciliation and downstream evidence-confidence aggregation, not presented as a user-facing quality score), and elevates Provenance to a first-class, externally visible concept with a binding drill-down requirement on any future API exposing Canonical Facts or Recommendations. No reconciliation semantics changed; the amendment constrains what the stored record must be able to answer, and therefore what the domain model must carry.

## References

- `CONSTITUTION.md`, Laws 1, 2, 3, 7
- `ARCHITECTURE_VISION.md`, "Current Principles" (Observation/Canonical Fact distinction; provider disagreement), "Open Questions"
- `DOMAIN_GLOSSARY.md`: Observation, Canonical Fact, Confidence, Provenance, Provider
