# OPTIONS-PRODUCT-001 — OP-02 payoff model

Baseline: `main@cbb0837cab626dd7e1ab0f65c9a587815ae8e08f`  
Operational issue: [#470](https://github.com/jaiaFoster/ASA/issues/470)

## Model boundary

`strategy_runtime.option_payoff` adds deterministic exact-leg expiration
payoff for same-expiration structures. The model uses the already-resolved
legs and modeled midpoint entry, exposes deterministic scenario points,
bounded/unbounded maximum loss and profit, breakevens, multiplier, model
version, and an immutable identity.

Calendars fail closed from this terminal model with
`multiple_expirations_require_model_dependent_value`. Their later-expiring leg
continues through the existing versioned front-expiration model, which retains
time value and requires explicit volatility, rate, dividend, fill, and clock
assumptions. It remains labeled modeled P&L, never guaranteed payoff.

The public execution-readiness surface now offers a deterministic
`terminal-payoff` endpoint alongside the existing assumption-driven
`modeled-pnl` endpoint. The canonical trade proposal can consume a matching
terminal model to populate only mathematically supported payoff quantities;
undefined and unbounded values remain typed.

## Proof

- pinned 1:1 call vertical: `-400 / 0 / +600`, max loss `400`, max profit
  `600`, breakeven `104`;
- ratio short-call tail: maximum loss is explicitly unbounded;
- calendar counterexample: deterministic terminal endpoint refuses
  intrinsic-only substitution;
- existing calendar front-expiration vector remains green and retains back-leg
  time value;
- no provider acquisition, strategy-policy change, or broker mutation.

Validation: 3,464 repository tests passed / 48 skipped; Ruff and mypy green;
frontend generation, lint, typecheck, 7 tests, and production build green.
