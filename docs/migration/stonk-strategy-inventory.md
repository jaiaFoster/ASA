# STONK-001 — Legacy Strategy Inventory

## Inventory basis

This inventory is pinned to public repository `jaiaFoster/Stonk` commit
`5f3fec846f70e9739cf3f15695fd587f0604344c`. The executable registry in
`app/strategies/registry.py` is the primary enumeration authority. Registry metadata,
adapters, service implementations, configuration, documentation, and tests were traced to
distinguish production strategies from disabled clones and adjacent application behavior.

The result is four production strategies. No Flask routes, provider access, database behavior,
mutable row schemas, report construction, or legacy orchestration is a migration target.

## Strategy catalog and feature matrix

| Strategy | Universe | Core signal | Structure | Principal gates | Output |
|---|---|---|---|---|---|
| Earnings Calendar | Analysis tickers with earnings context | Event-volatility and IV relationship | Same-strike calendar | confirmed event, valid pre/post-event expirations, quotes, liquidity, debit/risk | candidate, near miss, lifecycle row |
| Skew Momentum Vertical | Holdings/watchlist/gap candidates | Directional trend plus rich short-wing skew | Call or put debit vertical | momentum, delta suitability, skew, liquidity, reward/risk, event risk | vertical candidate |
| Forward Factor Calendar | Supported equities after deterministic caps | `front_ex_earnings_iv / implied_forward_iv - 1` | Matched-strike put-and-call double calendar | cheap data, source-qualified ex-earnings IV, positive forward variance, pair quality, liquidity, contamination | PASS/WATCH/NEAR MISS/diagnostic; dry-run |
| Stock Momentum | Holdings plus watchlist | Weighted trend, multi-period return, and relative-strength score | Equity exposure proposal | complete metrics, 50d/200d trend, positive 3m/6m returns, RS vs QQQ, allocation, extension, volatility | consider add, pullback, watch, avoid |

`stock_momentum_unified_test` is a disabled test clone and becomes an equivalence fixture, not a
fifth manifest. The custom-strategy compiler/validator is an authoring capability with no concrete
registered strategy. Calendar lifecycle logic is an output/lifecycle policy of Earnings Calendar.
Universal scoring/ranking is shared cross-strategy behavior and must be reconciled with ASA's
existing Guardrail and Ranking layers rather than copied.

## Duplicate and shared logic

The legacy implementation repeats the following patterns across strategy-specific services,
universal row enrichers, ranking services, and generic structure builders:

| Pattern | Legacy locations | Extraction decision |
|---|---|---|
| Universe normalization, exclusions, deterministic caps | adapters; Stock Momentum; Forward Factor; Skew | one canonical universe-filter/cap component family |
| Required-data completeness and blocked-result construction | all four services; row normalization | typed input contracts plus reusable required-evidence gates |
| Earnings event-window checks | Earnings Calendar; Skew; Forward Factor | one pure event-window component |
| Expiration enumeration and pair ranking | calendar spread, Forward Factor, generic structure builder | reusable deterministic expiration-pair selector |
| Quote validity, spread percentage, OI/volume liquidity | all options strategies and structure builders | one typed option-leg/package liquidity component set |
| Delta-nearest leg and matching-strike selection | Skew; Forward Factor; structure builders | shared deterministic leg-selection components |
| Debit/mid/conservative pricing | Earnings Calendar; Skew; Forward Factor; calculation registry | shared structure-pricing components |
| Weighted scoring, ceilings, verdict tiers, stable ordering | per-strategy rankers plus universal scoring/ranking | Components feeding existing ASA Guardrails and Ranking; no parallel ranking authority |
| Portfolio allocation/concentration checks | Stock Momentum; Skew account context | existing ASA Portfolio Engine inputs/policies; do not duplicate |
| Universal row/display normalization | four universal modules | compatibility presentation adapter only, outside strategy intelligence |

## Important behavioral findings

- Forward Factor's source-qualified signal requires an explicit ex-earnings IV. Raw-IV Forward
  Factor is diagnostic only and cannot become PASS.
- Several legacy functions read `date.today()`, environment configuration, providers, caches, or
  mutable dictionaries. Migration must turn all semantic time, evidence, and effective parameters
  into explicit immutable inputs.
- Stock Momentum mixes analytical scoring with portfolio concentration and entry guidance. Its
  manifest must stop at an Opportunity/desired-exposure result; ASA Portfolio Engine remains the
  portfolio policy authority.
- Options services mix evidence acquisition, structure construction, scoring, lifecycle, and row
  presentation. Only pure transformations and policies migrate into Components.
- Legacy universal scoring is strategy-ID-dispatched. ASA migration must use manifest composition
  and registered Components, never reproduce that dispatch in Core.

## Migration sequence

1. **STONK-002:** extract shared pure Components in dependency order: evidence gates; event and
   expiration policies; leg/liquidity/pricing primitives; structure builders; scoring/verdict
   primitives. Register them statically in `asa.stonk.options` or `asa.stonk.equity` Plugins.
2. **STONK-003:** create four canonical manifests. Preserve effective thresholds as explicit
   versioned parameters. Do not migrate the disabled clone as a strategy.
3. **STONK-004:** derive fixture vectors from pinned legacy tests and pure functions. Compare
   candidate eligibility, formulas, gates, scores/order, and desired portfolio exposure. Record
   intentional differences where legacy behavior violated ASA ownership boundaries.
4. **STONK-005:** remove only superseded logic within authorized ASA scope. The external Stonk
   repository remains read-only unless a separate ticket explicitly authorizes writes there.
   Compatibility interfaces must call ASA outputs; dual execution is forbidden.
5. **STONK-006/007:** publish the four-manifest library, dependency catalog, examples, replay and
   performance vectors, then run complete architecture/governance validation.

## Migration boundaries

Legacy source is evidence, not copied topology. Flask, SQLite, provider calls, broker context,
environment reads, caches, mutable result dictionaries, row repositories, universal UI schemas,
and runtime strategy-ID dispatch remain outside ASA Strategy Core. Any missing canonical option,
earnings, or lifecycle contract encountered during extraction is an architecture stop condition;
it must not be filled with hidden mappings or compatibility shims.
