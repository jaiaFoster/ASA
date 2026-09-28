# STRATEGY-PRODUCTION-001 — SP-04A

Primary ticket: `SP-04A` — A15 short-option and straddle margin.

## Outcome

`DF-CBOE-NAKED-MARGIN@1.1.0` implements the reusable Cboe uncovered-option
formula with explicit alpha/beta parameters. This preserves the source-specific
equity (20%/10%) and broad-index (15%/10%) parameter sets as consumer policy,
not hidden analytics defaults. Missing or invalid option value, spot, strike,
or parameters remains typed UNKNOWN.

`DF-CBOE-STRADDLE-MARGIN@1.0.0` implements the canonical short-combination rule:
the greater call/put naked requirement plus the other option value. Equal leg
requirements resolve conservatively and deterministically. It is margin, never
terminal payoff or maximum loss.

`DF-OPTION-PROCEEDS-ACCRUAL@1.0.0` requires an explicit matched-period financing
return. Missing financing evidence remains UNKNOWN; zero financing is never
invented. All three formulas are strategy-neutral and provider-free.

## Authority

The combination rule follows Cboe's strategy-based margin schedule for short
put/call combinations. Strategy manifests remain responsible for parameter
values, quantities, financing series, and interpretation.
