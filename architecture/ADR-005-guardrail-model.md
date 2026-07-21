<!-- Repository path: architecture/ADR-005-guardrail-model.md -->

# ADR-005: Guardrail Model

**Status:** Accepted
**Date:** 2026-07-20

## Context

`CONSTITUTION.md` Law 8 requires Guardrails to be platform-owned and shared across all Strategies, with risk logic never duplicated inside a Strategy. `ARCHITECTURE_VISION.md` describes Guardrails as deciding "whether opportunities should be recommended," separately from Strategies, which only discover them. ADR-003 requires every Opportunity to carry Guardrail outcomes as structural content, including for rejected Opportunities, but does not define what a Guardrail structurally is. ADR-004 assigns Guardrails a repository module (`guardrails/`) but, as flagged in its post-review Open Questions, gives it no contract. This ADR provides that contract.

Guardrails exist as a first-class architectural concept specifically because under-specified risk logic embedded inside individual strategies has caused real losses in the past (for example, a calendar-spread position taken with an insufficiently distant front leg). This history is the reason this layer is specified before any Guardrail code is written, not after.

## Decision

A **Guardrail** is a deterministic eligibility rule, evaluated against a single candidate Opportunity, that determines whether that Opportunity may proceed to the Ranking Layer. A Guardrail answers exactly one question — is this Opportunity eligible? — and does so as a pass/fail outcome with a reason, not as a probabilistic or advisory judgment.

**What a Guardrail may read.** A Guardrail may read Canonical Facts and Indicators (including Capabilities), exactly as a Strategy may (Constitution Law 4, extended here to Guardrails on the same rationale: eligibility rules consume established knowledge, they do not gather it). A Guardrail may not read raw Observations directly, for the same reason a Strategy may not.

**Guardrails carry no independent Confidence value.** A Guardrail's outcome is a deterministic function of the Facts and Indicators it evaluates, which already carry their own Confidence (ADR-001, ADR-003). Introducing a second, Guardrail-level Confidence would risk the same Facts/opinions conflation ADR-003 avoided at the Opportunity level by separating evidence confidence from strategy confidence — a Guardrail is not a judgment call, it is a deterministic check, and its pass/fail outcome is either correct given its inputs or it is a defect in the Guardrail's implementation, not a matter of degree.

**Guardrail versioning.** Every Guardrail is versioned, exactly as Strategies are versioned under ADR-003, and for the identical reason: Constitution Law 7 requires reproducible evaluation, which requires knowing which version of a Guardrail's logic actually ran. Every Guardrail outcome recorded on an Opportunity (ADR-003) references the specific Guardrail version that produced it, alongside the Canonical Fact and Indicator versions that Guardrail read.

**Guardrail evidence.** A Guardrail outcome's "reason" is not free text alone — it references the specific Facts and Indicators (with their versions) that drove the pass/fail result, in the same evidence-citing style ADR-003 requires of Strategies. This is what makes a Guardrail rejection explainable in the same way a Recommendation is explainable (Constitution Law 6 applies to Guardrail outcomes, not only to final Recommendations, since ADR-003 already requires rejected Opportunities' Guardrail trails to be retained).

**Evaluation scope: single-Opportunity only, for this ADR.** As specified here, a Guardrail evaluates exactly one candidate Opportunity in isolation. It does not have access to other candidate Opportunities being evaluated in the same cycle, and it does not have access to portfolio-level aggregate state (for example, total existing exposure to a given underlying) beyond whatever a Canonical Fact or Indicator already exposes about that state. This is a deliberate, narrower scope than "platform-wide risk rules" might suggest, and it is called out explicitly rather than left as an unstated assumption (see Open Questions) — a genuine portfolio-level or cross-Opportunity Guardrail (e.g., "reject this Opportunity if it would push aggregate exposure to this underlying past a limit, given other Opportunities also being considered right now") is not representable under this ADR's scope, because it requires comparing candidates against each other, not evaluating one candidate against static Facts and Indicators.

**Evaluation envelope.** The complete Guardrail Engine result for one candidate is an
`OpportunityGuardrailEvaluation`. It retains the exact immutable `Opportunity`, the complete
deterministically ordered Guardrail outcomes, and one aggregate `PASS` or `FAIL` decision.
The envelope does not replace the Opportunity and does not duplicate its fields. This makes
the `guardrails → ranking` pipeline explicit: Ranking receives the eligible Opportunity and
its full Guardrail trail together, without repository access or reconstruction.

