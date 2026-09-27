# ASA-QS-SV-01-SCS-SHORT-NEAR-ATM-STRADDLE — monthly short near-maturity ATM S&P 500 straddle

- **Lane:** 3, index short volatility
- **Role:** PRIMARY. Added in the closeout targeted pass (task 2, blocker 6).
- **Qualification state:** **READY_WITH_EXPLICIT_UNKNOWNS**
- **Source methodology version:** Santa-Clara and Saretto, "Option strategies: Good deals and margin calls", *Journal of Financial Markets* 12(3), 2009, 391–417. Full text reviewed 2026-09-27 from the UCLA Anderson working-paper copy ([`SANTACLARA-SARETTO-2009`](../../../sources/SANTACLARA-SARETTO-2009.yaml)).
  - The strategy is the paper's "Straddle N ATM" in the **short** direction.
  - Rules are pinned to §1–§2, Table 1, Table 10 and §4.2.

## Why this rule and not a variant

The paper evaluates short straddles and strangles at two maturities (N ≈ 45 days, F ≈ 180 days) and three moneyness levels (ATM, 5%, 10% OTM).
- **N ATM straddle:** the lane's P03 expression. Its after-spread result is positive in the SPX sample.
- **Strangles:** would need a strangle primitive (P04, not advanced) and are strike variants of the same mechanism.
- **Far-maturity versions:** turn negative after costs.

No other variant is selected (two-strategy diversity rule).

## 1. Evidence qualification

| Item | Finding | Source |
|---|---|---|
| Exact-strategy evidence, SPX (OptionMetrics, Jan 1996 – Dec 2002; Table 10) | **Mid-price:** mean 15.2% per month, SD 28.6%, monthly Sharpe 0.533.<br>**Bid-to-ask** (sell at bid, buy back at ask): mean **10.3% per month**, SD 29.3%, monthly Sharpe **0.351**. | SCS Table 10, full text |
| Exact-strategy evidence, S&P 500 futures options (CME, Jan 1985 – May 2001; Table 3, gross) | short near-maturity ATM straddle about 14% per month, Sharpe 0.273 | SCS §3 |
| Costs | "the bid-ask spread accounts for a loss of 4.9% in the near-maturity straddle" per month | SCS §4.1 |
| Margin (contradictory for leveraged sellers) | With CBOE margins (α 15%, β 10%) and margin calls met by liquidating other holdings, the best margin-adjusted portfolio (long market + short N ATM straddle, 7.5% of wealth) earns 0.9% per month (Sharpe 0.128). After the 4.9% spread cost this is about 0.53% per month (Sharpe about 0.032). The authors: "transaction costs and margin calls pose a formidable barrier to shorting options". | SCS §4.2, Table 12 |
| Independent replication | Coval-Shumway (2001) report short near-maturity ATM S&P straddles with high returns (cited by SCS; full text not accessed) | COVAL-SHUMWAY-2001 (bibliographic) |
| Evidence direction | **MIXED / QUALIFIED.** Positive after the quoted spread. Unfavorable after margin calls when the position is levered inside a wealth portfolio. | INFERENCE |
| Tail | Short straddle: unbounded loss on the call side, large loss on the put side. The 1985–2001 futures sample includes October 1987. | INFERENCE |
| Evidence confidence | MEDIUM for the phenomenon; LOW–MEDIUM for implemented net returns | INFERENCE |

## 2. Universe

U_t = { SPX (European, cash-settled) call and put options observable at the close of the first trading day of month m }.

**Research assumption RA-SV-01:** restrict to **standard monthly** SPX expirations. The 1996–2002 SPX sample contained only standard (third-Friday, SOQ-settled) and quarterly SPX expirations. Choosing "maturity closest to 45 days" among modern weekly or daily SPXW expirations would admit instruments absent from the evidence. The restriction reproduces the sample's instrument set. It is not a new rule.

## 3. Canonical facts

