# ASA-QS-EV-01-GXZ-PREEA-STRADDLE-TO-EXPIRY — long ATM straddle bought 3 sessions before earnings, held to expiry

- **Lane:** 1, event volatility
- **Role:** PRIMARY
- **Qualification state:** **DEEP_RESEARCH_REQUIRED**
- **Source methodology version:** Xing and Zhang, "Anticipating Uncertainty: Straddles Around Earnings Announcements", SSRN 2204549, working paper dated January 14, 2013, full text. This is the precursor of the published Gao-Xing-Zhang paper; the working paper lists only Xing and Zhang as authors. ([`GAO-XING-ZHANG-2013-WP`](../../../sources/GAO-XING-ZHANG-2013-WP.yaml)). Specifically, **Section 5 and Table 6** ("Holding the option from 3 days before EA to maturity").
  - The published version (JFQA 53(6), 2018; [`GAO-XING-ZHANG-2018`](../../../sources/GAO-XING-ZHANG-2018.yaml)) was **not accessible** (publisher paywall). Its abstract reports 3.34% for [−3,0], against 3.00% in this preprint's equal-weighted delta-neutral results, so **the versions differ**. Every rule below is pinned to the 2013 preprint.

## Why this expression, and why not the headline [−3,0] round trip

- **The headline round trip fails on costs.** GXZ's headline result buys a delta-neutral straddle at the close of day −3 and sells at the close of day 0. The authors themselves show it is unprofitable after costs: "Even if we use 50% of the quoted spread … with average 3-day return of 3%, and around 11% relative spread for a round trip trade, this strategy would deliver a 3-day return of −8%". That rule is recorded as the rejected alternate ASA-QS-EV-A1.
- **The authors' cost-reducing variant.** They propose, and test, the hold-to-maturity variant specified here, which avoids the exit spread.

## 1. Evidence qualification

| Item | Finding | Source |
|---|---|---|
| Phenomenon | Implied volatility rises into earnings and straddles bought shortly before the announcement earn positive average returns; the authors interpret this as investors underestimating event uncertainty. Equal-weighted delta-neutral [−3,0] 3.00%. | GXZ 2013 WP, full text |
| Exact-strategy evidence (Table 6, Panel A; 1996–2010; n = 8,273 straddles with 4–10 days to maturity) | "Daily return" 0.0164 (t 5.14) at 50% of quoted spread; 0.0061 (t 2.08) at 100% (buy at the day −3 closing ask, payoff = intrinsic value at maturity).<br>11–20 days: 0.0015 (t 1.64) / −0.0023 (t −2.72).<br>21–30 and 31–50 days: significantly negative at both cost levels. | GXZ 2013 WP Table 6, full text |
| Within-group dependence | Panel B, 4–10 days, 100% spread: low past spread 0.0116 (t 2.85); high past spread −0.0018 (t −0.45). The low/high split uses the **within-quarter median** of past spreads (not live-implementable, see §18). | GXZ 2013 WP Table 6 |
| Definition of "daily ret" | Not defined in the table notes. The text: "If the holding period is 4 days, the cumulative return becomes 7%", which is consistent with the holding-period return divided by holding days (INFERENCE). | GXZ 2013 WP |
| Independent replication | none recovered for the hold-to-expiry variant. The ALX RoF 2025 study finds a mean one-day EAD straddle return of −0.86% for large, liquid firms, 2013–2020. That is a **different window and universe**, but it is contrary evidence for unconditional pre-announcement straddle buying in the recent period. | ALEXIOU-ET-AL-2025 |
| Post-publication | not recovered for this rule | — |
| Gross vs net | Net is reported only in the 50%/100% effective-spread form on entry; there is no exit cost (payoff at intrinsic). Commissions are not modelled. | GXZ 2013 WP |
| Tail | not reported | UNKNOWN |
| Evidence confidence | LOW–MEDIUM: single study, preprint only, 1996–2010 | INFERENCE |

## 2. Universe

U_t = { US stocks i with a scheduled earnings announcement whose day 0 satisfies session(day0, −3) = t, with at least one call–put pair c passing all option gates, and whose option expires after day 0 }

- **Sample basis:** OptionMetrics, January 1996 – December 2010.
- **Look-ahead restriction:** day 0 must be known at t. GXZ use the I/B/E/S announcement date and do not describe a pre-announcement "scheduled" confirmation rule. Whether a confirmed-in-advance date is required is **UNKNOWN**. The text notes the date "is public information long before the actual announcement", which is an INFERENCE, not a rule.

## 3. Canonical facts

