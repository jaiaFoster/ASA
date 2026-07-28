# ADR-010: Strategy Integrity Topology

**Status:** Proposed — Founder merge required  
**Date:** 2026-07-28  
**Issue:** #250

## Context

The accepted repository architecture predates `market_data/`, `analytics/`,
`screening/`, and `strategy_runtime/`. Production execution therefore allowed
acquisition, reusable financial calculations, strategy judgment, and
projection to blur. `StrategyManifest` and `StrategyContract` also described
overlapping identity and capability semantics independently.

## Decision

The binding production flow is:

```text
market_data canonical facts
        ↓
analytics named derived facts
        ↓
strategies canonical manifest and graph
        ↓
screening orchestration
        ↓
strategy_runtime generic result, persistence, and API projection
```

`market_data/` owns provider-neutral immutable observations, timestamps,
freshness, completeness, and provenance. It owns no scores or verdicts.

`analytics/` is the ephemeral, point-in-time part of the Derived Fact layer.
It owns reusable pure calculations over canonical values. Each output has a
stable ID, unit, formula version, effective time, input evidence, and quality.
It owns no strategy threshold, structure selection, or verdict.

`indicators/` remains the durable/versioned Derived Indicator layer over
Canonical Facts. An analytics formula moves to `indicators/` when it becomes a
persisted cross-run indicator. The same formula may never exist in both
packages.

`strategies/` owns gates, thresholds, weights, direction, structure selection,
scores, assumptions, reason codes, and PASS/WATCH/FAIL. It consumes named
derived facts and canonical values. It never acquires provider data.

`screening/` owns acquisition planning and orchestration. It may request facts
declared by a strategy, invoke registered analytics, and execute the graph. It
must not define financial formulas, normalize strategy scores, reinterpret
verdicts, or branch on a strategy ID.

`strategy_runtime/` owns generic execution isolation, persistence projection,
API projection, history, and replay. It must preserve strategy semantics and
must not contain strategy-named conditionals.

## Canonical strategy authority

`StrategyManifest` is the only authored strategy definition. Identity,
semantic version, parameters, capability requirements, graph, outputs, and
events come from the manifest.

`StrategyContract` is a runtime projection. Fields overlapping the manifest
are mechanically validated before registry construction:

- `strategy_id == manifest.strategy_id`;
- `version == manifest.strategy_version`;
- market capabilities equal manifest requirements exactly.

Manifest schema 1.1 separates `required_market_capabilities` (canonical fact
acquisition) from the existing `required_capabilities` (component-runtime
capabilities). They are different namespaces and must never be overloaded.

Runtime-only declarations such as lifecycle storage support and generic output
envelope capabilities may remain in the projection, but cannot redefine
manifest semantics.

## Extension contract

Adding a strategy means:

1. author one versioned manifest;
2. declare every canonical capability it acquires;
3. consume registered, named derived facts;
4. express all gates and verdict paths in the graph;
5. generate or validate the runtime projection;
6. register one generic orchestration adapter;
7. prove deterministic replay and complete result projection.

No positional feature tuple, private duplicate formula, provider payload,
undeclared acquisition, or API-only verdict gate is permitted.

## Consequences

Existing formulas in `screening/live_adapters.py`, positional `score_values`,
duplicated DTE policy, under-declared capabilities, and WATCH collapsing are
migration debt governed by SPRINT-012. This ADR does not bless those paths;
each must be removed through bounded implementation PRs while main stays green.

Architecture or public-contract changes require Founder review.
