<!-- Repository path: docs/architecture/decisions/ADR-003-opportunity-model.md -->

# ADR-003: Explainable Opportunity Model

**Status:** Accepted
**Date:** 2026-07-20

## Context

`CONSTITUTION.md` Law 6 requires every recommendation to be explainable, and Law 8 requires Guardrails to be platform-owned rather than duplicated per Strategy. `ARCHITECTURE_VISION.md` states that the Presentation Layer may summarize evidence but never invent reasoning. `DOMAIN_GLOSSARY.md` already defines Opportunity, Evidence, Recommendation, Guardrail, and Confidence, and separately flags **Decision Journal** as a provisional term with no settled architecture. This ADR defines the minimum structural content of an Opportunity and, in doing so, resolves the Decision Journal open question.

## Decision

An **Opportunity**, from the moment it is produced by the Strategy Layer through Guardrail evaluation and Ranking, carries the following as its minimum structural content. This is a conceptual model, not a schema — no field types or serialization format are specified here.

- **Identity.** A stable identifier for the Opportunity that persists across its lifecycle (Strategy discovery → Guardrail evaluation → Ranking → Presentation or rejection), so its full history can be reconstructed from any stage.
- **Originating Strategy.** The specific Strategy, and the specific version of that Strategy, that produced this Opportunity. Recording the version, not just the Strategy's name, is required for Constitution Law 7 (deterministic, reproducible evaluation) — re-running history must use the Strategy version that actually ran, not whatever version exists today.
- **Supporting Indicators.** The specific Indicator values the Strategy relied on, each referencing the Canonical Fact version(s) (ADR-001) they were computed from — not just the final numbers, but a traceable path back to Evidence.
- **Evidence.** The structured Observations and Canonical Facts underlying the above, per `DOMAIN_GLOSSARY.md`'s existing Evidence definition. This is what the Presentation Layer is permitted to summarize; anything not present here is not available for the Presentation Layer to reference.
- **Assumptions.** Any modeling assumption the Strategy relied on that is not itself a Fact or Indicator (for example, an assumption about normal market conditions, or a simplification in how a spread's risk is modeled). Assumptions are recorded explicitly by the Strategy, not left implicit in code, so they can be surfaced as caveats.
- **Confidence.** A single value: *evidence confidence* — deterministically aggregated from the Confidence values of the underlying Canonical Facts and Indicators (ADR-001). It reflects uncertainty in the underlying data only. A Strategy does not express subjective confidence of its own, at any level — see Expected Outcome Metrics below, which replace the concept formerly called "Strategy confidence" (see Revision note).
- **Expected Outcome Metrics.** Standardized, objective financial characteristics that **every** Strategy produces for every Opportunity it emits — for example: expected return, maximum gain, maximum loss, capital required, probability of profit, and time horizon. These are deterministic outputs of the Strategy's model applied to the cited Evidence, expressed in a common, Strategy-independent vocabulary. They are not a judgment score and carry no subjective component: two Strategies of entirely different structure describe their Opportunities in the same financial terms. This common vocabulary is what makes the Ranking Layer possible — Ranking compares Opportunities produced by structurally different Strategies using these common financial metrics (together with evidence confidence and Guardrail outcomes), not by comparing Strategy-specific scores that have no shared meaning.
- **Guardrail outcomes.** The result of every Guardrail evaluated against this Opportunity — not only the final pass/fail, but each individual Guardrail's outcome and reason. This holds even for Opportunities that are ultimately rejected: a rejected Opportunity's Guardrail trail is retained, not discarded, so "why wasn't this recommended" is answerable from the same structural record as "why was this recommended."
- **Recommendation state.** An explicit lifecycle state (for example: discovered, guardrail-evaluated, ranked, presented, rejected) so any consumer of the record can tell where in the pipeline this Opportunity currently sits without inferring it from which fields happen to be populated.

**Presentation Layer constraint:** the Presentation Layer may summarize any of the above in natural language, including using a language model to do so. It may not introduce Evidence, Assumptions, Confidence values, or Guardrail outcomes that are not already present in the structured Opportunity record. A Presentation-layer summary is a strict function of the structured record; it never has independent access to raw Observations, Canonical Facts, or Providers.

**Decision Journal.** This ADR adopts the following definition, resolving `DOMAIN_GLOSSARY.md`'s open question: the Decision Journal entry for a given Recommendation is the immutable, persisted snapshot of that Opportunity's full structural content — Evidence, Assumptions, Confidence, Guardrail outcomes, and Recommendation state — as it existed at the moment the Opportunity was presented as a Recommendation. It is not a separate data structure; it is the Opportunity record itself, frozen at presentation time.

## Alternatives Considered

1. **Store only final Indicator values, without a full evidence chain back to Canonical Facts.** Rejected: fails Constitution Law 6 outright — a recommendation traceable only to a computed number, with no path back to the Facts it was computed from, is not explainable if the underlying Facts are later revised or disputed.
2. **Discard Guardrail evaluation results for rejected Opportunities.** Rejected: forecloses the ability to explain or audit non-recommendations, and creates an asymmetry where only successful Opportunities are auditable — inconsistent with Guardrails being a platform-wide, accountable mechanism (Constitution Law 8) rather than a silent filter.
3. **A single scalar Confidence field on the Opportunity.** Rejected: conflates uncertainty in the underlying data (evidence confidence) with the Strategy's own judgment (strategy confidence), which is exactly the Facts/opinions conflation Constitution Law 1 prohibits — just recurring one layer higher than Observation vs. Canonical Fact.
4. **A separate Decision Journal data structure, distinct from the Opportunity record.** Rejected as unnecessary duplication: everything a Decision Journal would need to contain is already required to exist on the Opportunity record by this same ADR (Constitution Law 3, one calculation, one home — extended here to one record, one home).

## Consequences

- Opportunity records are substantially larger than a "final score plus a label" model would produce, since they must carry a full evidence and Guardrail trail. This is treated as a direct, accepted cost of Constitution Law 6, not an inefficiency to be optimized away later.
- Every Strategy author must explicitly emit Assumptions and the full set of Expected Outcome Metrics — this is a discipline requirement on Strategy implementation, not merely a data-model nicety. A Strategy that cannot state its Opportunity's expected financial characteristics in the standard vocabulary is not a complete Strategy.
- Rejected Opportunities are retained with their full Guardrail trail rather than discarded, which has a storage-cost and retention-policy implication (see Open Questions), but directly enables future "why wasn't this recommended" functionality without further architectural work.
- Because the Decision Journal is defined as the Opportunity record itself at presentation time, no separate persistence mechanism needs to be designed or maintained for it.

## Open Questions

- Retention policy for full Opportunity records (including rejected ones and their Guardrail trails) is not decided here. Given the volume implied by tracking every Guardrail outcome for every discovered Opportunity, this may have cost implications material enough to warrant Founder input, not a purely architectural decision.
- The exact standard field set of Expected Outcome Metrics (which metrics are mandatory for every Strategy versus applicable-when-meaningful) is fixed at the domain-model level, not in this ADR; extending the standard set is an engineering decision unless a new metric changes what Ranking is allowed to compare, in which case it warrants an ADR amendment.

## Documentation Impact

Recommend updating `DOMAIN_GLOSSARY.md`'s **Decision Journal** entry to remove its "provisional" flag and reference this ADR as the settled definition (Decision Journal = the persisted Opportunity record at presentation time, per ADR-003). The Glossary's separate open question about the **Capability vs. Indicator boundary** is untouched by this ADR and remains open.

## Revision note (ASA-CORE-001)

This ADR originally defined a two-value Confidence model on the Opportunity: *evidence confidence* plus an optional, subjective *Strategy confidence*. That second value is removed by this amendment and replaced with **Expected Outcome Metrics**, as defined in the Decision section above. Rationale: a subjective per-Strategy confidence score has no shared meaning across structurally different Strategies and therefore cannot be compared by Ranking without conflating model judgment with data uncertainty — the same Facts/opinions conflation this ADR's Alternative 3 already rejected for a single merged score. Standardized financial characteristics are objective, Strategy-independent, and give Ranking a common basis of comparison. Alternative 3 in "Alternatives Considered" is retained as originally written for historical accuracy; its reasoning (never merge data uncertainty with model output into one number) continues to apply to the amended model.

## References

- `CONSTITUTION.md`, Laws 1, 3, 6, 8
- `ARCHITECTURE_VISION.md`, "Architectural Direction" (Strategy → Guardrail → Ranking → Presentation), "Current Principles" (explainability, guardrails)
- `DOMAIN_GLOSSARY.md`: Opportunity, Evidence, Recommendation, Guardrail, Confidence, Decision Journal (provisional), Indicator
- ADR-001 (Observation & Canonical Fact Model)
- ADR-006 (Indicator Versioning and Immutability) — clarifies that "Supporting Indicators" here means a pinned Indicator version, not a live value