| Fact | Unit | Observation | ASA status | Missing |
|---|---|---|---|---|
| earnings_date(i) | date | before t | EARNINGS_CALENDAR_V1 | UNKNOWN |
| S_i(t) close | USD | close of day −3 | HISTORICAL_BARS_V1 / REAL_TIME_QUOTE_V1 | UNKNOWN |
| call/put bid, ask at close | USD | close of day −3 | OPTION_CHAIN_V1 | UNKNOWN |
| delta (call, put) | [−1, 1] | close of day −3 | OPTION_CHAIN_V1. **Provider delta ≠ OptionMetrics delta: equivalence UNKNOWN.** | UNKNOWN |
| open interest | contracts | day −3 | OPTION_CHAIN_V1 | UNKNOWN |
| volume (for multi-pair weighting) | contracts | **date UNKNOWN** | OPTION_CHAIN_V1 | UNKNOWN |
| S_T at expiry (payoff) | USD | expiration | closing/settlement convention **UNKNOWN**. Equity options settle by physical delivery; the source uses "the in the money amount". | UNKNOWN |

## 4. Derived facts

- DF-EA-EFFECTIVE-DATE-GXZ
- DF-TRADING-SESSION-OFFSET
- DF-OPT-MID
- DF-OPT-MONEYNESS-SK
- DF-OPT-EFFECTIVE-PRICE
- DF-OPT-HOLDING-RETURN
- DF-STRADDLE-RETURN

DF-STRADDLE-ZERO-DELTA-WEIGHT applies **only if** Table 6 straddles are delta-neutral, which is UNKNOWN (§10).

## 5. Fact ownership

| Input | Class |
|---|---|
| earnings date, quotes, deltas, OI, volume, S | CANONICAL_FACT |
| effective day 0, session offset, mid, moneyness, returns | DERIVED_FACT |
| −3 sessions; [0.375, 0.625]; [0.95, 1.05]; $5; $0.125; [4, 10] days | STRATEGY_PARAMETER |
| G-GXZ-* gates | STRATEGY_GATE |
| call/put pair per stock; volume weighting across pairs | STRUCTURE_SELECTION_RULE (**leg ratio ambiguous**, §10) |
| hold to first maturity after day 0 | PORTFOLIO_OR_LIFECYCLE_RULE |

## 6. Gates

All are defined in gate-registry.yaml:

| Gate | Status |
|---|---|
| G-GXZ-EA-DATE-KNOWN | |
| G-GXZ-ENTRY-SESSION | |
| G-GXZ-STOCK-PRICE-MIN | |
| G-GXZ-OPT-MID-MIN | |
| G-GXZ-QUOTE-VALID | |
| G-GXZ-ARBITRAGE-BOUNDS | |
| G-GXZ-ABS-DELTA-BAND | |
| G-GXZ-OI-POSITIVE | |
| G-GXZ-MONEYNESS | |
| G-GXZ-EXPIRES-AFTER-EA | |
| G-GXZ-HOLD-TO-EXPIRY-DTE | **research blocker** |

G-GXZ-HOLD-TO-EXPIRY-DTE is a blocker for two reasons:
- **Unit ambiguity.** Calendar vs trading days is not stated. The paper notes options then expired on the third Saturday, which suggests calendar days (INFERENCE).
- **Filter conflict.** The paper's main-sample maturity filter (10–60 days) cannot coexist with a [4, 10] group, and the filter set actually used for Table 6 is not stated.

## 7. Verdict truth table

| EA-KNOWN | ENTRY-SESSION | stock & option gates | EXPIRES-AFTER-EA | DTE [4, 10] | Verdict |
|---|---|---|---|---|---|
| FAIL | * | * | * | * | FAIL (not eligible) |
| * | FAIL | * | * | * | NO_ACTION |
| UNKNOWN | * | * | * | * | UNKNOWN |
| PASS | PASS | any FAIL | * | * | FAIL |
| PASS | PASS | any UNKNOWN | * | * | UNKNOWN |
| PASS | PASS | PASS | FAIL | * | FAIL |
| PASS | PASS | PASS | PASS | UNKNOWN (always, currently) | UNKNOWN |
| PASS | PASS | PASS | PASS | PASS | PASS: buy the straddle |

## 8. Score

NONE. Table 6 groups are reporting cells, not a score.

## 9. Direction

| Dimension | Direction |
|---|---|
| delta | neutral at entry (if delta-neutral weights apply; otherwise approximately neutral for ATM pairs) |
| volatility | positive |
| theta | negative |
| event exposure | long the announcement move |
| after entry | not rebalanced; delta drifts |

## 10. Structure selection (P03 straddle)

- **Pair.** One call and one put on the same underlying, strike and expiration, passing all option gates. That the same strike is required is DERIVED from "straddle". The expiration is the first maturity after day 0 ("hold it until option's first maturity after earnings announcement").
- **Multiple qualifying pairs.** "In the case when one stock has more than one pair of short term at the money straddles, we adopt volume weighting."
  - Whose volume, on which date, and whether call + put volume is used: **UNKNOWN**.
  - Whether this means holding several pairs weighted by volume (INFERENCE from "weighting") needs **P03 multi-pair semantics**.
