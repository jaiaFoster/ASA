# ASA-RSCH-FAM-COVERED-CALL-001 — Covered Call / Buy-Write

## Identity

- **Research ID:** ASA-RSCH-FAM-COVERED-CALL-001
- **Strategy:** Covered Call / Buy-Write
- **Family:** FAM-VRP-COVERED-CALL (E1 insurance selling); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** TRIAGE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 6.

## Thesis

### Concise description

Hold the underlying and systematically sell a near-dated (typically one-month ATM or OTM) call, rolled on a calendar schedule.

### Proposed economic or behavioral mechanism

Collects the equity risk premium plus the short-volatility premium; also embeds an uncompensated equity-reversal exposure (ISRAELOV-NIELSEN-2015-FAJ). Shorter-dated calls strengthen the volatility-spread effect relative to the equity-premium drag (FIGELMAN-2008).

## Evidence

Sample, universe and method context: S&P 500 BXM 1988-2001 (Whaley) and ~15 years to mid-2000s (Hill et al.); Russell 2000 (Kapadia-Szado). Single-stock evidence not recorded.

### Original research

- **WHALEY-2002** — BXM 1988-2001 earned almost as much as the S&P 500 with substantially lower risk.

### Supporting research

- **HILL-ET-AL-2006** — BXM outperformed on average over 15+ years with lower SD; volatility-adjusted strike variants better (in-sample).
- **FIGELMAN-2008** — Decomposition: IV-RV spread positive, equity-premium effect negative; short-dated better.
- **ISRAELOV-NIELSEN-2014** — Realized profile not much below equity with much lower volatility.

### Independent replications

- **KAPADIA-SZADO-2007** — Russell 2000 buy-write: one-month version outperforms risk-adjusted, robust to non-normal measures.

### Failed replications

- **KAPADIA-SZADO-2007** — Two-month-call version: consistent advantage disappears; written calls on average end ITM; writing at bid increases losses.

### Contradictory research

- **ISRAELOV-NIELSEN-2015-FAJ** — Most return is equity beta; ~25% of risk is an uncompensated reversal exposure; short-vol component is only ~10% of risk.

### Post-publication evidence

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Reported empirical results

| Field | Value |
|---|---|
| Reported return metrics | REPORTED qualitatively: near-equity returns with lower volatility (WHALEY-2002, HILL-ET-AL-2006). Point values not recovered at abstract depth (UNKNOWN). |
| Reported risk metrics | REPORTED: lower SD than index; negative skew INFERENCE. |
| Drawdown / tail | Full equity downside less premium (INFERENCE from structure). |
| Opportunity frequency | Calendar monthly. |
| Regime dependence | INFERENCE: underperforms in strong rallies (capped upside) and crashes (full downside). |
| Persistence | UNKNOWN post-2006 in recorded sources. |
| Transaction-cost sensitivity | REPORTED: writing at bid increases losses (KAPADIA-SZADO-2007). |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | Calendar roll; no signal. |
| DTE / expiration | ~1 month (maturity sensitivity REPORTED: 2-month weaker). |
| Strike / delta | ATM (BXM); OTM variants (e.g. BXY, 30-delta BXMD) named in Cboe family but not evaluated here. |
| Liquidity requirements | Index or liquid single names. |
| Exit rules | Hold to expiration. |
| Roll rules | Monthly. |
| Sizing assumptions | 1 call per 100 units of underlying. |
| Exclusions | None documented. |
| Unresolved rule gaps | Strike rule for OTM variants, cost model, and single-stock evidence UNKNOWN. |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Underlying loss less premium. |
| Liquidity risk | Low for indexes/ETFs. |
| Assignment / exercise risk | American calls: early assignment around ex-dividend (INFERENCE). |
| Gap risk | High (long underlying). |
| Volatility-regime risk | Medium. |
| Model dependency | Low. |
| Crowding / decay evidence | UNKNOWN. |
| Known failure modes | Sharp rallies (capped) and crashes (uncapped downside). |

## Adversarial review

| Question | Answer |
|---|---|
| Independently replicated? | Yes on Russell 2000 (one-month). |
| Failed replications? | Two-month variant fails (KAPADIA-SZADO-2007). |
| Later research reduces claim? | Yes: most return is equity beta (ISRAELOV-NIELSEN-2015-FAJ). |
| Persisted? | UNKNOWN in recorded sources. |
| Data mining? | Low for base rule; variants in-sample. |
| Concentrated period? | UNKNOWN. |
| Parameter-dependent? | Yes: maturity. |
| Costs? | Bid-side writing hurts. |
| Execution realistic? | Mostly. |
| Another factor? | Equity beta + short vol + reversal. |
| Look-ahead? | No. |
| Failure regime? | Strong rallies, crashes. |
| Crowding? | UNKNOWN. |
| Omission risk? | Omitting the attribution result overstates 'alpha'. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Underlying price, option chain. |
| Required analytics | None required for base; volatility-adjusted strikes for variants. |
| Required history | Historical option prices for replication (A08). |
| Required event data | Dividend/ex-dividend dates relevant to early exercise (INFERENCE). |
| Structural primitives (RES-001B §3) | P09. |
| Apparent existing ASA capabilities | Quote, chain, delta selection; `OptionStructureType.COVERED_CALL` vocabulary. |
| Apparent missing ASA capabilities | Stock+option overlay runtime structure (P09); holding-of-underlying representation UNKNOWN; historical option panel. |
| Execution complexity | Low. |

## Assessment

### Strongest supporting evidence

Benchmark evidence across two indexes (WHALEY-2002, KAPADIA-SZADO-2007).

### Strongest contradictory evidence

Return mostly equity beta with an uncompensated reversal component (ISRAELOV-NIELSEN-2015-FAJ).

### Unresolved questions

- Post-2006 index performance
- Single-stock and ETF evidence
- OTM-strike variants

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

TRIAGE

### Qualification basis

TRIAGE: repeated peer-reviewed/benchmark evidence, one independent index replication, but attribution evidence reframes the 'outperformance'. Not qualified.

## Research history

- 2026-09-26: record created as TRIAGE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/WHALEY-2002.yaml`
- `research/sources/HILL-ET-AL-2006.yaml`
- `research/sources/FIGELMAN-2008.yaml`
- `research/sources/ISRAELOV-NIELSEN-2014.yaml`
- `research/sources/KAPADIA-SZADO-2007.yaml`
- `research/sources/ISRAELOV-NIELSEN-2015-FAJ.yaml`
