# ASA-RES-STRATEGY-QUALIFICATION-002 — Deep research qualification of the six selected lanes

- **Role:** ROLE-RESEARCH (research method and status only; GOV-AMD-017)
- **Basis:** `main` @ 63f824c
  - The six lanes are the bundles that advanced in [ASA-STRATEGY-CAPABILITY-SELECTION-001](../../selection/ASA-STRATEGY-CAPABILITY-SELECTION-001/primitive-comparison-report.md).
- **Governance state:**
  - This assignment has no Founder-merged activation file under `docs/sprints/`, so there is no delegated merge. **Founder merge required.**
  - No `CLOSURE.md` is written.
  - ASA-RES-SPRINT-001 is not retroactively activated.
- **Status:** complete. **No implementation is authorized by these files.** Qualification states describe research evidence and specification completeness only. They do not rank lanes or choose what to build.

## Result

- 14 candidate specifications were written: 9 primaries and 5 alternates.
- **No candidate reached IMPLEMENTATION_READY_RESEARCH.**
- Two primaries reached **READY_WITH_EXPLICIT_UNKNOWNS**: Cboe PUT and Cboe BXM. Their signal, structure, lifecycle and sizing are fully sourced. The remaining unknowns are non-signal provider questions:
  - option trade prints for the VWAP entry price;
  - SOQ settlement values;
  - Treasury rates;
  - index dividend points.
- Fewer than the target 12 reached qualification. Per the assignment, the bar was not lowered, and each lane below states exactly why.

| Lane | Primaries specified | Ready (with explicit unknowns) | Alternates | Lane document |
|---|---|---|---|---|
| 1 Event volatility | 2 (both DEEP_RESEARCH_REQUIRED) | 0 | 1 (RESEARCH_REJECT) | [LANE-01](LANE-01-EVENT-VOL.md) |
| 2 Index put writing | 2 | **1 (PUT)** | 1 (INSUFFICIENT_EVIDENCE) | [LANE-02](LANE-02-INDEX-PUTWRITE.md) |
| 3 Index short volatility | 0 | 0 | 1 (DEEP_RESEARCH_REQUIRED) | [LANE-03](LANE-03-INDEX-SHORT-VOL.md) |
| 4 Covered call | 2 | **1 (BXM)** | 1 (INSUFFICIENT_EVIDENCE) | [LANE-04](LANE-04-COVERED-CALL.md) |
| 5 Option-implied information | 0 | 0 | 1 (RESEARCH_REJECT) | [LANE-05](LANE-05-OPTION-INFORMATION.md) |
| 6 Cross-sectional option returns | 2 (both DEEP_RESEARCH_REQUIRED) | 0 | 1 (INSUFFICIENT_EVIDENCE) | [LANE-06](LANE-06-CROSS-SECTIONAL-OPTION-RETURNS.md) |

**Architecture:** no candidate is ARCHITECTURE-INCOMPATIBLE. Every candidate maps to canonical facts, reusable derived facts, a manifest graph and a taxonomy structure primitive (P01, P03, P09, P10, P12). Two needs fall outside the P/A/X taxonomy and are flagged for Architect classification in [`capability-map.yaml`](capability-map.yaml):
- option trade prints;
- first-quote-after-time event capture.

## Files

| File | Content |
|---|---|
| `LANE-0n-*.md` | candidate survey, lane-specific mathematics, reason for fewer than two, evidence uncertainties |
| [`strategy-specifications/`](strategy-specifications/) | one specification per primary or alternate (14) |
| [`derived-fact-registry.yaml`](derived-fact-registry.yaml) | 35 deduplicated derived facts, with explicit formulas and ASA status |
| [`gate-registry.yaml`](gate-registry.yaml) | 47 source-defined gates with PASS/FAIL/UNKNOWN semantics |
| [`capability-map.yaml`](capability-map.yaml) | per-candidate existing and missing capabilities; gaps outside the taxonomy |
| [`qualification-matrix.yaml`](qualification-matrix.yaml) | one row per candidate with state, evidence, precision and unknowns |
| [`SELF-REVIEW.md`](SELF-REVIEW.md) | research PR self-review (`roles/researcher/REVIEW_TEMPLATE.md`) |

The source records are in `research/sources/`:
- 10 new records.
- 10 existing records extended with an appended `qualification_002_verification` block. Prior fields are unchanged.

## Method

