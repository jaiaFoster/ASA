# SPRINT-012 Preflight Root-Cause Map

Issue: #250  
Base: `main` at `28d3ed6`

| Quantity or policy | Current owner | Correct owner | Duplicate/conflict | Migration | Tests |
|---|---|---|---|---|---|
| Manifest identity/version/capabilities | `strategies/manifest.py` plus independent `strategy_runtime/contract.py` values | Canonical `StrategyManifest`; validated runtime projection | IDs and capabilities drift | Align production manifests and validate before registry construction | manifest-contract consistency |
| Forward implied volatility and factor | `analytics/forward_factor.py`, `strategies/stonk_components.py`, screening context | named derived facts in `analytics/` | conceptual ownership split | move complete formula chain to one derived-fact registry | independent vectors/replay |
| Realized volatility and trailing return | `analytics/realized_volatility.py`, invoked directly by screening | named derived facts in `analytics/` | screening participates in calculation path | typed derived-fact outputs | vectors/provenance |
| Richness normalization | `screening/live_adapters.py::_richness_score` | strategy graph | judgment in orchestration | replace positional scores with named facts and manifest policy | gate truth tables |
| DTE/expiration policy | manifest nodes plus screening constants/context | manifest parameters | duplicated policy | acquisition reads canonical manifest values | consistency test |
| Earnings eligibility | manifest output, disconnected from verdict | strategy graph hard gate | output does not affect decision | connect gate to verdict | truth table |
| Liquidity | skew manifest output, disconnected from verdict | strategy graph hard gate | output does not affect decision | connect gate to verdict | truth table |
| WATCH mapping | screening maps WATCH to framework PASS | generic result projection preserving verdict | semantic collapse | distinct end-to-end verdict | persistence/API round trip |
| Raw front IV label | context port `front_ex_earnings_iv` | canonical raw `front_iv`; earnings exclusion in strategy | false semantic label | rename end-to-end; no ex-earnings proxy | formula/label tests |
| Actual capability acquisition | live adapters | manifest declarations | contracts omit bars/earnings | declare exactly and validate mechanically | acquisition/declaration comparison |
| Input explanations | positional `score_values`, one native score | named derived facts/gates/reasons | names, units, versions lost | generic explanation envelope | API reconstruction |

## Actual acquisition inventory

| Strategy | Acquired capabilities |
|---|---|
| `forward_factor` | quote, option chain/expirations; earnings required by approved exclusion |
| `earnings_calendar` | earnings, quote, option chain/expirations, historical bars |
| `skew_momentum` | quote, option chain/expirations, historical bars |

## Translation and storage constraints

- Screening currently maps PASS/WATCH to framework PASS and FAIL to NO_SIGNAL.
- The universal bridge persists only framework evaluation state, verdict text,
  one native score, generic economics, and provenance.
- PostgreSQL uses one generic JSON-capable latest-result path; no
  strategy-specific schema is required.
- Refresh-integrity regressions live in
  `tests/strategy_runtime/test_refresh_integrity_regressions.py` and must remain
  green throughout.

## Risk and recovery

This is R3 because it changes canonical strategy authority and production
financial semantics. Architecture/public contracts require Founder review.
Each workstream is independently revertible; no destructive migration or
provider/broker behavior is introduced.
