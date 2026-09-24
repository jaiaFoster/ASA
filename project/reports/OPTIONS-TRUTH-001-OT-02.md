# OPTIONS-TRUTH-001 — OT-02 funnel observability

Baseline: `main@cbe43a79d1b691838cd4bda79e4d104c57ffb994`  
Operational issue: [#459](https://github.com/jaiaFoster/ASA/issues/459)

## Owner map

- Acquisition truth remains in the existing subject plan and durable attempt
  owner. Preparation projects only sanitized demand status, attempt count,
  missing reason, and cross-consumer reuse.
- The latest universal result remains the signal/gate authority. Acquisition
  diagnostics use its existing typed metric envelope; no new persistence table
  or repository exists.
- The existing immutable execution-readiness artifact remains the exact
  structure/constructibility authority.
- `GET /api/v1/screening/{signal}/{symbol}/option-funnel` composes those
  authorities read-only into one typed terminal trace.

## Terminal states

Every current row projects one of: `evidence_unavailable`, `strategy_rejected`,
`structure_unresolved`, `structure_unavailable`, `structure_unknown`, or
`actionable_opportunity`. A missing execution-readiness artifact is explicit;
it never upgrades a qualifying signal to actionable.

The trace includes candidate inclusion, declared capabilities, demand-level
acquisition/usability/reuse, missing reason, gate outcomes, verdict,
constructibility, and one terminal reason. Raw payloads, provider credentials,
and broker state are absent.

## Architecture and safety

The change is provider-neutral and strategy-ID-blind. It adds no acquisition,
financial gate, structure substitution, persistence authority, or broker
mutation. Existing strategy semantic metrics remain unchanged; operational
diagnostics are namespaced under `diagnostic.` and have a dedicated API
projection.