1. **Full-text recovery**, in the assignment's preferred order:
   - peer-reviewed full text;
   - exchange methodology plus published evaluation;
   - working paper.

   Recovered: Cboe methodologies (PUT, PutWrite family, BuyWrite, BXRT, BXMVM); ALX 2025; the Xing-Zhang 2013 working paper; Zhan et al. (accepted manuscript); Cao-Han 2013; Heston et al. (December 2021 working paper); MPP (May 2022 conference version); Bakshi-Kapadia 2003; Carr-Wu 2009; Israelov-Nielsen 2015; Israelov-Klein-Tummala 2018; Wilshire 2019; Ennis Knupp 2008.

   Not obtained:
   - GXZ JFQA 2018 (paywall);
   - Coval-Shumway 2001 (blocked);
   - Goyal-Saretto 2009;
   - Xing-Zhang-Zhao 2010;
   - MPP final JFE (403);
   - the Heston JF typeset version.
2. **Specification.** Each rule was transcribed with its source location. Every missing rule was resolved in exactly one way:
   - recovered;
   - DERIVED, with the derivation stated (for example the zero-delta weight equivalence and the strict reading of "below");
   - preserved as UNKNOWN or AMBIGUOUS_SELECTION;
   - the candidate was deferred or rejected.

   No practitioner convention, ASA default, "reasonable" DTE or assumed sizing was used.
3. **Deduplication.** Every formula appears once in the derived-fact registry. Every threshold appears once in the gate registry.
4. **Qualification** uses the assignment's six states. IMPLEMENTATION_READY_RESEARCH would additionally require every canonical input to be confirmed available. PUT and BXM miss it only on provider questions.

## Final handoff (A–I per lane)

The questions are:
- **A.** Which specifications reached research qualification?
- **B.** What is the strategy mathematically?
- **C.** Which canonical and derived facts does it inherit?
- **D.** What are its gates?
- **E.** How does it choose legs?
- **F.** What is its lifecycle?
- **G.** What primitives does it consume?
- **H.** What evidence uncertainties remain?
- **I.** Could a worker author the manifest without a new financial-policy decision?

### Lane 1 — Event volatility

- **A.** None. Two primaries are specified at DEEP_RESEARCH_REQUIRED: the GXZ hold-to-expiry straddle and the ALX concavity-conditioned EAD straddle.
- **B.**
  - *GXZ:* buy an ATM straddle at the close of session −3 before day 0 and hold it to the first expiry after day 0. Payoff is intrinsic value.
  - *ALX:* on d−1, fit the IV curve and set CONCAVE; the measured object is the zero-delta straddle from close d−1 to close d.
- **C.**
  - *Canonical:* earnings date and time, chain quotes, deltas, IVs, OI, volume, S, r (ALX).
  - *Derived:* DF-EA-EFFECTIVE-DATE-GXZ / -ALX, DF-TRADING-SESSION-OFFSET, DF-OPT-MID, DF-OPT-MONEYNESS-SK / -KS, DF-OPT-DTE-CALENDAR, DF-ALX-BLENDED-IV-POINTS, DF-ALX-CONCAVE, DF-STRADDLE-ZERO-DELTA-WEIGHT, DF-STRADDLE-RETURN, DF-OPT-EFFECTIVE-PRICE.
- **D.** G-GXZ-* (12 gates shared by EV-01 and EV-A1) and G-ALX-* (7 gates), in gate-registry.yaml. The blockers are G-GXZ-HOLD-TO-EXPIRY-DTE and G-ALX-UNIVERSE-TOP100-VOLUME.
- **E.**
  - *GXZ:* same-strike call/put pairs passing the filters; volume weighting across multiple pairs (semantics UNKNOWN); leg ratio UNKNOWN.
  - *ALX:* the nearest-to-money pair, K/S 0.98–1.02, in the shortest 4–13-day expiry; ALX eq. 5 weights; equidistant ties are AMBIGUOUS.
- **F.**
  - *GXZ:* enter at the close of session −3; hold to expiry.
  - *ALX:* close d−1 to close d.
  - Neither has stops or rolls.
- **G.** P03 (HARD), X04 (ALX), A12 (diagnostic). Architect review: P03 multi-pair semantics, and the spline analytic.
- **H.**
  - GXZ: the published version was not accessed; there is no post-2010 test.
  - ALX: no net levels; the universe is look-ahead; the evidence is the conditional differential only.
  - The two eras conflict.
- **I.** **No.**
  - GXZ needs the DTE unit, leg ratio and multi-pair decisions.
  - ALX needs a live universe and a trade direction.

### Lane 2 — Index put writing

- **A.** **Cboe PUT: READY_WITH_EXPLICIT_UNKNOWNS.** WPUT is specified at DEEP_RESEARCH_REQUIRED.
- **B.** On each third-Friday roll date:
  1. Settle the expiring put at max(0, K_old − SOQ).
  2. Sell N_new next-month SPX puts struck at max{K ≤ S before 11:00 ET}, at the 11:30–12:00 ET VWAP.
  3. Hold the position fully collateralized in 1-month and 3-month T-bills.
