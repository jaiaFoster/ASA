# SPRINT-008D — PROD-001: Production Screening Universe Definition

Status: Complete.

Sprint reference: `docs/sprints/SPRINT-008D.yaml`
Repository commit at definition time: `0ee7707` (`main`)

## 1. Objective

Define and justify an initial production screening universe — which registered signals run
against which symbols — bounded by the existing `screening.live_acquisition.APPROVED_LIVE_UNIVERSE`,
and document a future expansion strategy. This ticket defines the universe; PROD-002 executes
against it.

## 2. Constraint this universe must respect

`APPROVED_LIVE_UNIVERSE = ("AAPL", "MSFT", "NVDA", "AMD", "SPY", "QQQ")` is the existing,
Founder-approved, code-enforced bound on live acquisition (`screening/live_acquisition.py`'s own
docstring: "The SPRINT-007 Founder-approved live validation_universe"). Both
`screening/cli.py`'s `--live` flag and `POST .../refresh` already bound to this exact set — PROD-001
does not, and per its own ticket exclusion cannot, widen it. Everything below selects a subset of
signal/symbol pairs *within* this existing bound; expanding the bound itself is PROD-005's own
question, evaluated separately and later, informed by real usage this universe produces.

## 3. Data-requirement audit — what each registered signal actually needs

| Signal | `required_capabilities` (declared, `screening/registry.py`) | Provider(s) that can supply it |
|---|---|---|
| `forward_factor` | `option_chain_v1` | **Tradier only** |
| `skew_momentum` | `option_chain_v1` | **Tradier only** |
| `earnings_calendar` | `earnings_calendar_v1`, `option_chain_v1` | `earnings_calendar_v1`: Finnhub or Alpha Vantage. `option_chain_v1`: **Tradier only** |

Checked directly against each provider's own declared capability tuple
(`market_data/tradier.py::TRADIER_CAPABILITIES`, `market_data/finnhub.py::FINNHUB_CAPABILITIES`,
`market_data/alpha_vantage.py::ALPHA_VANTAGE_CAPABILITIES`), not assumed: **no enabled provider
other than Tradier supplies `option_chain_v1` at all**, and every one of the three registered
signals requires it. `earnings_calendar` additionally requires a second provider
(`earnings_calendar_v1`, which Tradier does not supply) to be both enabled and actually working.

## 4. Initial universe

**`forward_factor` × {AAPL, MSFT, NVDA, AMD, SPY, QQQ}** and
**`skew_momentum` × {AAPL, MSFT, NVDA, AMD, SPY, QQQ}** — 12 signal/symbol pairs, the full
`APPROVED_LIVE_UNIVERSE` for both signals whose data requirement is satisfied by exactly one
already-enabled, single-provider dependency (Tradier).

**`earnings_calendar` is deliberately excluded from this initial universe.** Its
`earnings_calendar_v1` requirement depends on Finnhub or Alpha Vantage, and this sprint's own
handoff separately asks PROD-004 to investigate a reported Finnhub authorization issue. Running
`earnings_calendar` in the first production execution, before that investigation completes,
risks populating `screening_state` with results derived from a provider path already flagged as
degraded — or silently failing every earnings_calendar pair for reasons unrelated to the market
data itself. Deferred, not abandoned: see Section 6.

## 5. Justification for the symbol set

The six symbols are not re-chosen here — they are inherited unchanged from
`APPROVED_LIVE_UNIVERSE`, per this ticket's own exclusion against widening that bound — but it is
still worth recording why this set remains appropriate for *screening* use, not only for the
*validation* use it was originally approved for (SPRINT-007): AAPL, MSFT, NVDA, and AMD are
among the most liquid U.S. single-name options markets that exist, and SPY/QQQ are the two
highest-volume U.S. index ETF options markets. Every one of `forward_factor`'s and
`skew_momentum`'s manifests (`strategies/stonk_manifests.py`) operates on option chains and
requires selecting specific strikes/expirations from real market depth
(`select_atm_strike_at_expiration`, `select_expiration_pair`) — a thin or illiquid chain would
produce degraded or missing results regardless of code correctness. This symbol set is exactly
the kind of market where that data requirement is reliably met, which is precisely why it was
approved for live validation in the first place; the same property makes it appropriate for a
first production screening universe.

## 6. Future expansion strategy

Two independent expansion axes, deliberately not conflated:

1. **Signal expansion within the existing symbol bound**: add `earnings_calendar` × the same six
   symbols once PROD-004 confirms the `earnings_calendar_v1` provider path (Finnhub and/or Alpha
   Vantage) is healthy. No universe redefinition needed beyond that confirmation — the pairs are
   already implied by `APPROVED_LIVE_UNIVERSE` and the existing registry.
2. **Symbol expansion beyond the current six**: out of this ticket's own scope entirely.
   PROD-005 evaluates this properly, informed by real request-budget and execution-timing data
   PROD-002 will produce — this ticket does not pre-judge that evaluation or propose specific
   additional symbols. The only criterion recorded here, for PROD-005 to apply rather than
   invent: any candidate symbol should meet the same liquidity bar this section just described
   for the existing six, since that bar is what the signals' own data requirements actually
   depend on, not an arbitrary popularity or market-cap threshold.

## 7. Conclusion

Initial production universe: 12 signal/symbol pairs (`forward_factor` and `skew_momentum`, each
against all six `APPROVED_LIVE_UNIVERSE` symbols). `earnings_calendar` deferred pending PROD-004.
No code or configuration changes were made by this ticket — it is a definition and its written
justification, ready for PROD-004 (provider validation) and then PROD-002 (execution) to build
on, per this sprint's own `execution.ticket_order`.
