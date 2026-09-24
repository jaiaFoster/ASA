# STOCK-PRODUCT-001 — SP-01, SP-02, SP-03, SP-05

Baseline: `main@7566f4f`
Operational issue: [#484](https://github.com/jaiaFoster/ASA/issues/484)
Sprint start: OPTIONS-PRODUCT-001's trade-card path is merged and usable
(OP-07 observed on production); its OP-07-C1 correction merged in #483.

## Production defects found before implementation (main@d6d4c8d)

- B001/SPY (PASS, BUY) and B002/SPY (typed `unusable_historical_bars`) run on
  schedule and are fresh.
- The Intelligence Console requests `active_only=true`. The API defined
  "active" as S&P membership symbols only, so the scheduler's own benchmark
  pairs were counted as retained non-active. The Stock strategies tab
  therefore showed "No persisted stock-benchmark results yet" although a
  fresh B001 PASS existed.
- The stock UI classified stock strategies with a hardcoded `["B001", "B002"]`
  identifier list.

## SP-01 — stock proposal contract

`strategy_runtime/stock_proposal.StockOpportunityProposal` projects one
result of a strategy that declares `StructureKind.NONE`:

- instrument, strategy/version, and the strategy's declared description;
- status: `actionable` (verdict PASS **and** a strategy-emitted
  `decision.direction`), `no_action`, or `unknown` (with typed reasons);
- action only from `decision.direction`; otherwise
  `no_action_emitted_by_strategy` or `evaluation_incomplete`. It never infers
  SELL or HOLD;
- allocation only from a strategy-emitted `decision.target_weight`;
  otherwise `not_defined_by_strategy`;
- signal metrics, evidence time, rationale, invalidation
  (`not_defined_by_strategy`), warnings, and provenance.

## SP-02 — generic projection

- `GET /api/v1/screening/{signal}/{symbol}/stock-proposal`. It is gated by the
  declared structure, not the strategy ID: option-structured signals return
  `404 NO_STOCK_PROPOSAL`. The response adds the current freshness projection.
- The API's active scope is S&P membership **plus** the scheduler's declared
  pairs outside it (`STOCK_BENCHMARK_UNIVERSE`), injected at the composition
  root from the scheduling authority. List, health, and retained-non-active
  counts share one `_is_active` predicate.
- `/capabilities` exposes each contract's declared `structure` and `category`.
- The frontend OpenAPI contract and generated types are updated.

## SP-03 and SP-05 — stock card and cross-asset shell

- The stock detail view leads with a stock card: "STOCK OPPORTUNITY ·
  ANALYTICAL, NOT AN ORDER", the instrument and action (or its typed absence),
  strategy, status, verdict, evidence time, freshness and age, allocation or
  its typed absence, signal metrics, and unknown reasons. It has an
  expandable rationale, invalidation, warnings, and provenance, plus the
  disclosure that ASA neither sizes positions nor estimates returns unless the
  strategy defines them.
- Asset surfaces (Stocks tab, detail loader, the "OPTIONS" or "STOCK / ETF"
  heading) come from the declared structure in `/capabilities`. The UI source
  contains no strategy identifiers, and a static test enforces this.

## SP-04 — scheduled operation (assessed)

Benchmarks already run through `run_scheduled_stock_benchmark_refresh` on
the production cron, using the shared market-data authority. No second
acquisition path exists or is added. B002's current `missing_data` is the
documented external adjusted-close entitlement limit (STOCK-RUNTIME-001
STK-01), so it is a truthful typed unknown, not an ASA defect.

## Validation

- Full Python suite: 3,512 passed / 48 skipped.
- ui-tests: 18/18 pass (stock card actionable and unknown, structure-based
  stock view).
- Frontend: lint, typecheck, tests, and build pass with the regenerated types.
- Ruff, mypy, and Lean pre-push pass.

## Remaining

SP-06 is a production observation of stock proposals on the exact deployed
SHA containing this change.
