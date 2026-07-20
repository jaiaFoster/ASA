<!-- Repository path: docs/architecture/decisions/ADR-002-provider-interface.md -->

# ADR-002: Provider Interface Contract

**Status:** Accepted
**Date:** 2026-07-20

## Context

`ARCHITECTURE_VISION.md` requires provider independence: a Provider can be added, removed, or reprioritized without altering any layer above the Observation Layer. `CONSTITUTION.md` Law 4 requires Strategies to consume knowledge, not gather it, which depends on Providers never leaking provider-specific concerns upward. ADR-001 establishes that Observations carry Provider identity and are structurally normalized at the point of recording. This ADR defines the architectural contract every Provider must satisfy to make both of those things true in practice.

This ADR defines responsibilities, not a programming interface. No abstract class or language-specific contract is specified here.

## Decision

A **Provider**, architecturally, is responsible for exactly one thing: producing well-formed Observations from an external data source. It has no responsibility, and no permission, beyond the Observation Layer boundary.

**Provider responsibilities:**
- Fetch data from its external source.
- Normalize that data structurally into ASA's Observation schema for the relevant data type (consistent field names, units, and shape — not an interpretive transformation of the reported value itself).
- Attach a stable Provider identity to every Observation it produces.
- Attach both effective time and recorded time to every Observation (ADR-001).
- Report its own operational health (reachable / unreachable, rate-limited, erroring) separately from the data it produces.

**Provider identity:** every Provider is assigned a stable, ASA-internal identity, distinct from any vendor-specific account or API key identifier. This identity is what Canonical Fact reconciliation (ADR-001) uses for priority ranking and provenance; it must not change if, for example, an API key is rotated or a vendor renames a product tier.

**Normalization boundary:** normalization into ASA's Observation schema happens entirely inside the Provider's adapter, before an Observation is recorded. Nothing above the Observation Layer ever parses a vendor-specific payload shape. The raw, un-normalized vendor payload MAY be retained alongside the Observation as an opaque audit reference, but it is never queried or interpreted by any layer above Observation.

**Error handling philosophy:** a failed fetch (unreachable Provider, malformed response, rate limit) produces **no Observation** — absence of data is represented as absence, never as a fabricated or default-valued Observation. Provider errors are surfaced as operational health signals, independent of the Observation stream, so that a Provider outage is visible as "no new Observations from Provider X since time Y," not as corrupted or synthetic data flowing into reconciliation.

**Retry philosophy:** retries are entirely the Provider adapter's responsibility and are invisible to every layer above it. Retries must be **idempotent with respect to Observations**: retrying a fetch must never produce a duplicate Observation for the same underlying reported event. Idempotency is achieved by deriving a deterministic Observation identity from Provider identity, effective time, and the specific data point being reported (the exact key composition per data type is left to the relevant per-data-type specification — see Open Questions).

**Provider independence:** no component above the Observation Layer may contain Provider-specific branching logic (e.g., "if Provider is X, do Y"). Canonical Fact reconciliation (ADR-001) depends only on generic Provider metadata — identity, configured priority, and confidence inputs derived from agreement across Observations — never on Provider-specific code paths.

## Alternatives Considered

1. **Providers write raw, un-normalized payloads; normalization happens at the Canonical Fact layer.** Rejected: pushes Provider-specific parsing logic upward into the reconciliation layer, which must then special-case every Provider's payload shape — directly violating provider independence and complicating reconciliation with heterogeneous, Provider-specific data shapes.
2. **A centralized normalization service sitting between all Providers and the Observation Layer.** Rejected for the current architecture: introduces a shared component with no clear single owner per Provider, and is unnecessary indirection given each Provider adapter can own its own normalization independently. Revisit only if normalization logic is found to be substantially duplicated across Providers (Constitution Law 10, Simplicity wins).
3. **No idempotency requirement; deduplicate at the Canonical Fact layer instead.** Rejected: pushes complexity upward and risks skewing reconciliation confidence with duplicate evidence from retries, since the reconciliation layer would need to distinguish "two Providers agreeing" from "one Provider's retried Observation counted twice."

## Consequences

- Adding a new Provider is isolated to writing a new adapter; no change is required to reconciliation, Indicators, Strategies, Guardrails, or Ranking.
- Each Provider adapter bears the full cost of normalization and idempotency for its own data source. This is more work per Provider than a shared normalization service would require, but keeps blast radius contained to a single adapter when a Provider's data format changes.
- Operational monitoring must track Provider health independently of data flow, since a silent Provider outage (no error, just no new Observations) is architecturally indistinguishable from "nothing new happened" unless health is explicitly reported.

## Open Questions

- The exact idempotency key composition per data type is not fixed here. For a data type with a single point-in-time value (e.g., an end-of-day price) the key is straightforward; for continuously updating data (e.g., a live quote stream) "the same underlying reported event" is less obvious and should be defined per data type as each is implemented, rather than forced into one global rule here.
- Whether Provider priority configuration (used by ADR-001's reconciliation) is itself versioned or auditable in the same way Canonical Facts are is not addressed by this ADR and may need its own follow-up decision once priority configuration is implemented.

## Documentation Impact

None required. This ADR is consistent with `DOMAIN_GLOSSARY.md`'s existing Provider, Observation, and Provenance entries and does not introduce new terminology.

## References

- `CONSTITUTION.md`, Laws 4, 10
- `ARCHITECTURE_VISION.md`, "Current Principles" (provider independence, provider disagreement), "Architectural Direction"
- `DOMAIN_GLOSSARY.md`: Provider, Observation, Provenance
- ADR-001 (Observation & Canonical Fact Model)
