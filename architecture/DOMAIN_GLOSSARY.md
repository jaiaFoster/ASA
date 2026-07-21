<!-- Repository path: architecture/DOMAIN_GLOSSARY.md -->

# ASA Domain Glossary

This document is the canonical vocabulary for ASA's architecture. If a term used elsewhere in this documentation set, in an ADR, or in the codebase conflicts with a definition here, this document wins — file an issue rather than silently using a different meaning.

Terms are listed alphabetically. Each definition states what the term is and, where useful, what it is not.

---

**Canonical Fact**
ASA's current best-understanding record derived from one or more Observations. Versioned: a Canonical Fact may be revised as better information arrives, and its prior versions remain part of the historical record. Not the same thing as an Observation — a Canonical Fact is an interpretation of evidence, not the evidence itself.

**Capability**
A named, discrete unit of analytical function that a Strategy or the platform can draw on — for example, a specific detection or scoring routine offered to the Strategy Layer. A Capability is not itself a Strategy; a Strategy may use one or more Capabilities to evaluate Opportunities. (See Open Questions below — the precise boundary between a Capability and an Indicator has not yet been fixed by ADR.)

**Confidence**
A structured measure of how strongly ASA believes a given Observation, Canonical Fact, or Indicator value is accurate. Confidence is carried alongside data, not implied by its presence — per Constitution Law 2, nothing is presented as certain that is not.

**Decision Journal**
A per-recommendation record of the specific evidence, Indicators, and Guardrail evaluations that led ASA to surface a given Opportunity to a user. Distinct from the `DECISION_LOG.md` architecture document: the Decision Journal is product-level, per-recommendation output; the Decision Log is a project-level architectural changelog. (See Open Questions below.)

**Evidence**
The structured Observations, Canonical Facts, and Indicator values cited in support of a Recommendation. Evidence is what makes a Recommendation explainable under Constitution Law 6 — a Recommendation without linked Evidence is not a valid Recommendation.

**Guardrail**
A platform-owned rule that determines whether a candidate Opportunity is eligible to be recommended. Guardrails are shared across all Strategies; a Strategy does not implement its own private risk logic (Constitution Law 8).

**Indicator**
A derived, shared quantity computed from one or more Canonical Facts. Indicators are computed exactly once and consumed by every Strategy that needs them (Constitution Law 3) — a Strategy never maintains its own private copy of an Indicator's calculation.

**Observation**
Immutable, raw evidence as reported by an external Provider. An Observation is a historical record: once written, it is never altered, even if later shown to be wrong. Corrections are represented as new Observations and reconciled at the Canonical Fact layer, not by editing history.

**Opportunity**
A candidate investment action surfaced by the Strategy Layer, prior to Guardrail evaluation and Ranking. An Opportunity that does not pass Guardrail evaluation is never presented to a user as a Recommendation.

**Provider**
An external source of raw data — market data, options data, broker data, financial events, or similar — that ASA does not control. ASA does not assume Providers agree with one another; see Provenance and Confidence.

**Provenance**
The record of which Provider(s) an Observation or Canonical Fact originated from, and how a Canonical Fact was reconciled if multiple Providers disagreed. Provenance is what makes reconciliation auditable after the fact.

**Recommendation**
An Opportunity that has passed Guardrail evaluation and been ordered by the Ranking Layer for presentation to a user. A Recommendation is always backed by Evidence and is never generated directly by the Presentation Layer.

**Strategy**
A deterministic evaluation over Indicators (and, where applicable, Capabilities) that surfaces candidate Opportunities. A Strategy does not read raw Observations directly (Constitution Law 4) and does not implement its own Guardrail logic (Constitution Law 8).

---

## Open Questions / Requires ADR

- **Capability vs. Indicator boundary.** This glossary defines Capability as a unit of analytical function distinct from an Indicator, but the precise line between the two — and whether every Capability must ultimately reduce to one or more Indicators, or whether a Capability can encapsulate logic an Indicator does not — has not been settled by an ADR. Until resolved, treat this entry as provisional.
- **Decision Journal vs. Decision Log.** These are two different things with similar names — one is a per-recommendation product artifact, the other is a project-level architecture changelog. This glossary distinguishes them explicitly to prevent the ambiguity, but no ADR has yet formally adopted the Decision Journal as a system component; it is defined here because the term appears in the domain vocabulary this brief specified, not because its implementation has been decided.
