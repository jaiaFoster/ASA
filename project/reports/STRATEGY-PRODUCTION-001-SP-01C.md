# STRATEGY-PRODUCTION-001 — SP-01C

## Outcome

X05 now has one provider-neutral canonical option-trade-tape contract and one
reusable, versioned windowed-VWAP calculation. Quotes, contract marks and
midpoints cannot enter the VWAP formula.

## Canonical evidence

- Capability: `option_trade_tape_v1`.
- `OptionTrade` preserves source trade identity, exact option-contract
  identity, price, size, event time, ASA observation time, and raw normalized
  sale-condition codes.
- `OptionTradeTape` is one deterministic event-time-ordered collection for one
  exact contract. Duplicate prints, mixed contracts, and impossible observation
  timing fail closed.
- Tape and observation identities are content-derived and round-trip through
  the existing immutable market-data serialization/replay contract.

## Derived fact

- Feature: `windowed_option_trade_vwap@1.0.0`.
- Formula: `DF-OPTION-TRADE-WINDOW-VWAP@1.0.0`.
- The caller supplies the exact timezone-aware event-time window and explicit
  sale-condition exclusion set required by its source methodology.
- Eligible prints are weighted by reported trade size.
- Missing tape returns typed `option_trade_tape_unavailable`; a window with no
  eligible prints returns typed `no_eligible_option_trades_in_window`.

## Boundaries

- No provider is falsely declared capable of supplying X05.
- No last trade, option mark, quote midpoint, or synthetic print is substituted.
- No strategy-ID branch, strategy-private formula, provider routing, or broker
  mutation was introduced.

## Verification

Pinned tests cover event-time endpoints, size weighting, sale-condition
exclusion, deterministic ordering/identity, immutable serialization, invalid
contract/timing rejection, typed absence, and registry ownership.