| Fact | Unit | Observation | ASA status | Missing |
|---|---|---|---|---|
| spx_value(t) at close | index points | close of the entry and exit days | X01 INDEX quote | UNKNOWN |
| SPX option chain: bid, ask, IV, strike, expiration, root/settlement | — | close of the entry and exit days | OPTION_CHAIN_V1 + X01 | UNKNOWN |
| dividend yield d, risk-free rate r | decimal | entry day | X04 | UNKNOWN (arbitrage-bound filter) |
| trading calendar | — | — | TRADING_CALENDAR_V1 | UNKNOWN |
| SOQ (only if the option expires before the exit day) | index points | expiration morning | X01 | UNKNOWN |

## 4. Derived facts

- DF-FIRST-TRADING-DAY-OF-MONTH
- DF-OPT-DTE-CALENDAR
- DF-OPT-MID
- DF-ZERO-COST-OPTION-RETURN
- DF-CBOE-NAKED-MARGIN (index parameter set α = 0.15, β = 0.10)

## 5. Fact ownership

| Input | Class |
|---|---|
| index close, chain, r, d, calendar, SOQ | CANONICAL_FACT |
| entry date, DTE, mid, return, margin | DERIVED_FACT |
| target maturity 45 days; ATM; IV bounds 1%–100%; minimum tick 0.05 / 0.10 | STRATEGY_PARAMETER |
| G-SCS-* | STRATEGY_GATE |
| strike = argmin |K − S|; expiry = argmin |DTE − 45|; one call and one put at the same K and T | STRUCTURE_SELECTION_RULE |
| monthly roll; exit at the next month's first trading day; $1-premium unit; proceeds at rf | PORTFOLIO_OR_LIFECYCLE_RULE |

## 6. Gates

| Gate | Predicate | PASS | FAIL | UNKNOWN |
|---|---|---|---|---|
| G-SCS-ENTRY-DATE | date(t) = first trading day of month(t) | roll | hold (not an error) | calendar missing |
| G-SCS-EXPIRY-UNIQUE | argmin over standard monthly expirations of \|DTE_cal − 45\| is unique | expiry defined | — | tie → AMBIGUOUS_SELECTION; chain missing |
| G-SCS-STRIKE-UNIQUE | argmin_K \|K − S_close\| over strikes listed with both a call and a put is unique | strike defined | — | tie → AMBIGUOUS_SELECTION |
| G-SCS-QUOTE-FILTERS | both legs satisfy all conditions below | legs admissible | either leg fails → no admissible straddle (see note) | input missing |

G-SCS-QUOTE-FILTERS conditions, per leg:
- bid > 0;
- ask ≥ bid;
- ask − bid ≥ minimum tick ($0.05 if price < $3, else $0.10);
- the arbitrage bound: call ∈ (S·e^{−τd} − K·e^{−τr}, S·e^{−τd}), with the put bound defined analogously (DERIVED by parity; the paper states only the call example);
- 0.01 ≤ IV ≤ 1.00.

Note on G-SCS-QUOTE-FILTERS: the paper uses these as data-cleaning filters. What to trade when the ATM pair fails them is not stated. Verdict: UNKNOWN. No fallback to another strike.

## 7. Verdict truth table

| ENTRY-DATE | EXPIRY-UNIQUE | STRIKE-UNIQUE | QUOTE-FILTERS | Verdict |
|---|---|---|---|---|
| FAIL | * | * | * | NO_ACTION (hold until the exit rule fires) |
| UNKNOWN | * | * | * | UNKNOWN |
| PASS | UNKNOWN | * | * | UNKNOWN |
| PASS | PASS | UNKNOWN | * | UNKNOWN |
| PASS | PASS | PASS | FAIL or UNKNOWN | UNKNOWN |
| PASS | PASS | PASS | PASS | PASS: sell the straddle |

## 8. Score

NONE.

## 9. Direction

| Dimension | Direction |
|---|---|
| delta | approximately neutral at entry; not hedged |
| volatility | negative |
| theta | positive |
| gamma | negative |
| event exposure | none targeted |

## 10. Structure selection (P03, short)

1. T* = argmin_{T ∈ standard monthly SPX expirations} | DTE_cal(T, t) − 45 |
2. K* = argmin_{K listed at T* for both a call and a put} | K − S_close(t) |. "Moneyness closest to ATM" (Table 1: price = f(moneyness, maturity)).
3. Legs: short 1 call(K*, T*) and short 1 put(K*, T*). Unit ratio: "A straddle involves … a call and a put option with the same strike and expiration date".

