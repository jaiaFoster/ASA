# SPRINT-013 S13-08 — Strategy Modularity and Core-Ownership Audit

Scope: `strategies/`, `strategy_runtime/`, `screening/`, `analytics/`, `market_data/`, `asa/` (API projection). Inventory of significant operations, not a line-by-line sweep, per ticket scope.

## Legacy system disambiguation

`strategies/reference_strategy.py`, `strategies/registry.py` (`DEFAULT_REGISTRY`), and the `moving_average_crossover`/`breakout`/`momentum` demo strategies are **dead in the live path** — zero references from `screening/`, `asa/`, or `strategy_runtime/`; only referenced by `tests/architecture/test_strategy_boundaries.py` and `tests/strategies/*`. The live production path is `asa/` API routes → `strategy_runtime.service` → `strategy_runtime/adapters/*` → `screening.adapters.TARGET_STRATEGY_REGISTRY` + `screening.live_adapters`, backed by `strategies/stonk_manifests.py` and `strategies/stonk_components.py`. `tests/architecture/test_strategy_boundaries.py` only guards the dead demo path and does not cover the live strategy files at all — a coverage gap, not a defect, noted for S13-08 follow-up architecture-test work.

## Findings

| # | Location | Behavior | Classification | Action taken |
|---|---|---|---|---|
| 1 | `screening/live_adapters.py:110-117`, `screening/context_builders.py:44-53` vs `strategies/stonk_manifests.py` | Earnings Calendar / Forward Factor DTE-selection policy values are duplicated (deliberately, per an existing code comment) between `screening` and the frozen manifest parameters. | REMOVE_DUPLICATE, but the fix requires a queryable manifest-parameter accessor that does not exist today | **Not fixed.** Design decision needed (new manifest read API) — recorded as blocker below, not attempted as a bounded PR. |
| 2 | `screening/live_adapters.py` (`LIVE_ADAPTER_FACTORIES`, the three `build_live_*_adapter` functions) | The nominally-generic `screening/` layer contains three complete strategy-specific acquisition/threshold/gate implementations keyed by strategy-id string literals, including hardcoded strategy-specific constants (e.g. `MAX_FORWARD_FACTOR_PAIR_ATTEMPTS`, a 20-session return window, a specific richness-formula citation). | UNKNOWN_REQUIRES_ARCHITECT_OR_FOUNDER | **Not fixed.** This is the sprint's largest structural finding — splitting generic acquisition mechanics (belongs in `screening`/`market_data`) from strategy-specific selection thresholds (belongs in each strategy's manifest/adapter) is a multi-file design decision, not a bounded move. Recorded as blocker below. |
| 3 | `screening/live_adapters.py:663-676` | Skew Momentum's 25-delta option "wing" selection target is a hardcoded magic number with no declared owner — it is distinct from the vertical-structure delta targets that *are* manifest parameters. | UNKNOWN_REQUIRES_ARCHITECT_OR_FOUNDER | **Not fixed.** Needs a new manifest parameter slot; folded into finding #2's remediation rather than a standalone patch, since both live in the same file/decision. |
| 4 | `strategies/stonk_components.py` — `SkewMomentumResearchDecision.evaluate()` inline multi-leg liquidity check vs `OptionLegLiquidity.evaluate()` | Identical quote-width/open-interest/volume gate math implemented twice: once as the reusable `OptionLegLiquidity` component, once inlined per-leg inside the Skew Momentum decision component. Violates "one owner per gate_primitive." | REMOVE_DUPLICATE | **Fixed.** Extracted to a shared pure helper `_contract_liquid()`; both components now call it. Behavior is bit-identical (same boolean expression, same short-circuiting) — no output or `algorithm_version` change. See PR below. |
| 5 | `strategies/stonk_components.py` — `SkewMomentumResearchDecision.evaluate()` overall | Bullish/bearish core gates, momentum alignment, direction, verdict — all parameterized via `ParameterDefinition`s, no provider/DB/network/cache access. | KEEP_STRATEGY_POLICY | No action — correctly owned. |
| 6 | `strategies/scoring.py` (`normalize_richness`) | Generic-looking bounded linear transform, imported by `screening/live_adapters.py`. Initially flagged by reconnaissance as misplaced (candidate `MOVE_CORE_ANALYTICS`). | KEEP_STRATEGY_POLICY (verified) | **No action — reconnaissance finding rejected on verification.** [SPRINT-012-PREFLIGHT.md](SPRINT-012-PREFLIGHT.md) explicitly records this as a deliberate SPRINT-012 decision to keep richness normalization as strategy/manifest-owned policy, not core analytics. Moving it would reverse a recorded prior architecture decision without Founder/architect sign-off. The real smell — `screening` importing from `strategies` at all — is a symptom of finding #2 and should be resolved together with it, not in isolation. |
| 7 | `analytics/forward_factor.py` | Strategy-named filename, but contents (`compute_days_to_expiration`, `compute_option_implied_volatility`) are genuinely generic, capability-scoped facts, registered in `analytics/registry.py`. | Confirmed correctly placed | No action. |
| 8 | `strategy_runtime/adapters/_screening_bridge.py` | Single shared, strategy-neutral `ScreeningResult → UniversalScreeningResult` translator, no strategy-ID branching. | Confirmed correctly placed | No action. |
| 9 | `strategy_runtime/adapters/__init__.py`, `asa/scheduled_screening.py` | Strategy-id literals appear only as static composition-root wiring/config, not conditional branching inside generic logic. | Confirmed correctly placed | No action. |
| 10 | `market_data/budget.py`, `market_data/fulfillment.py` | Never imported from `strategies/` (verified: zero `market_data` imports under `strategies/`). | Confirmed clean | No action. |
| 11 | `strategy_runtime/adapters/{skew_momentum_vertical,forward_factor,earnings_calendar}.py` | Thin translation-only glue; no provider/DB/budget/cache objects leak into strategy-facing code. | Confirmed correctly placed | No action. |

