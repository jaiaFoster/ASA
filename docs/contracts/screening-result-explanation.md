# Screening result explanation contract

SPRINT-012 WS6 preserves one strategy evaluation through the generic runtime,
latest-result repository, and screening API. The strategy manifest remains the
semantic owner; screening and runtime only project its named outputs.

Every successful API result exposes:

- `evaluation_state`: orchestration success or failure;
- `verdict`: the exact strategy `PASS`, `WATCH`, or `FAIL`;
- `outcome`: the lower-case strategy verdict when evaluation succeeded;
- `canonical_facts` and `named_derived_facts`: manifest-declared evidence and
  reusable calculations, kept distinct;
- `formula_versions`: versions from the canonical derived-fact registry;
- `gate_results`: named Boolean or UNKNOWN strategy gates;
- `direction` and `structure`;
- `reason_codes`, manifest-parameter `assumptions`, `warnings`, and `blockers`;
- typed generic `metrics`, provenance, and complete temporal metadata.

`WATCH` is not translated to `PASS`, and `FAIL` is not presented merely as
`no_signal`. `evaluation_state` remains separate so callers can distinguish a
valid strategy decision from missing data or an adapter failure.

The generic persistence schema stores explanation values inside its existing
typed metrics namespace using `fact.`, `derived_fact.`, `formula_version.`,
`gate.`, and `decision.` prefixes. No strategy ID, provider payload, provider
SDK type, or strategy-specific column exists in persistence or API projection.

Unknown mandatory evidence is rendered as `UNKNOWN`; it is never replaced by a
proxy. Formula versions are emitted only for outputs backed by a registered
canonical derived fact. Manifest parameters are disclosed as assumptions so an
API consumer can independently apply the versioned gates.
