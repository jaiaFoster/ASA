<!-- Repository path: docs/architecture/README.md -->

# ASA Architecture Documentation

This directory is the authoritative architecture documentation for ASA (Algo Stock Advisor). It exists to let a new contributor understand what ASA is, why it is built the way it is, and where to look when a specific question arises.

## Document Set

| Document | Answers |
|---|---|
| [`CONSTITUTION.md`](./CONSTITUTION.md) | What must never change? |
| [`ARCHITECTURE_VISION.md`](./ARCHITECTURE_VISION.md) | What kind of system are we building, and why? |
| [`DOMAIN_GLOSSARY.md`](./DOMAIN_GLOSSARY.md) | What does this term mean? |
| ADRs (`docs/architecture/decisions/`) | Why was this specific decision made? |
| [`DECISION_LOG.md`](./DECISION_LOG.md) | What has been decided, and where is the reasoning? |

Each document has exactly one job. If you find the same explanation in two places, that is a defect — file an issue.

## Authority Hierarchy

When documents appear to conflict, resolve the conflict using this order, highest authority first:

1. **Constitution** — architectural laws. Rarely changes. A proposed change here should be rare and deliberate.
2. **Architecture Vision** — long-term direction and philosophy. Changes occasionally, as a result of accumulated ADRs.
3. **Domain Glossary** — canonical vocabulary. Changes when a new concept is introduced or an existing one is clarified.
4. **ADRs** — individual, dated architectural decisions with full context and rationale.
5. **Decision Log** — an index into ADRs. It carries no independent authority.

The Decision Log never supersedes an ADR. It exists so a reader can scan the history of architectural decisions without opening every ADR; the ADR remains the source of truth for *why* a decision was made and what alternatives were considered.

## How to Use This Documentation

- **New to the project?** Read `ARCHITECTURE_VISION.md` first, then skim `CONSTITUTION.md`.
- **Implementing a feature?** Check `DOMAIN_GLOSSARY.md` for the terms involved, then search ADRs for prior decisions in that area before proposing a new one.
- **Proposing an architectural change?** Write an ADR. Do not edit the Vision, Constitution, or Glossary directly to introduce a new decision — see "Maintaining This Documentation" below.
- **Looking for history?** Start at `DECISION_LOG.md` and follow the ADR links.

## Maintaining This Documentation

Architectural change flows in one direction:

```
Architecture Vision
        │
        ▼
   Constitution
        │
        ▼
      ADR
        │
        ▼
  Decision Log
```

An ADR is where a specific architectural decision is proposed, discussed, and recorded. When an ADR is accepted, the author is responsible for checking whether it also requires an update to:

- **Architecture Vision** — only if the ADR changes long-term direction, not just an implementation detail within existing direction.
- **Constitution** — only if the ADR touches one of the small set of laws in that document. This should be rare.
- **Domain Glossary** — if the ADR introduces or redefines a term.
- **Decision Log** — always. Every accepted ADR gets a corresponding entry.

The Decision Log entry summarizes the decision in one or two sentences and links to the ADR. It never duplicates the ADR's reasoning.

## What This Documentation Set Does Not Cover

Deployment decisions, database technology choices, CI implementation, secrets management, OAuth implementation, API design, and other implementation-level infrastructure decisions belong in ADRs or in engineering documentation outside this directory, not in the Vision, Constitution, or Glossary. Those documents describe architectural philosophy and direction, not implementation.

## Open Questions / Requires ADR

- No ADR index or numbering convention has been formally adopted yet. This README assumes ADRs live at `docs/architecture/decisions/` and are individually numbered; that convention itself should be confirmed by an ADR rather than assumed here.
