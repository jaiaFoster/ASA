# ASA-QS-XR-A1-CAOHAN-IVOL-DH-CALL — delta-hedged call spread sorted on idiosyncratic volatility

- **Lane:** 6, cross-sectional option returns
- **Role:** ALTERNATE
- **Qualification state:** **INSUFFICIENT_EVIDENCE**
  - The quintile headline is defeated net of costs.
  - The decile variant is marginal (see below).
- **Source:** Cao and Han, "Cross section of option returns and idiosyncratic stock volatility", *Journal of Financial Economics* 108(1), 2013. Full text reviewed ([`CAO-HAN-2013`](../../../sources/CAO-HAN-2013.yaml)).

## Specification (recorded)

| Element | Rule |
|---|---|
| Sample | OptionMetrics, January 1996 – October 2009; about 1,514 stocks per month |
| Option | per stock, the call "closest to being at-the-money" with "a time-to-maturity of about 50 days" (common maturity, about 1.5 months), standard filters (shared with Zhan et al. footnote 10) |
| Signal | IVOL: the standard deviation of residuals from daily Fama-French 3-factor regressions over the previous month (DF-IVOL-FF3-DAILY-1M) |
| Sort | quintiles at month end (DF-XS-QUANTILE-ASSIGNMENT) |
| Position | buy delta-hedged calls in the bottom IVOL quintile; sell delta-hedged calls in the top quintile |
| Hedge | Black-Scholes delta, **rebalanced daily**; one option contract held to the end of the next month (DF-DH-CALL-DAILY-REBAL-RETURN) |
| Weights | EW, stock-VW and option-OI-VW, "consistent across weighting schemes" |
| Score | NONE |
| Sizing | UNKNOWN beyond return weights |

## Net-of-cost evidence

Cao-Han Table 10, equal-weighted, quintile 5 − 1:

| Effective / quoted spread | Mean monthly return |
|---|---|
| 0% (mid) | 1.40% |
| 10% | 1.16% (significant) |
| 25% | 0.79% (significant) |
| 50% | 0.17%, "no longer significant statistically or economically" |

The decile ("10 minus 1") variant, per footnote 18, "is still significantly positive when the effective spread is 50% of the quoted spread. But it becomes insignificant when the effective spread is 75%". Its level is not tabulated in the text reviewed.

The authors conclude that "only market participants who face relatively low transaction costs can take advantage of our option strategy profitably".

For context, Zhan et al. (same author group) measure actual OPRA effective spreads at about 55% of quoted for similar options. That puts the decile variant at the edge of significance (INFERENCE).

The signal also needs external daily factor data (Fama-French), which is not an ASA market capability.

**Status reason:** the headline rule is defeated at a 50% effective spread. The decile variant survives only at or below about a 50% effective spread and has no tabulated level. The evidence does not support advancement for return-seeking use.

## Closeout disposition (2026-09-27)

NOT SELECTED. Evidence is marginal net of costs, and the live rule would consume Fama-French factors (an external-data requirement the Architect advises against creating for this purpose). State unchanged: INSUFFICIENT_EVIDENCE.
