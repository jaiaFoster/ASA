# OPTIONS-PRODUCT-001 — OP-03 user-first trade card

Baseline: `main@a33d7a2`  
Operational issue: [#472](https://github.com/jaiaFoster/ASA/issues/472)

## Product projection

The Agent Data API now exposes the canonical trade-proposal contract for one
current strategy/symbol identity. It verifies current result/readiness
identity and immutable assessment integrity before projecting exact legs. A
nonconstructible assessment remains a typed unavailable response.

The Intelligence Console detail page now leads actionable option results with
a trade card that shows:

- the underlying, strategy/version, and intended structure;
- explicit BUY/SELL leg directions, quantity, call/put, expiration, strike,
  bid/ask/mid;
- modeled midpoint entry, constructibility, liquidity, and typed payoff
  quantities;
- expandable rationale, risks/invalidation, and evidence snapshot identity.

The card is labeled analytical and not an order. Existing decision semantics,
exact readiness, named facts, modeled-P&L controls, and raw evidence remain
available below it. The UI does not reconstruct or own financial truth.

## Proof

- API route pins current identity and exact-leg projection;
- generated OpenAPI/TypeScript contract includes the additive route;
- DOM behavior test proves exact two-leg rendering and expandable rationale;
- mobile layout collapses exact legs without omitting them;
- no provider acquisition, broker mutation, or signal-semantic change.

Validation: 3,466 repository tests passed / 48 skipped; 15 Intelligence
Console DOM tests and 7 frontend tests passed; generation, lint, typecheck, and
production builds are green.
