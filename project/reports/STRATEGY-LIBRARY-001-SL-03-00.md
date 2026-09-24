# STRATEGY-LIBRARY-001 — SL-03-00 B001/B002 manifest conformance

Baseline: `main@c0c3aa5`
Authority: SL-01 Architect decision
(`STRATEGY-LIBRARY-001-SL-01-ARCHITECT-DECISION.md`, §3). This must merge
before any SL-03 stock strategy.

## Change

- `strategies/stock_benchmark_manifests.py` adds `B001_MANIFEST` and
  `B002_MANIFEST` (schema 1.1.0) with exact `required_market_capabilities`.
  Both graphs are composed **only from already-registered components**:
  - B001: `asa.core/constant(1)` → `asa.stonk.shared/verdict_classifier`
    (thresholds 1/1) gives a constant PASS on usable price evidence.
  - B002: `asa.core/compare(left=sma, right=price)` → `asa.core/boolean_not`
    gives the gate `above_sma_10m_gate` (strictly price > SMA10M). A constant
    PASS then passes through `asa.stonk.shared/verdict_eligibility_gate`.
- `strategies/stock_benchmark_evaluation.py` only assembles graph inputs and
  executes the compiled graphs. The Python verdict is removed.
- `build_migrated_strategy_registry()` now validates both contracts with
  `validate_manifest_contract`. The catalog carries the real manifest ids.
  `_NO_MANIFEST` is removed.

## Semantics and versioning

The decision is unchanged: B001 always PASS once reached, and B002 PASS iff
price > SMA10M. Parity tests cover above, at the boundary, below, and a
zero SMA.

The graph's canonical verdict vocabulary is PASS/WATCH/FAIL. B002's
non-qualifying verdict token therefore changes from `NO_SIGNAL` to `FAIL`.
Its evaluation state stays `NO_SIGNAL`, which matches every other migrated
strategy. Because a public output token changes, **B002 advances to 1.1.0**.
The frozen `B002@1.0.0` record in STOCK-RUNTIME-001 STK-01 remains the
historical definition. B001's outputs are unchanged, so it stays `1.0.0`.
No acquisition, capability, SMA formula, product surface, or broker behavior
changes.

## Validation

Full suite: 3,523 passed / 48 skipped. Ruff and mypy are clean on the changed
modules.
