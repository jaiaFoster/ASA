# Lane 6 — Cross-sectional option returns: candidate survey and qualification

**Result:** **0 of 2** primaries reached READY status. Two primaries are specified at DEEP_RESEARCH_REQUIRED, and one alternate is INSUFFICIENT_EVIDENCE.

## Candidates

| Candidate | Source | Role | State |
|---|---|---|---|
| [Zhan et al. −Ln(PRICE) delta-neutral call writing](strategy-specifications/ASA-QS-XR-01-ZHAN-NEG-LNPRICE-DN-CALL.md) | ZHAN-ET-AL-2022 (accepted manuscript, full text) | PRIMARY | DEEP_RESEARCH_REQUIRED |
| [Heston et al. straddle momentum](strategy-specifications/ASA-QS-XR-02-HESTON-STRADDLE-MOMENTUM.md) | HESTON-ET-AL-2023 (working-paper full text) | PRIMARY | DEEP_RESEARCH_REQUIRED |
| [Cao-Han IVOL delta-hedged calls](strategy-specifications/ASA-QS-XR-A1-CAOHAN-IVOL-DH-CALL.md) | CAO-HAN-2013 (full text) | ALTERNATE | INSUFFICIENT_EVIDENCE |

**Surveyed, not specified:**

| Source | Reason |
|---|---|
| Zhan et al., the other nine characteristics (CFV, CH, DISP, ISSUE_1Y, ISSUE_5Y, PM, PROFIT, TEF, ZS) | Each needs Compustat or I/B/E/S inputs that ASA does not hold as canonical facts. Net spreads at 100% quoted spread (Table 6): DISP 0.40 (t 2.94); CFV 0.29; ISSUE_5Y 0.33; –PROFIT 0.38; –ZS 0.45. CH, ISSUE_1Y, TEF and –PM are not significant at 100%. |
| Heston et al. option reversal and composite | Same paper, Table 13. At quoted cost, zero exercise costs, low-cost decile: reversal (Panel A) 0.0199 (t 1.64); composite (Panel C) 0.0198 (t 1.47). The composite is source-tested, so the no-composite rule would allow it, but it inherits every unresolved rule of the momentum specification plus a z-score combination. Neither is specified separately. |
| GOYAL-SARETTO-2009 | Full text not obtained. |

## Lane-specific mathematics

| Requirement | Zhan (XR-01) | Heston (XR-02) |
|---|---|---|
| Characteristic | x = −ln(P) at formation month end | MOM = mean of straddle returns, lags 2–12 (all 11 required) |
| Universe | common stock, P ≥ $5, optionable, filters | common equity, monthly expirations, filters |
| Option return | DF-DN-CALL-WRITE-RETURN (eq. 1), unrebalanced one-month hedge | DF-STRADDLE-RETURN with zero-delta weights, held to expiry |
| Lookback | none (point-in-time price) | 12 months of option history (A08) |
| Rank / breakpoints | deciles; breakpoint and tie conventions UNKNOWN | quintiles (deciles in the cost-optimized variant); conventions UNKNOWN |
| Long/short | write decile 10 (lowest price), buy decile 1 | long top quintile, short bottom |
| Weighting | Stock-VW (headline); EW and Option-VW gross only | equal weight |
| Rebalance | monthly, at month end | monthly, on expiration day |
| Delta hedging | static Black-Scholes delta at formation | none beyond the zero-delta weights at formation |
| Costs | 25–100% of quoted spread; actual OPRA effective spread; CBOE margin | 20.3/51.6/75.8/100% of the half-spread; exercise cost; SPAN margin |
| Factor neutralization | the alpha is explained by two option factors (IVOL, illiquidity); equity factors do not explain it | not evaluated in this sprint |

## Why fewer than two ready

**Zhan.** The net evidence is the strongest in the sprint: 1.01%/month (t 5.48) at the full quoted spread. But:
- the dividend-during-life exclusion is ex post;
- value weights need market capitalization, which is not canonical in ASA;
- the capital convention and borrow cost of the long delta-hedged leg (short stock) are unstated;
- the moneyness ratio definition is unstated.

**Heston.** The replacement rule for straddles that fail the spread cut has no stated ordering. Net returns at conventional effective costs are not significant (t 1.75). The signal needs a 12-month option panel.

## Evidence uncertainties

- **Persistence.** Both samples end in 2016 (Zhan) or 2019 (Heston). No post-publication replication was recovered.
- **Spanning.** Zhan's profits are spanned by option factors.
- **Execution.** Heston's profitability depends on algorithmic-trader execution quality, taken from the Muravyev-Pearson 2020 ratios.
