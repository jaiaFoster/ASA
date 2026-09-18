# TGSM-RUNTIME-001 — S001-03 cross-sectional decision

`analytics.cross_sectional_ranking` adds one strategy-neutral, provider-free
ranking boundary over comparable named facts. Inputs must share feature,
formula version, and effective time. Ordering is explicit; equal values use
canonical instrument identity as the deterministic tie-breaker. Missing facts
remain separately typed `UnrankableSubject` values and never become an economic
rank.

The same module exposes a generic strict-above trend projection. Equality is
FAIL; absent evidence is UNKNOWN with a typed reason. `top_ranked` only slices an
already-auditable ranking and owns no S001 policy.

No provider, strategy identity, acquisition, option, portfolio, broker, or
persistence behavior is introduced. The immutable value objects are directly
provider-free replayable because their identity depends only on named fact IDs,
versions, values, common effective time, direction, and typed gaps.
