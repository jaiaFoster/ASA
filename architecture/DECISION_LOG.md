<!-- Repository path: docs/architecture/DECISION_LOG.md -->

# ASA Architecture Decision Log

This is an index of adopted architectural decisions, newest first. It is not a substitute for the ADRs it links to — see `README.md`'s authority hierarchy. Each entry is a one- or two-sentence summary; the linked ADR is the source of truth for context, alternatives considered, and rationale.

Do not add substantive reasoning to this file. If an entry needs more than two sentences to be understood, that reasoning belongs in its ADR, not here.

| Date | Summary | ADR |
|---|---|---|
| 2026-07-21 | "Strategy confidence" is removed and replaced by Expected Outcome Metrics — standardized, objective financial characteristics every Strategy must produce; Ranking compares Opportunities using these common metrics. | ADR-003 (amended) |
| 2026-07-21 | Reconciliation confidence is clarified as an internal attribute; Provenance is elevated to a first-class externally visible concept with a binding drill-down requirement (contributing providers, selected provider, disagreements, timestamps, reconciliation metadata). | ADR-001 (amended) |
| 2026-07-20 | Indicator values are versioned and immutable, mirroring the Canonical Fact model, closing a reproducibility gap between Facts and Strategies. | ADR-006 |
| 2026-07-20 | Guardrails are defined as deterministic, versioned, single-Opportunity eligibility rules with no independent Confidence; cross-Opportunity guardrails are explicitly out of scope pending a future ADR. | ADR-005 |
| 2026-07-20 | `presentation/`'s allowed dependencies are narrowed to `ranking/` and `domain/` only, correcting a contradiction with the Presentation Layer's evidence-only constraint. | ADR-004 (revised) |
| _pending_ | Providers are not assumed to agree; Canonical Facts are reconciled from potentially conflicting Observations using provider priority, confidence, and provenance. | ADR-001 |
| _pending_ | Guardrails are platform-owned and shared across all Strategies; Strategies do not implement independent risk logic. | ADR-005 |
| _pending_ | Strategy evaluation, and everything feeding it, is deterministic; language models are confined to the Presentation Layer. | ADR-004 |
| _pending_ | Observation and Canonical Fact are established as distinct, non-interchangeable architectural concepts. | ADR-001 |

## Open Questions / Requires ADR

- ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, and ADR-006 now cover the Observation/Canonical Fact model, Provider contract, Opportunity model, repository organization, Guardrail model, and Indicator versioning respectively. The Ranking Layer and the cross-Opportunity (portfolio-level) Guardrail question remain without a corresponding ADR — see ADR-004's and ADR-005's own Open Questions sections.
- No ADR numbering or storage convention has been formally adopted (see `README.md`'s Open Questions). This log assumes ADRs will be referenced by filename or number once that convention exists.