## Alternatives Considered

1. **Guardrails carry their own Confidence score, independent of the Facts/Indicators they read.** Rejected: this reintroduces the Facts/opinions conflation ADR-003 specifically eliminated at the Opportunity level, one layer over — a Guardrail's job is to apply a deterministic rule to evidence that already carries whatever uncertainty exists, not to add a second, parallel uncertainty judgment.
2. **Guardrails are unversioned, since they are "just rules," unlike Strategies.** Rejected: a Guardrail's logic changing over time (a DTE threshold tightened after an incident, for example) has exactly the same reproducibility requirement as a Strategy's logic changing — an audit or replay of a historical rejection must be able to identify which rule version actually rejected it.
3. **Guardrails may evaluate the full candidate set jointly, in this ADR, to support portfolio-level rules from the start.** Rejected for this ADR: this would require a structural change to ADR-004's strict single-item `strategies → guardrails → ranking` pipeline (Guardrails would need to see multiple candidates, not one), which is a bigger architectural change than this ADR is scoped to make. Deferring it explicitly (rather than silently assuming it away) is preferred so the limitation is visible before portfolio-level guardrail needs arise in practice.

## Consequences

- Every Guardrail implementation must cite the specific Facts/Indicators it read as part of its outcome, not just return a boolean — this is a discipline requirement on Guardrail authors, mirroring the discipline ADR-003 places on Strategy authors for Evidence and Assumptions.
- Because Guardrails are versioned and their outcomes are retained even for rejected Opportunities (ADR-003), a historical rejection can always be explained by exactly which rule version and which evidence produced it — directly addressing the kind of gap that caused prior real losses from under-specified risk logic.
- Portfolio-level, cross-Opportunity Guardrails (aggregate exposure limits, concentration limits, and similar) are explicitly not supported by the architecture as specified here. If and when they are needed, they will require a follow-up ADR that changes the pipeline shape described in ADR-004, not merely a new Guardrail implementation within the current single-item evaluation model.

## Open Questions

- Cross-Opportunity / portfolio-level Guardrails are a known, anticipated future need (the reviewed product context already runs multiple concurrent strategy types against a single real portfolio, making an aggregate exposure check a realistic near-term requirement) but are out of scope for this ADR. A follow-up ADR should address whether this is solved by giving the Guardrail Layer visibility into the full candidate set for a given evaluation cycle, by a separate portfolio-level check that runs after Ranking, or by some other structural change — this ADR does not presume which.
- Whether a Guardrail may depend on another Guardrail's outcome (composition/ordering among Guardrails) is not addressed here and is left to be resolved when more than a small number of Guardrails exist and ordering dependencies, if any, become apparent in practice.

## Documentation Impact

`ARCHITECTURE_VISION.md`'s Current Principles section already states that Guardrails are platform-owned and shared; this ADR is consistent with that and requires no change there. Recommend `DOMAIN_GLOSSARY.md`'s **Guardrail** entry be updated to note that Guardrail evaluation is currently single-Opportunity in scope, with a reference to this ADR's Open Questions for the anticipated portfolio-level extension, so a future reader doesn't assume broader scope than what is architected today.

## References

- `CONSTITUTION.md`, Laws 4, 6, 7, 8
- `ARCHITECTURE_VISION.md`, "Current Principles" (guardrails are platform-owned, not strategy-owned)
- `DOMAIN_GLOSSARY.md`: Guardrail, Opportunity, Evidence, Confidence
- ADR-001 (Canonical Fact versioning model, extended here to Guardrail evidence)
- ADR-003 (Opportunity model; Guardrail outcomes as structural content; Strategy versioning precedent)
- ADR-004 (repository module boundary for `guardrails/`; single-item pipeline assumption this ADR makes explicit)

## Revision note (ASA-CORE-007)

The original implementation represented a Guardrail evaluation with only an
`opportunity_id`, outcomes, and a boolean result. That shape could establish eligibility but
could not supply Ranking with the immutable Opportunity and standardized metrics that Ranking
must compare. The evaluation is now explicitly the pipeline envelope: immutable Opportunity,
ordered outcomes, and aggregate decision. Redundant copied Opportunity fields and repository
lookups are prohibited.
