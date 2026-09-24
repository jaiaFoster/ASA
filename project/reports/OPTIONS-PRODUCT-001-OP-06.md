# OPTIONS-PRODUCT-001 — OP-06

## Outcome

`Track This` now preserves the exact canonical option trade proposal attached to
the selected screening observation. Tracking is an ASA lifecycle mutation only:
it does not place an order, claim a fill, or mutate brokerage state.

## Ownership and reuse

- Reused the existing `TrackCandidateService`, lifecycle repository, and
  `/api/v1/portfolio/tracked-candidates` endpoint.
- The client submits only the strategy, symbol, and immutable observation
  identity. The server reconstructs the proposal from the authoritative
  persisted result and execution assessment.
- Modern execution-readiness artifacts persist the canonical
  `OptionTradeProposal` identity and exact-leg JSON. Historical pre-proposal
  artifacts remain readable and immutable through the existing assessment
  representation.
- Repeated tracking is idempotent. Later readiness refreshes do not rewrite the
  originally tracked proposal.

## Product behavior

- Constructible proposals expose `Track This` and an explicit no-order/no-fill
  disclosure.
- Tracked proposals display their durable lifecycle identity.
- Non-constructible proposals remain untrackable and preserve their typed
  blocker presentation.

## Verification

- Focused portfolio lifecycle, API/UI route, and proposal tests pass.
- Direct Intelligence Console DOM tests pass, including the tracking action and
  non-constructible negative case.
- Full repository and required static validation are recorded on the OP-06 PR.

## Boundaries

- No broker/provider call or mutation was added.
- No order, fill, execution, signal, strategy, or payoff semantics changed.
- No new lifecycle or market-data authority was introduced.