## 11. DTE

Calendar days from the entry date to the expiration date (DF-OPT-DTE-CALENDAR). The target is 45 ("approximately 45 days").

## 12. Entry timing

At the close of the first trading day of each month ("from closing of the first trading day of each month to the next").

## 13. Lifecycle

- **Exit:** at the close of the first trading day of the next month, "or at the option-expiration day if it comes first". At expiration, the settlement value is "the opening price of the underlying on the expiration day" (SOQ).
- **Roll:** re-establish the position at the same close per §10.
- **Stops and targets:** none (none are sourced).
- **Positions:** one straddle position at a time.

## 14. Sizing

- **Return unit:** "take a long position of $1 and a short position of $1 … presented as a percentage of the $1 notional". The strategy sells straddles with premium value equal to the notional, and the proceeds are invested at the risk-free rate (the zero-cost convention). The contract quantity is N = notional / (C + P) at the entry price.
- **Notional as a share of account capital:** **not sourced for the standalone strategy.** The paper's 7.5%-of-wealth weight is an in-sample certainty-equivalent optimum and is **not** adopted. This is a Founder capital decision (retained), not a research gap.

## 15. Transaction costs

- **gross:** mid to mid.
- **net:** sell at the bid, buy back at the ask. For the N ATM straddle the spread costs about 4.9% per month.
- Commissions: not modelled.

## 16. Capital and margin

- **CBOE initial margin per short option** (index parameters α = 15%, β = 10%): M = max(V + α·S − OTM, V + β·(S for calls, K for puts)). See DF-CBOE-NAKED-MARGIN.
- **Straddle combination:** the paper applies the rule per option. The CBOE rule for a straddle combination is not stated → A15 must represent CBOE straddle margin (an external rule; a DATA or ARCHITECTURE item).
- Margin calls: see §1.
- Maximum loss: unbounded (short call).

## 17. Liquidity

The sourced gates are bid > 0, ask ≥ bid and the minimum tick. A12 is used for diagnostics.

## 18. UNKNOWN / invalid states

| Condition | Outcome |
|---|---|
| calendar, chain, index close missing | UNKNOWN |
| expiry or strike tie | AMBIGUOUS_SELECTION → UNKNOWN |
| ATM pair fails the quote filters | UNKNOWN (no sourced fallback) |
| r or d unavailable | UNKNOWN (arbitrage bound) |
| SOQ unavailable when expiry precedes exit | UNKNOWN settlement |

## 19. Provenance

| Object | Source | Depth | Direct / inferred |
|---|---|---|---|
| data filters | SCS §1 | full text | direct |
| entry/exit schedule, $1 convention, rf reinvestment | SCS §1–§2 | full text | direct |
| near ≈ 45 days, ATM | SCS §2, Table 1 | full text | direct |
| costs | SCS §4.1, Table 10 | full text | direct |
| margin | SCS §4.2, Tables 11–12 | full text | direct |
| put arbitrage bound | parity analogue of the stated call bound | — | DERIVED |
| standard-monthly restriction | sample composition | — | RESEARCH ASSUMPTION RA-SV-01 |

## 20. ASA translation sheet

| Field | Value |
|---|---|
| strategy_id_candidate | `index_short_vol_scs_near_atm_straddle` |
| lane | index short volatility |
| required_market_capabilities | OPTION_CHAIN_V1 (SPX), REAL_TIME_QUOTE_V1 (INDEX via X01), TRADING_CALENDAR_V1 |
| structure_primitive | **P03** (short, unit ratio) |
| missing_reusable_primitives | X01 (HARD), P03 (HARD), X04 (HARD for the arbitrage bound), A15 (CBOE margin incl. straddle rule), A12 (diagnostic) |
| architecture_review_required | none beyond the shared X01/P03/A15 work |

## 21. Manifest readiness

Signal, structure, lifecycle and return unit are sourced. Open items:
- the capital share is a Founder capital decision;
- the straddle margin combination and the rates are data/architecture items;
- RA-SV-01 is an explicit research assumption.

A manifest can be authored without inventing a trading decision.
