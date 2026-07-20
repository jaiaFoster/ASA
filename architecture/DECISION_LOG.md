<!-- Repository path: docs/architecture/DECISION_LOG.md -->

# ASA Architecture Decision Log

This is an index of adopted architectural decisions, newest first. It is not a substitute for the ADRs it links to — see `README.md`'s authority hierarchy. Each entry is a one- or two-sentence summary; the linked ADR is the source of truth for context, alternatives considered, and rationale.

Do not add substantive reasoning to this file. If an entry needs more than two sentences to be understood, that reasoning belongs in its ADR, not here.

| Date | Summary | ADR |
|---|---|---|
| _pending_ | Providers are not assumed to agree; Canonical Facts are reconciled from potentially conflicting Observations using provider priority, confidence, and provenance. | ADR pending |
| _pending_ | Guardrails are platform-owned and shared across all Strategies; Strategies do not implement independent risk logic. | ADR pending |
| _pending_ | Strategy evaluation, and everything feeding it, is deterministic; language models are confined to the Presentation Layer. | ADR pending |
| _pending_ | Observation and Canonical Fact are established as distinct, non-interchangeable architectural concepts. | ADR pending |

## Open Questions / Requires ADR

- The entries above summarize architectural decisions already reflected in `ARCHITECTURE_VISION.md` and `CONSTITUTION.md`, but none currently has a corresponding formal ADR on record. Each should be backed by an ADR documenting context and alternatives before this log is treated as complete; until then, the "ADR pending" entries are placeholders, not finished index entries.
- No ADR numbering or storage convention has been formally adopted (see `README.md`'s Open Questions). This log assumes ADRs will be referenced by filename or number once that convention exists.
