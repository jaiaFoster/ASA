<!-- Repository path: architecture/ADR-007-ranking-model.md -->

# ADR-007: Deterministic Ranking Model

**Status:** Accepted
**Date:** 2026-07-21

## Context

ADR-003 gives every Opportunity standardized Expected Outcome Metrics so structurally different
Strategies can be compared. ADR-005 makes Guardrails an eligibility layer and, as amended by
ASA-CORE-007, defines `OpportunityGuardrailEvaluation` as the pipeline envelope containing the
immutable Opportunity, ordered Guardrail outcomes, and aggregate decision. The Ranking Layer
must order eligible Opportunities reproducibly without inventing Opportunities, gathering new
data, or hiding judgment inside an opaque score.

## Decision

Ranking accepts only `OpportunityGuardrailEvaluation` values. It filters to aggregate `PASS`
decisions, retains each complete evaluation envelope, and produces immutable
`RankedOpportunity` values in one `RankingResult`. It never mutates or recreates an Opportunity.

The algorithm is pinned as `asa.ranking` `v1`. Six independently versioned component scorers
produce scores in `[0, 1]` with complete provenance:

1. **Expected return:** linear normalization of mandatory expected return between configured
   floor and ceiling.
2. **Downside risk:** one minus the bounded maximum-loss-to-capital ratio. Lower downside is
   better. Zero capital and zero loss receives the maximum score; nonzero loss with zero capital
   receives the minimum.
3. **Evidence confidence:** the Opportunity's existing evidence-confidence score, unchanged.
4. **Capital efficiency:** v1 heuristic of expected return divided by time-horizon days, linearly
   normalized between configured daily-return bounds. Expected return is already defined by
   ADR-003 as a fraction of capital required, so this is capital-normalized return per day.
5. **Liquidity:** configured neutral placeholder because the current Opportunity contract has no
   liquidity metric. This assumption is explicit in component provenance and isolated in its own
   scorer; no unrelated Evidence is used as a proxy.
6. **Opportunity quality:** probability of profit when present; otherwise a configured neutral
   placeholder recorded in provenance.

The total score is the weighted mean of the six component scores, quantized to twelve decimal
places using `Decimal` arithmetic. Every weight, normalization bound, and placeholder is an
immutable effective parameter included in deterministic identity. Default v1 weights are equal.

Ordering is descending by total score, then descending evidence confidence, then descending
expected return, then ascending `opportunity_id`. Input order and execution timestamps never
affect identity or ordering.

A `RankedOpportunity` identity includes its Opportunity ID, ranking algorithm version, complete
ordered scoring-component provenance, and effective parameters. It excludes rank, timestamps,
execution order, and randomness. The result identity includes the deterministically ordered
ranked identities and effective parameters.

## Boundaries

`ranking/` may import only `ranking`, `guardrails`, `strategies`, `indicators`, `facts`,
`reconciliation`, and `domain`. It may not import Providers, Observations, Presentation,
Execution, or infrastructure. Ranking has no repository and performs no I/O. Scorers are
registered explicitly; dynamic plugins, ML, LLMs, randomness, and broker access are prohibited.

## Consequences

- Rankings are transparent and replayable, including when placeholder policies are active.
- Liquidity does not influence relative order under the default constant placeholder; that is
  preferable to fabricating a proxy from unrelated fields.
- Calibration can replace one scorer at a time only by versioning its semantics and, when the
  overall algorithm changes, advancing the ranking algorithm version.
- Duplicate evaluations for one Opportunity are rejected rather than resolved by input order.

## Alternatives Considered

1. **Read missing values from a repository.** Rejected: violates the pure pipeline contract and
   would make replay depend on external state.
2. **Infer liquidity from evidence count or confidence.** Rejected: those concepts are not
   liquidity and using them would hide an unsupported assumption.
3. **Use floating-point or random tie-breaking.** Rejected: violates deterministic replay and
   stable ordering.
4. **Copy Opportunity fields into RankedOpportunity.** Rejected: the Guardrail envelope already
   owns the immutable Opportunity; copying creates parallel structures and drift risk.

## References

- ADR-003: Explainable Opportunity Model
- ADR-004: Repository Organization
- ADR-005: Guardrail Model
- Architecture Constitution, Laws 3, 6, 7, 9, and 10
