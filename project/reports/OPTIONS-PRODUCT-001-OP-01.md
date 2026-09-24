# OPTIONS-PRODUCT-001 — OP-01 canonical trade proposal contract

Baseline: `main@78c8624df8eebd3db7747392d12d62b8900bdd47`  
Operational issue: [#468](https://github.com/jaiaFoster/ASA/issues/468)

## Contract

`strategy_runtime.trade_proposal` now owns one immutable, provider-neutral
product projection over the existing `UniversalScreeningResult` and
`ExecutableStructureAssessment` authorities. It contains:

- the originating result, strategy/version, underlying, intended structure,
  evidence snapshot, and structure-assessment identities;
- exact canonical option legs, side, type, strike, expiration, ratio, quote,
  quote time, and target/actual delta where present;
- modeled midpoint entry with explicit model/version and non-fill semantics;
- typed constructibility and liquidity;
- capital, maximum loss/profit, and breakeven as typed unknowns until OP-02
  supplies a mathematically compatible payoff model;
- deterministic rationale, assumptions, risk, and strategy-policy absence.

The projection has a deterministic identity and a canonical JSON-safe form.
Nonconstructible assessments remain typed unavailable and retain their exact
reason; they never become proposals.

## Boundary proof

The contract performs no provider acquisition, valuation, strategy
interpretation, persistence mutation, or broker action. Exact legs and entry
economics are copied only from the accepted execution-readiness authority.
Unsupported payoff quantities are never fabricated or silently set to zero.

## Validation

- focused trade-proposal and dependency-direction tests: green;
- full repository suite: 3,458 passed / 48 skipped;
- Ruff: green;
- mypy: green.
