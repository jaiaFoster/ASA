<!-- Repository path: docs/architecture/ARCHITECTURE_VISION.md -->

# ASA Architecture Vision

This document describes what kind of system ASA is trying to be. It does not describe how any specific component is implemented — for that, see the relevant ADR. For binding architectural laws, see `CONSTITUTION.md`. For term definitions, see `DOMAIN_GLOSSARY.md`.

## Mission

ASA turns broker portfolio data, market data, options data, financial events, and derived indicators into explainable investment intelligence.

ASA does not execute trades, does not act as a brokerage, and does not replace a manual portfolio tracker. Portfolio state originates from broker integrations wherever a broker integration is available; ASA does not become an alternate system of record for positions a broker already tracks.

## Product Philosophy

ASA exists to help a user understand their portfolio and the opportunities around it — not to act on their behalf. Every output ASA produces should be something a careful, informed investor could have derived themselves given the same evidence, faster and more consistently than they could have gathered it alone.

ASA is read-only by design. It observes, interprets, and explains. It does not place orders, move funds, or modify brokerage state. This is not a temporary limitation; it is a product boundary (see `CONSTITUTION.md`).

## Architectural Philosophy

Three commitments shape every architectural decision in ASA:

- **Facts before opinions.** Raw evidence and ASA's interpretation of that evidence are different things and are never conflated in the system's data model.
- **Determinism through analysis, judgment at the edges.** Everything from raw facts through strategy evaluation is reproducible: the same inputs produce the same outputs, every time, regardless of which component or model version is running. Judgment — including anything a language model contributes — is confined to how a result is presented, never to what the result is.
- **Explainability over cleverness.** A recommendation that cannot be traced back to specific evidence is not a recommendation ASA makes, no matter how well it might perform.

## Current Principles

These principles are already implemented in the current architecture and are expected to remain stable:

- **Observations and Canonical Facts are architecturally distinct.** Raw provider evidence (Observation) and ASA's current best understanding (Canonical Fact) are never the same object in the data model. See `DOMAIN_GLOSSARY.md`.
- **Indicators are shared, not duplicated.** A given calculation has exactly one implementation, consumed by every Strategy that needs it. No Strategy computes its own private version of an indicator another Strategy already computes.
- **Strategy evaluation is deterministic.** Facts, Indicators, and Strategies form a pipeline that must produce reproducible output. Nothing in this path depends on a language model or any other non-deterministic component.
- **Guardrails are platform-owned, not strategy-owned.** Strategies discover candidate opportunities; a separate, shared Guardrail layer decides whether an opportunity is fit to recommend. Risk logic is not duplicated inside individual strategies.
- **Recommendations are explainable.** Every recommendation traces to structured evidence. The presentation layer may summarize that evidence in natural language; it does not invent reasoning that isn't already present in the structured result it is describing.
- **ASA is read-only.** ASA observes broker and market state; it does not change it.
- **Providers are not assumed to agree.** Multiple data providers may disagree about the same underlying fact. The architecture accounts for provider priority, confidence, provenance, and reconciliation rather than assuming a single provider is always correct.

## Architectural Direction

The system is organized as a layered intelligence pipeline:

```
External Providers
        │
        ▼
Observation Layer
        │
        ▼
Canonical Fact Layer
        │
        ▼
Derived Indicator Layer
        │
        ▼
Strategy Layer
        │
        ▼
Guardrail Layer
        │
        ▼
Ranking Layer
        │
        ▼
Presentation Layer
```

Each layer consumes only from the layer(s) below it and has a single, well-defined responsibility:

- **External Providers** supply raw data ASA does not control.
- **Observation Layer** records what a provider said, immutably, as historical evidence.
- **Canonical Fact Layer** resolves Observations (possibly from multiple, disagreeing providers) into ASA's current best-understanding state, which may itself be revised as better information arrives.
- **Derived Indicator Layer** computes shared, reusable quantities from Canonical Facts.
- **Strategy Layer** evaluates Indicators deterministically to surface candidate Opportunities.
- **Guardrail Layer** applies platform-wide risk and eligibility rules to those candidates.
- **Ranking Layer** orders surviving Opportunities for presentation.
- **Presentation Layer** communicates the result to the user, including any natural-language summarization. This is the only layer where a language model may participate.

Provider independence follows from this structure: a provider can be added, removed, or reprioritized without altering any layer above the Observation Layer, because everything above it consumes Canonical Facts, not raw provider payloads.

## Future Possibilities

The following are architectural possibilities the current direction does not foreclose. They are not commitments, are not scheduled, and should not be treated as roadmap items until an ADR adopts one of them:

- **User-authored strategies** — allowing users to define their own Strategy-layer logic against the existing Indicator set.
- **Plugin marketplace** — a mechanism for third parties to contribute Strategies, Indicators, or providers.
- **Community ecosystem** — shared, community-contributed indicators or strategies reviewed and distributed through the platform.

None of these are architecturally required by the current direction; they are documented here only so that a future contributor considering them understands they were already anticipated as *possible*, not that they were *decided*.

## Open Questions / Requires ADR

- The precise mechanism by which the Canonical Fact Layer resolves disagreement between providers (priority ordering, confidence scoring, manual override) is described at the principle level here (see "Providers are not assumed to agree") but the specific reconciliation algorithm is an implementation decision that should be captured in its own ADR, not in this document.
- The boundary between "Ranking Layer" and "Guardrail Layer" — specifically, whether a Guardrail can ever consider relative ranking, or only absolute eligibility — is assumed here to be a strict one-way dependency (Ranking depends on Guardrail output, never the reverse) but this has not been confirmed by a dedicated ADR.