- **C.**
  - *Canonical:* SPX value before 11:00, SPX chain and quotes, OPRA trades, SOQ, USBR 4- and 13-week rates, calendar.
  - *Derived:* DF-THIRD-FRIDAY-ROLL-DATE, DF-OPT-MID, DF-CBOE-TBILL-DAILY-ACCRUAL, DF-CBOE-PUT-CONTRACT-COUNT.
- **D.** G-CBOE-MONTHLY-ROLL-DATE, G-CBOE-SPX-REF-BEFORE-1100, G-PUT-STRIKE-EXISTS. There are no liquidity or market-state gates.
- **E.** One short put. Strike = max listed K ≤ S_ref, unique. Expiry = the next monthly AM-settled SPX.
- **F.** Hold to expiry, SOQ settlement, roll the same day. No targets or stops.
- **G.** X01, P01, X02a, X04 (HARD); A15 (collateral representation); GAP-OPTION-TRADE-PRINTS (outcome valuation only).
- **H.**
  - Index-only, sponsor-published evidence.
  - Net of costs UNKNOWN.
  - 2006–2018 Sharpe 0.50 vs S&P 500 0.51.
  - WPUT's AM-roll timing inconsistency.
  - No PUTY performance evidence.
- **I.** **PUT: yes** for the strategy graph. Tracking the VWAP entry price needs a data source ASA lacks; that is a provider and architecture question, not a financial rule. **WPUT: no** (AM-day ordering).

### Lane 3 — Index short volatility

- **A.** None. No primary was specified. One alternate: the Bakshi-Kapadia daily delta-hedged index call, DEEP_RESEARCH_REQUIRED.
- **B.** Buy one call and short Δ index units, rebalancing daily to the Black-Scholes delta, to expiry. The gain is DF-BK-DELTA-HEDGED-GAIN. This is a measurement design.
- **C.** S&P 500 option chain, index path, r (from put-call parity), dividends. DF-BK-DELTA-HEDGED-GAIN. The Carr-Wu variance-swap and realized-variance facts are registered for the lane.
- **D.** G-BK-OPTION-FILTERS.
- **E.** Every option-day passing the filters. There is no selection rule for a strategy.
- **F.** Hold to expiry with daily hedging. There is no entry schedule.
- **G.** X01, A14, P10.
- **H.** The phenomenon is strong. There is no tradable rule set, no sizing and no net results, and the GARCH volatility is look-ahead.
- **I.** **No.**

### Lane 4 — Covered call / buy-write

- **A.** **Cboe BXM: READY_WITH_EXPLICIT_UNKNOWNS.** BXMD is specified at DEEP_RESEARCH_REQUIRED.
- **B.** Hold the S&P 500 index (total return). On each third-Friday roll:
  1. Settle the expiring call at max(0, SOQ − K_old).
  2. Sell one next-month SPX call per index unit, struck at min{K ≥ S before 11:00 ET}, at the 11:30–13:30 ET VWAP.
- **C.**
  - *Canonical:* SPX value, chain and quotes, OPRA trades, SOQ, index dividend points, calendar.
  - *Derived:* DF-THIRD-FRIDAY-ROLL-DATE, DF-OPT-MID, DF-CBOE-BUYWRITE-DAILY-RETURN.
- **D.** G-CBOE-MONTHLY-ROLL-DATE, G-CBOE-SPX-REF-BEFORE-1100, G-BXM-STRIKE-EXISTS.
- **E.** One short call per index unit, strike = min listed K ≥ S_ref (unique), next-month expiry.
- **F.** Hold to expiry, SOQ settlement, roll the same day. No targets or stops. Assignment is not applicable (European, cash-settled).
- **G.** X01, P09, X02a (HARD); GAP-OPTION-TRADE-PRINTS; GAP-INDEX-DIVIDEND-POINTS. Architect review: P09 with a non-tradable index as the covered leg.
- **H.**
  - Index-only, sponsor-commissioned evidence.
  - Net UNKNOWN.
  - Israelov-Nielsen: the timing component is uncompensated.
  - BXMD's Black-formula inputs are undefined.
  - The BXM/BXMD distinctness is at the diversity-rule boundary.
- **I.** **BXM: yes** for the strategy graph, with the same provider caveats as PUT plus the P09 index-leg semantics. **BXMD: no** (delta inputs).

### Lane 5 — Option-implied information