- **Leg ratio: UNKNOWN.** GXZ's main results use "delta-neutral straddles … weights adjusted to make straddle delta zero" (with the ratio then given by DF-STRADDLE-ZERO-DELTA-WEIGHT, a DERIVED equivalence). The Table 6 notes do not say whether the hold-to-maturity straddles are delta-neutral or simple.
- **Tie rule:** not needed for pair choice, because all qualifying pairs are held with volume weights, subject to the multi-pair semantics above.

## 11. DTE

days_to_T(c, day −3) ∈ [4, 10] for the reported group. The unit is UNKNOWN (§6).

## 12. Entry timing

- entry_session = session(day0, −3)
- entry_time = close
- Price:
  - closing ask in the 100%-spread case;
  - mid + 0.25·(ask − bid) in the 50% case (DF-OPT-EFFECTIVE-PRICE).
- The price convention is an evaluation assumption, not a signal input.

## 13. Lifecycle

| Stage | Rule |
|---|---|
| Entry | §12 |
| Holding | to first maturity after day 0 |
| Exit | payoff = intrinsic value at maturity ("if the option is in the money, we use the in the money amount") |
| Profit target, stop, roll, re-entry | none (not sourced) |
| Positions per stock | one straddle position per announcement (DERIVED) |

## 14. Sizing

**SIZING = UNKNOWN.** Returns are averaged "across straddles in each group" (equal weight across straddles), with volume weights across pairs within a stock. No capital allocation per position is defined.

## 15. Transaction costs

- **Entry:** effective spread of 50% or 100% of quoted; closing ask at 100%.
- **Exit:** none (intrinsic payoff).
- **Commissions, exercise/assignment costs:** not modelled. The equity options in the sample are physically settled American options, and exercise mechanics are not addressed.
- **gross_result:** Table 6 has no zero-cost column.
- **net_result:** the 50% and 100% columns reported above.

## 16. Capital and margin

Long premium only. Maximum loss = premium paid. There is no margin.

## 17. Liquidity

The sourced gates are: bid > 0, bid < ask, mid ≥ $0.125, OI > 0, arbitrage bounds. The past-spread split (Panel B) is **not** a gate (§18). A12 is used for diagnostics.

## 18. UNKNOWN / invalid states

| Condition | Outcome |
|---|---|
| DTE unit and Table 6 maturity filter | RESEARCH BLOCKER → UNKNOWN |
| delta-neutral vs simple straddle in Table 6 | RESEARCH BLOCKER (leg ratio) |
| multi-pair volume weighting (volume date/definition) | UNKNOWN; requires P03 multi-pair semantics |
| "low past spread" conditioning | not live-implementable as sourced: within-quarter median across the same quarter's straddles (look-ahead), past-spread window unstated. **Excluded from this specification.** |
| provider delta vs OptionMetrics | UNKNOWN equivalence |
| day 0 unconfirmed | UNKNOWN |
| settlement value S_T definition | UNKNOWN |

## 19. Provenance

| Object | Source | Depth | Direct / inferred |
|---|---|---|---|
| filters ($5, $0.125, bounds, delta band, OI, moneyness) | GXZ 2013 WP §2 | full text | direct |
| day −3 close entry, hold to first maturity, intrinsic payoff, ask price at 100% | GXZ 2013 WP §5 | full text | direct |
| [4, 10] group results | Table 6 | full text | direct |
| DN weight formula | — | — | DERIVED (applicability UNKNOWN) |
| DTE unit | — | — | UNKNOWN |
| sizing | — | — | UNKNOWN |

## 20. ASA translation sheet

| Field | Value |
|---|---|
| strategy_id_candidate | `event_vol_gxz_preea_straddle_to_expiry` |
| lane | event volatility |
| source_methodology_version | GXZ working paper 2013-01-14, §5 and Table 6 |
| required_market_capabilities | EARNINGS_CALENDAR_V1, OPTION_CHAIN_V1, REAL_TIME_QUOTE_V1, TRADING_CALENDAR_V1 |
| canonical_facts | §3 |
| derived_facts_existing | days_to_expiration (partial), earnings timing (partial) |
| derived_facts_new | §4 |
| strategy_parameters | §5 |
| gates | §6 |
| direction | §9 |
| structure_primitive | **P03** (leg ratio and multi-pair semantics unresolved) |
| structure_selection_rules | §10 |
| score | NONE |
| verdict_truth_table | §7 |
| lifecycle | §13 |
| sizing | UNKNOWN |
| cost_model | effective-spread entry |
| capital_model | premium at risk |
| unknown_states | §18 |
| current_ASA_reuse | earnings calendar, expiration selection facts, verdict classifier |
| missing_reusable_primitives | P03 (HARD), A12 (diagnostic), A09 not required by this rule |
| architecture_review_required | P03 multi-pair (volume-weighted) semantics |

## 21. Manifest readiness

**Not ready.** An implementer would have to decide three things:
- the DTE unit and applicable filter;
- delta-neutral vs simple weighting;
- multi-pair weighting.

Each of these affects which positions are proposed and in what ratio.

Required research action: obtain the published JFQA 2018 text (Section 5 / hold-to-maturity table) and check whether it resolves these three points.
