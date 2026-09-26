# ASA-RSCH-FAM-DEFINED-RISK-001 — Defined-Risk Premium Structures (credit spreads, iron condor, iron butterfly)

## Identity

- **Research ID:** ASA-RSCH-FAM-DEFINED-RISK-001
- **Strategy:** Defined-Risk Premium Structures (credit spreads, iron condor, iron butterfly)
- **Family:** FAM-VRP-DEFINED-RISK (E1 insurance selling); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** TRIAGE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 2, bibliographic_and_search_engine_summary: 1, primary_page_reviewed: 1, primary_repository_readme_reviewed: 1.

## Thesis

### Concise description

Sell short-dated option premium through structures with long protective wings: put or call credit spreads, iron condors (CNDR-style), iron butterflies (BFLY-style).

### Proposed economic or behavioral mechanism

INFERENCE: same volatility risk premium as FAM-VRP-INDEX-SHORT-VOL with the far tail purchased back. Whether the premium survives paying for the wings is an open empirical question; expected put returns increase with strike, so the lowest-strike (wing) puts carry the most negative expected returns (COVAL-SHUMWAY-2001), suggesting wings may give back a disproportionate share of the premium (INFERENCE). Counter-evidence: delta-hedged underperformance is smaller for options away from the money (BAKSHI-KAPADIA-2003), so the net effect on a truncated structure is UNKNOWN.

## Evidence

Sample, universe and method context: Only sponsor-commissioned index studies (SPX) and a practitioner five-year SPY backtest were found. **No independent peer-reviewed return evidence for monthly defined-risk premium structures was found.**

### Original research

- **CBOE-CNDR-BFLY-METHODOLOGY** — Explicit benchmark rules (CNDR ~0.20Δ short / ~0.05Δ long; BFLY ATM short / 5% OTM long); 2016 Cboe-commissioned study reports S&P-like returns with lower volatility and drawdown.
- **OA-SPY-PCS-2021** — Practitioner SPY 30-DTE 0.30Δ/0.10Δ put spread backtests (re-verified 2026-09-26; see that source).

### Supporting research

- **CHAPUT-EDERINGTON-2003** — Usage evidence: spreads common; condors/iron flies 'mostly colorful names' in large Eurodollar option trades; combinations may reduce effective spreads.

### Independent replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Failed replications

- **VILKOV-0DTE** — 0DTE iron condors/butterflies included; after the Aug-2026 erratum no strategy or basket has positive net Sharpe (0DTE horizon only).

### Contradictory research

- **BAKSHI-KAPADIA-2003** — Delta-hedged underperformance is smaller away from the money: a nuance against assuming wings are disproportionately expensive (index-level, delta-hedged; indirect).

### Post-publication evidence

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Reported empirical results

| Field | Value |
|---|---|
| Reported return metrics | UNKNOWN (independent). Sponsor study: returns similar to S&P 500 (REPORTED, secondary). Practitioner: see OA-SPY-PCS-2021. |
| Reported risk metrics | UNKNOWN (independent). |
| Drawdown / tail | Defined per position by wing width (structural, DERIVED). |
| Opportunity frequency | Calendar monthly (CNDR/BFLY); sequential 30-DTE (OA). |
| Regime dependence | UNKNOWN. |
| Persistence | UNKNOWN. |
| Transaction-cost sensitivity | UNKNOWN; four-leg structures pay more spread (INFERENCE); CHAPUT-EDERINGTON-2003 suggests combination orders may reduce effective spreads. |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | Calendar (CNDR/BFLY); sequential (OA SPY PCS). |
| DTE / expiration | ~1 month. |
| Strike / delta | Delta targets (CNDR 0.20/0.05; OA 0.30/0.10) or ATM/5% OTM (BFLY). |
| Liquidity requirements | SPX (indices) or SPY (practitioner). |
| Exit rules | Hold to expiry (base); OA variants with profit targets/stops. |
| Roll rules | Monthly. |
| Sizing assumptions | T-bill collateral (indices); % allocation (OA). |
| Exclusions | None documented. |
| Unresolved rule gaps | CNDR delta computation inputs (per ASA Architect decision) and cost treatment UNKNOWN. |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Defined: wing width minus credit. |
| Liquidity risk | Low for SPX/SPY; leg count raises cost. |
| Assignment / exercise risk | American ETF legs: early assignment on short ITM legs (INFERENCE). |
| Gap risk | Bounded by wings. |
| Volatility-regime risk | High: max loss realized in volatility expansions (INFERENCE). |
| Model dependency | Low. |
| Crowding / decay evidence | UNKNOWN. |
| Known failure modes | Trending or gapping markets through short strikes; pin risk at expiration (INFERENCE). |

## Adversarial review

| Question | Answer |
|---|---|
| Independently replicated? | No independent evidence found. |
| Failed? | 0DTE variant negative after erratum (horizon differs). |
| Later research? | None found. |
| Persisted? | UNKNOWN. |
| Data mining? | Practitioner variants chosen ex post (OA variants). |
| Concentrated? | UNKNOWN. |
| Parameter-dependent? | Likely (INFERENCE); OA variants differ materially. |
| Costs? | UNKNOWN; leg count increases exposure. |
| Execution? | Mid-fill assumptions UNKNOWN. |
| Another factor? | Short VRP with truncated tail. |
| Look-ahead? | No. |
| Failure regime? | Trend/gap regimes. |
| Crowding? | UNKNOWN. |
| Omission risk? | Presenting sponsor studies without noting sponsorship. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Chain with greeks. |
| Required analytics | A02 delta selection. |
| Required history | Historical chains for replication. |
| Required event data | None. |
| Structural primitives (RES-001B §3) | P02, P05. |
| Apparent existing ASA capabilities | Vertical structure (P02), delta-nearest selection, modeled credit/max loss; SPY PCS implemented (production operability is not evidence). |
| Apparent missing ASA capabilities | Four-leg structure (P05); SPX identity and settlement root for CNDR/BFLY fidelity; Cboe-faithful Black delta (per Architect decision). |
| Execution complexity | Low-medium. |

## Assessment

### Strongest supporting evidence

Explicit benchmark rules and sponsor study (CBOE-CNDR-BFLY-METHODOLOGY).

### Strongest contradictory evidence

No direct contradiction of the rule set found; the absence of independent evidence is itself the finding. Wing-cost direction is contested (COVAL-SHUMWAY-2001 vs BAKSHI-KAPADIA-2003).

### Unresolved questions

- Does wing purchase preserve VRP per unit risk?
- Net-of-cost performance
- Independent evaluation of CNDR/BFLY history

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

TRIAGE

### Qualification basis

TRIAGE (not DISCOVERED): rules are explicit and the parent premium is well documented, which justifies deep research; but direct evidence is sponsor-commissioned or practitioner only, so this family has the weakest evidence-to-attention ratio in the landscape. Not qualified.

## Research history

- 2026-09-26: record created as TRIAGE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/CBOE-CNDR-BFLY-METHODOLOGY.yaml`
- `research/sources/OA-SPY-PCS-2021.yaml`
- `research/sources/CHAPUT-EDERINGTON-2003.yaml`
- `research/sources/VILKOV-0DTE.yaml`
- `research/sources/BAKSHI-KAPADIA-2003.yaml`