- **A.** None. No primary was specified. One alternate: the MPP smirk decile, RESEARCH_REJECT.
- **B.** Daily decile sort on skew = IV(OTM put) − IV(ATM call). Short decile 10 stocks from close t+1 to close t+22.
- **C.** Chain IVs, S, Markit fee, stock returns. DF-XZZ-SMIRK-MPP, DF-OPT-MONEYNESS-KS, DF-XS-QUANTILE-ASSIGNMENT. Related: DF-CW-IV-SPREAD-OI-WEIGHTED, DF-OS-VOLUME-RATIO.
- **D.** G-MPP-VALID-PAIR, G-MPP-SKEW-COMPUTABLE.
- **E.** A stock position; option choice within the moneyness ranges is UNKNOWN.
- **F.** Hold 21 trading days after a one-day skip; overlapping daily formation.
- **G.** A10, P12, A06.
- **H.** Net of borrow, decile 10 is −0.21% (t −1.6). Predictability is concentrated in high-fee stocks. The final version was not accessed.
- **I.** **No** (and rejected).

### Lane 6 — Cross-sectional option returns

- **A.** None. Two primaries are specified at DEEP_RESEARCH_REQUIRED: Zhan −Ln(PRICE) delta-neutral call writing and Heston straddle momentum.
- **B.**
  - *Zhan:* at month end, sort optionable common stocks (P ≥ $5) into deciles on −ln P. Write ATM calls hedged with Black-Scholes-Δ shares in decile 10; buy delta-hedged calls in decile 1. Stock-VW. Hold one month without rehedging.
  - *Heston:* on each monthly expiration, sort on the mean zero-delta straddle return over lags 2–12. Go long the top quintile's straddles and short the bottom, equal-weighted, held to expiry.
- **C.**
  - *Canonical:* month-end closes, option chains, deltas, market cap (missing), security type (missing), a 12-month option history (A08).
  - *Derived:* DF-NEG-LN-PRICE, DF-DN-CALL-WRITE-RETURN, DF-CBOE-NAKED-MARGIN, DF-STRADDLE-MOMENTUM-FORMATION, DF-STRADDLE-ZERO-DELTA-WEIGHT, DF-STRADDLE-RETURN, DF-OPT-WEIGHTED-SPREAD, DF-XS-QUANTILE-ASSIGNMENT, DF-HESTON-SPAN-MARGIN.
- **D.** G-ZHAN-* (8 gates) and G-HES-* (5 gates). The blockers are G-ZHAN-NO-DIVIDEND-DURING-LIFE and the Heston replacement ordering.
- **E.**
  - *Zhan:* the ATM call (and put for eligibility), shortest maturity over one month, modal maturity.
  - *Heston:* the pair with call delta closest to 0.5 in [0.25, 0.75]; weighted spread ≤ 50%, otherwise a replacement further from the money (order UNKNOWN).
- **F.**
  - *Zhan:* month end to month end.
  - *Heston:* expiration to expiration.
  - Both re-form monthly; neither has stops.
- **G.** P10 / P03, P12, A15, X04, A08, A17, A12, plus the canonical gaps (security type, shares outstanding).
- **H.**
  - Zhan: the strongest net evidence (1.01%/month at the full quoted spread, t 5.48), but spanned by option factors; no post-2016 evidence.
  - Heston: net at conventional costs is not significant (t 1.75 effective, 0.75 quoted).
  - Cao-Han: marginal after costs.
- **I.** **No.**
  - Zhan needs the dividend filter, the long-leg capital convention and the weighting input.
  - Heston needs the replacement ordering and spread aggregation.

## Items for Founder or Architect attention (not decisions)

1. **Diversity-rule boundary.** BXM and BXMD differ in market-regime exposure (beta 0.55 vs 0.77) but share one mechanism under the Israelov-Nielsen decomposition.
2. **Gaps outside the taxonomy.** Option trade prints and quote-event capture have no P/A/X entry. They affect outcome valuation (PUT, BXM) and signal timing (WPUT) respectively.
3. **P09 semantics.** BXM's covered leg is the S&P 500 index itself. Substituting an ETF or futures proxy would be a different strategy requiring its own evidence.
4. **ASA `OptionContract.mark`** holds the provider's last trade, not the quote midpoint. Every source here uses the midpoint (DF-OPT-MID).
5. **Next research actions** (each would lift one blocker):
   - the GXZ JFQA text;
   - a Cboe clarification of WPUT's AM-day premium timestamp;
   - Cboe's BXMD delta inputs;
   - the Zhan replication package or appendix;
   - the Heston JF internet appendix;
   - an explicitly specified, independently evaluated SPX short-straddle or short-strangle rule.
