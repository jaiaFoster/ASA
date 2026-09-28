# STRATEGY-PRODUCTION-001 — SP-03B

Primary ticket: `SP-03B` — Cboe PUT production strategy.

## Outcome

`index_putwrite_cboe_put@1.0.0` is registered through the universal
subject-first runtime on fixed subject `SPX`. Its manifest owns the sourced
monthly roll, pre-11:00 ET reference, next-month standard AM-settled SPX put,
and closest-listed-strike-not-above-reference rules. A non-roll date produces
`NO_ACTION`; missing reference, root/settlement identity, chain, or eligible
strike remains typed `UNKNOWN`.

The exact selected short put projects through generic `P01`. The proposal is a
one-whole-contract executable unit under disclosed `IA-PUT-01`; portfolio-scale
fractional sizing remains a separate capital input. The source equations are
owned by `DF-CBOE-PUT-CONTRACT-COUNT@1.0.0`, and cash collateral remains owned
by `DF-CASH-SECURED-PUT-COLLATERAL@1.0.0`. Neither is replaced with vertical
maximum loss.

X05 entry VWAP is explicitly `UNKNOWN` while authoritative option prints are
unavailable. Quote midpoint, option midpoint, and last trade are not accepted
as substitutes. The SPX reference likewise requires the authoritative last
value and never falls back to bid/ask midpoint. Expiration selection requires
the standard monthly cycle; an earlier weekly expiration cannot preempt it.
SOQ and Treasury evidence remain declared canonical requirements for
lifecycle/outcome accounting; the result projects explicit typed lifecycle
and sizing `UNKNOWN` states until those facts are materialized. No proxy is
invented. Contract-count equations accrue each prior-period Treasury sleeve
before settlement loss and roll sizing.

## Production path

- Registry, subject preparation, catalog, cutover, and resolution declarations: wired.
- Scheduler: fixed subject `SPX`, isolated through the generic fixed-subject path.
- Generic API/UI and tracking/outcome projection: inherited from the universal result path.
- Provider-blind strategy execution and exact sealed snapshot provenance: preserved.

## Verification

Focused truth-table, root/settlement, selection, registry, scheduler, formula,
identity, and proposal tests plus exact-head repository validation are recorded
on the PR.

- Focused ticket suite: `75 passed`.
- Full repository suite: `3,879 passed, 50 skipped`.
- Ruff, mypy, and Lean pre-push validation: green.