## Blockers raised (Founder/architect decision required)

**Exact blocked action:** splitting `screening/live_adapters.py`'s per-strategy acquisition/threshold logic (findings #1, #2, #3) into (a) generic reusable acquisition mechanics owned by `screening`/`market_data`, and (b) strategy-specific selection thresholds owned by each strategy's manifest/adapter, including adding a queryable manifest-parameter read API that does not exist today.

**Confirmed root cause:** `screening/live_adapters.py` was built as a single per-strategy implementation file during earlier sprints, before the S13-08 modularity rule existed; it now holds a mix of genuinely generic acquisition orchestration and strategy-specific policy (DTE windows, richness formula selection, the 25-delta skew wing target) with no boundary between them.

**Why current authority/tools cannot resolve it:** this is a multi-file architectural split affecting three live production strategies simultaneously (Skew Momentum, Forward Factor, Earnings Calendar) and requires designing a new manifest-parameter accessor contract. Per `blocker_policy` and the S13-08 acceptance criteria, "broad refactor is not used as a substitute for evidence" — this is exactly the kind of change the ticket says must not be attempted speculatively.

**Options:**
- (a) Design a manifest-parameter read API now, then split `live_adapters.py` into generic + per-strategy-adapter-owned files, one bounded PR per strategy (3 PRs) plus one shared-mechanics PR. Highest correctness, highest effort/risk to 3 live strategies at once.
- (b) Leave `live_adapters.py` as-is for this sprint, track as a named architecture debt item (new issue), and constrain S13-08 to the findings that were safely bounded (#4, done). Lowest risk, defers the structural fix.
- (c) Split only the lowest-risk piece first (e.g. just the DTE-policy duplication in finding #1, once a minimal manifest read accessor exists) and leave the acquisition/threshold split for a dedicated future sprint.

**Recommended option:** (c) — resolves the clearest duplicate-ownership violation (#1) without touching the higher-risk acquisition/threshold logic (#2, #3), and can be scoped as its own bounded ticket once a manifest read API is designed.

**Smallest Founder action required:** decide whether to (i) accept option (c) and authorize a follow-up ticket to design the manifest-parameter read API, (ii) accept option (b) and have this tracked as a standing architecture-debt issue instead of sprint scope, or (iii) authorize the full split under option (a).

**Work continuing in parallel:** S13-08's safely-bounded finding (#4) is fixed in this same PR; sprint execution continues to S13-02 without waiting on this blocker, per `blocker_policy.forbidden: stopping_unrelated_unblocked_work`.

## Acceptance status

- Concise audit matrix recorded: yes (this document).
- Every remaining strategy operation justified as policy or composition: yes, per findings #5–#11.
- Verified shared logic moved to correct core layer: finding #4 moved (dedup within `strategies/`, no cross-layer move was needed for this one).
- No duplicate calculation/persistence path remains in touched scope: true for finding #4; findings #1–#3 remain open pending the blocker above.
- Broad refactor not used as a substitute for evidence: confirmed — findings #1–#3 were deliberately *not* fixed speculatively.
