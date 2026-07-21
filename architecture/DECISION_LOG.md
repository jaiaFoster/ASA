<!-- Repository path: architecture/DECISION_LOG.md -->

# ASA Architecture Decision Log

This is an index of adopted architectural decisions, newest first. It is not a substitute for the ADRs it links to — see `README.md`'s authority hierarchy. Each entry is a one- or two-sentence summary; the linked ADR is the source of truth for context, alternatives considered, and rationale.

Do not add substantive reasoning to this file. If an entry needs more than two sentences to be understood, that reasoning belongs in its ADR, not here.

| Date | Summary | ADR |
|---|---|---|
| 2026-07-21 | Guardrail evaluation is the pipeline envelope containing the immutable Opportunity, ordered Guardrail outcomes, and aggregate decision; Ranking never reconstructs Opportunity data from outcomes or persistence. | ADR-005 (amended, ASA-CORE-007) |
| 2026-07-21 | `guardrails/`'s allowed dependencies narrowed to `strategies/`, `indicators/`, `facts/`, `reconciliation/`, `domain/` — not `observation/` or `providers/` — making ADR-005's existing "no raw Observation access" prose structurally enforceable. | ADR-004 (amended, ASA-CORE-006) |
| 2026-07-21 | `strategies/`'s allowed dependencies narrowed to `indicators/`, `facts/`, `reconciliation/`, `domain/` — not `observation/` or `providers/` — making Constitution Law 4 ("consume knowledge, don't gather it") structurally enforceable for the Strategy Layer. | ADR-004 (amended, ASA-CORE-005) |
| 2026-07-21 | `indicators/`'s allowed dependencies narrowed to `facts/`, `reconciliation/`, `domain/` — not `observation/` or `providers/` — so Indicators derive only from reconciled Canonical Facts, never raw Observations. Canonicalization relocated from `observation/` to `domain/` to support this without duplicating logic. | ADR-004 (amended, ASA-CORE-004) |
| 2026-07-21 | `reconciliation/` split out of `facts/` as a pure, repository-free module at the Canonical Fact Layer's pipeline position; `facts/` now depends on it for storage/versioning orchestration. | ADR-004 (amended, ASA-CORE-003) |
| 2026-07-21 | Expected Outcome Metrics units fixed at the domain level (decimal-fraction return, USD amounts, [0,1] probability); expected_return, maximum_loss, and capital_required are mandatory. Domain primitives enforce normalized immutable values, legal ranges, positive versions, and timezone-aware timestamps. | ADR-003 (domain level, ASA-CORE-001A) |
| 2026-07-21 | "Strategy confidence" is removed and replaced by Expected Outcome Metrics — standardized, objective financial characteristics every Strategy must produce; Ranking compares Opportunities using these common metrics. | ADR-003 (amended) |
| 2026-07-21 | Reconciliation confidence is clarified as an internal attribute; Provenance is elevated to a first-class externally visible concept with a binding drill-down requirement (contributing providers, selected provider, disagreements, timestamps, reconciliation metadata). | ADR-001 (amended) |
| 2026-07-20 | Indicator values are versioned and immutable, mirroring the Canonical Fact model, closing a reproducibility gap between Facts and Strategies. | ADR-006 |
| 2026-07-20 | Guardrails are defined as deterministic, versioned, single-Opportunity eligibility rules with no independent Confidence; cross-Opportunity guardrails are explicitly out of scope pending a future ADR. | ADR-005 |
| 2026-07-20 | `presentation/`'s allowed dependencies are narrowed to `ranking/` and `domain/` only, correcting a contradiction with the Presentation Layer's evidence-only constraint. | ADR-004 (revised) |
| 2026-07-20 | Providers are not assumed to agree; Canonical Facts are reconciled from potentially conflicting Observations using provider priority, confidence, and provenance. Observation and Canonical Fact are distinct, non-interchangeable concepts. | ADR-001 |

## Open Questions / Requires ADR

- ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, and ADR-006 now cover the Observation/Canonical Fact model, Provider contract, Opportunity model, repository organization, Guardrail model, and Indicator versioning respectively. The Ranking Layer and the cross-Opportunity (portfolio-level) Guardrail question remain without a corresponding ADR — see ADR-004's and ADR-005's own Open Questions sections.
- No ADR numbering or storage convention has been formally adopted (see `README.md`'s Open Questions). This log assumes ADRs will be referenced by filename or number once that convention exists.
