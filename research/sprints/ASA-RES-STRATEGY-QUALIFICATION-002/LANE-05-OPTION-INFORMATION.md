# Lane 5 — Option-implied information: candidate survey and qualification

**Result:** **0 primaries.** One alternate is RESEARCH_REJECT.

## Candidates

| Candidate | Source | Role | State |
|---|---|---|---|
| [MPP smirk decile (stock expression)](strategy-specifications/ASA-QS-OS-A1-MPP-SMIRK-DECILE.md) | MURAVYEV-PEARSON-POLLET-2022-WP (full text); MURAVYEV-PEARSON-POLLET-2025 (abstract) | ALTERNATE | RESEARCH_REJECT |

**Surveyed within the same full text** (the same verdict applies):

| Signal | Definition | Gross | Net of borrow |
|---|---|---|---|
| IV spread (Cremers-Weinbaum; put − call, OI-weighted pairs; DF-CW-IV-SPREAD-OI-WEIGHTED) | as defined | decile 10 −0.67%/month (t −5.5) | −0.19% (t −1.6) |
| O/S volume ratio (DF-OS-VOLUME-RATIO) | as defined | — | decile 10 −6 bp per month |

**Surveyed, not recovered in full text:**

| Source | Status |
|---|---|
| XING-ZHANG-ZHAO-2010 (the smirk's origin; Cambridge) | bibliographic only |
| Bakshi-Kapadia-Madan (2003) risk-neutral moments (the A07 formula source) | not recovered in full text in this sprint; no return-seeking specification based on it was evaluated |

## Lane-specific mathematics

| Requirement | Source definition |
|---|---|
| Signal formula | DF-XZZ-SMIRK-MPP, DF-CW-IV-SPREAD-OI-WEIGHTED, DF-OS-VOLUME-RATIO |
| Normalization | none; raw cross-sectional decile sort |
| Direction | high smirk, high put-minus-call spread and high O/S predict **lower** stock returns |
| Lag | sort at close t; hold from close t+1 (a one-day skip to avoid the stale-quote effect) |
| Portfolio | deciles, equal weight, daily overlapping; D1 − D10 long-short |
| Horizon | 21 trading days |
| Universe | CRSP common stocks with valid options and a Markit fee |
| Borrow treatment | Markit IndicativeFee. Shorts pay the fee. Long lending income = fee × utilization × 0.7. |
| Final expression | **stock** |

## Why zero

The lane asks for "two differentiated signal families with credible return-direction evidence".

The strongest recovered full-text evidence shows that all three mainstream option-implied stock signals lose significance once short sellers pay the borrow fee:
- smirk: −0.59% → −0.21%, t −1.6;
- IV spread: −0.67% → −0.19%, t −1.6;
- O/S: about −6 bp.

The predictability is concentrated in high-fee stocks. The final JFE abstract states that predictability "decreases by about two-thirds".

**Option expression.** Re-expressing the signal as an option trade (for example buying puts) does not escape the fee. Option prices embed the lending fee through put-call parity. That parity mechanism is the paper's explanation of *why* the signals predict (INFERENCE from the paper's thesis; not separately tested as a trading strategy here).

No second signal family (such as model-free risk-neutral moments via A07) with net-positive return evidence was recovered in full text.

## Evidence uncertainties

- The final JFE version was not accessed.
- In the conference text, the skew definition is internally inconsistent: §4.2 says "OTM call", while the data section says "OTM put".
