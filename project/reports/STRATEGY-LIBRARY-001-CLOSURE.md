# STRATEGY-LIBRARY-001 — SL-05 observation and sprint closure

State: `OBSERVATION_PASS` → `CLOSED` **with a recorded SL-02 target downgrade**
Production SHA observed: `8c97b834cc9e8cbc938dfd709b2d5e4ceeb560cb` (verified via `/api/v1/version`)
Captured: 2026-09-24 ~21:35Z (after the regular session; latest persisted state)

## Delivered

| Ticket | PR | Outcome |
|---|---|---|
| SL-01 | #487 | Architect decision: one manifest-first authoring path (ADR-010, no amendment); intake template; guide corrected |
| SL-03-00 | #488 | B001/B002 brought into manifest conformance (only prior deviation) |
| SL-04 | #487 | Strategy library view (declared contracts × current coverage, no ranking) |
| SL-02 | #489 | `spy_put_credit_spread` (Option Alpha SPY PCS backtest 1), independently reviewed |
| SL-03 | — | `stock_momentum` skipped (portfolio/news/theme-list source semantics) |

Adding the strategy was a bounded composition task: no new component,
capability, derived fact, schema, API shape, or authority; one manifest, one
planning module, one knowledge mapping, one contract, one subject-first
binding, and one declared scheduler pair.

## SL-05 production observation

- **Trade-card path** ([`…-SL-05-trade-card.json`](STRATEGY-LIBRARY-001-SL-05-trade-card.json)):
  verdict `complete_trade_card_path_observed`; 2 complete cards, 3 typed
  failures, 0 defects. The new strategy's live card: sell SPY 2026-10-23 755P
  (Δ −0.299), buy 715P (Δ −0.097), modeled credit 4.595, deterministic max
  loss 3,540.50, max profit 459.50, breakeven 750.405; capital required
  typed `capital_requirement_not_defined_for_structure`.
- **Funnel census** ([`…-SL-05-census.json`](STRATEGY-LIBRARY-001-SL-05-census.json)):
  1,510 / 1,510 active option rows traced across four strategies; **zero
  unexplained drops**.
- **Capability pressure:** the new strategy adds 3 provider demands per cron
  tick (quote + expirations + one chain), 1 attempt each, 0 failures, no
  cross-consumer reuse (it runs on its own isolated fixed-subject
  invocation). Screening operations show 0 batch failures and 0 incomplete
  diagnostics; the overdue-subject count reflects the pre-existing
  after-hours cohort gating. No procurement blocker.

## SL-02 target downgrade (explicit, not a pass)

The sprint targeted 2–4 additional option strategies. One was implemented.
Every other researched candidate was skipped under the sprint's own rule
("skip candidates whose material semantics the source does not define";
never lower the explicitness bar):

- **Cboe CNDR iron condor** — Architect decision
  ([`…-SL-02-CNDR-ARCHITECT-DECISION.md`](STRATEGY-LIBRARY-001-SL-02-CNDR-ARCHITECT-DECISION.md)):
  needs additive ARCH-005 public-contract amendments (index underlying;
  typed option root/settlement style) behind ADR-010's Founder review floor,
  plus a Black-delta fact. Not uniquely necessary → deferred, not escalated.
- **Cboe PUT** — same SPX gaps plus a single-leg structure.
- **Gao/Xing/Zhang pre-earnings straddle** — explicit but averages over all
  qualifying strike/expiry pairs with no selection rule, and needs a new
  STRADDLE structure kind ([`…-SECOND-CANDIDATE-SEARCH.md`](STRATEGY-LIBRARY-001-SL-02-SECOND-CANDIDATE-SEARCH.md)).
- **Other public rule sets** — IV-Rank-dependent (not acquired),
  contradictory, proprietary, or cosmetic variants of the SPY PCS.

**Smallest Founder decision that would unlock more breadth (optional, not a
blocker):** approve one additive ARCH-005 amendment — `InstrumentKind.INDEX`
plus typed option root/settlement style on `OptionContract` — which would let
the Architect-scoped CNDR intake proceed.

## Closure

STRATEGY-LIBRARY-001 is closed with the downgrade above recorded. Any later
falsifying observation reopens it per the program rule.
