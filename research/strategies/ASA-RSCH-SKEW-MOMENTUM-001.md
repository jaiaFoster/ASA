# ASA-RSCH-SKEW-MOMENTUM-001 — Skew Momentum

## Identity

- **Strategy:** Skew Momentum
- **Family:** options relative value / directional vertical
- **Research status:** TRIAGE
- **Created:** 2026-09-25
- **Updated:** 2026-09-26

## Thesis

ASA's current research policy combines unusually stretched option skew, implied-versus-realized volatility value relationships, and multi-dimensional equity momentum alignment to choose a directional defined-risk vertical.

The current policy is an ASA strategy specification. This dossier does **not** assume the combined rule has been externally validated.

## Prior ASA research/specification

The current internal evidence contract specifies, among other things:

- historical call/put skew z-score evaluation;
- a 60-observation window with at least 40 valid observations;
- a skew threshold of z <= -2.0 for the relevant branch;
- ATM IV versus realized-volatility value conditions;
- wing IV richness conditions;
- 20-session directional return;
- cross-sectional return percentile;
- sector-relative return;
- two-of-three momentum alignment;
- typed UNKNOWN behavior when required evidence is absent.

Deterministic fixture vectors validate calculation direction and reproducibility only. They do not establish profitable thresholds.

## External evidence state

No external evidence synthesis currently establishes the combined Skew Momentum strategy.

Research should decompose the hypothesis into literature-supported components:

1. option skew as a predictor or relative-value signal;
2. implied-versus-realized volatility spreads;
3. cross-sectional or sector-relative equity momentum;
4. directional information embedded in option-implied distributions;
5. evidence, if any, for combining skew/volatility value with momentum;
6. defined-risk vertical implementation versus delta-hedged or underlying implementations.

Any evidence for individual components must not be silently treated as evidence for the combined strategy.

## Practical evidence required

Deep research should extract:

- signal construction and lookback choices used in published work;
- whether skew is measured by delta points, risk reversals, slope, or another definition;
- realized-volatility estimator;
- holding period;
- transaction costs and option liquidity;
- tail-event behavior;
- regime dependence;
- cross-sectional universe construction;
- whether findings survive after controlling for equity momentum, value, volatility, and liquidity factors;
- post-publication persistence.

## ASA capability mapping

Existing ASA support includes:

- option-chain evidence;
- IV/Greeks where supplied;
- realized-volatility analytics;
- historical return inputs;
- skew-history contracts;
- cross-sectional and sector-relative analytical vocabulary;
- vertical structure resolution;
- deterministic missing-evidence handling.

Some current live inputs remain unavailable or incomplete, including canonical long skew history, configured-universe peer percentiles, and sector-relative evidence for all subjects.

## Adversarial questions

Before qualification:

- does the skew effect survive realistic option transaction costs;
- is extreme skew compensation for crash/tail risk rather than mispricing;
- does the momentum filter add independent information;
- are threshold choices data-mined;
- does the effect disappear outside a narrow sample;
- does provider-specific IV/Greek methodology materially affect signal classification;
- is the combined strategy supported by evidence or merely assembled from individually plausible components.

## Current assessment

- **Strongest support:** deterministic ASA specification and known researchable component hypotheses.
- **Strongest contradiction:** not yet established. *(Superseded 2026-09-26: see the component evidence map below.)*
- **Evidence limitation:** no research-grade external synthesis for the combined strategy.
- **Qualification:** not qualified; TRIAGE.

## ASA-RES-SPRINT-001 extension (2026-09-26): component evidence map

Per RES-001B, this is a **hybrid**. It combines an E5 option-implied signal, E3 volatility-value conditions, an equity momentum filter, and an E6 directional vertical expression. Each component is mapped to external evidence separately. **Evidence for a component is not evidence for the combination.** No external source testing the combination was found.

| Component | Nearest external evidence | Direction | Family record |
|---|---|---|---|
| Stretched skew as a directional signal | XING-ZHANG-ZHAO-2010 (steep smirk: underperformance 10.9%/yr); CREMERS-WEINBAUM-2010 (IV spread, decaying); STILGER-KOSTAKIS-POON-2017 vs CONRAD-DITTMAR-GHYSELS-2013 (**opposite signs** for risk-neutral skewness) | contradictory on sign; decaying | ASA-RSCH-FAM-OPTION-SIGNAL-001 |
| Implementability of option-implied equity signals | MURAVYEV-PEARSON-POLLET-2025: about two-thirds of predictability removed after borrow-fee adjustment | **negative** | ASA-RSCH-FAM-OPTION-SIGNAL-001 |
| Skew as a separately compensated premium | KOZHAN-NEUBERGER-SCHNEIDER-2013: variance-hedged skew strategies earn an insignificant premium (index level) | **negative** | ASA-RSCH-FAM-SKEW-PREMIUM-001 |
| ATM IV vs realized volatility value | GOYAL-SARETTO-2009 and follow-ups (cross-sectional delta-hedged option returns); partly spanned by factors (GOYAL-SARETTO-2022-IPCA, HORENSTEIN-VASQUEZ-XIAO-2026) | supportive for *option returns*, not for stock direction | ASA-RSCH-FAM-XS-OPTION-RETURNS-001 |
| Realized-implied spread as a stock predictor | BALI-HOVAKIMIAN-2009 (negative relation with stock returns) | supportive (single study) | ASA-RSCH-FAM-OPTION-SIGNAL-001 |
| Cross-sectional / sector momentum | Not researched in this sprint (equity-momentum literature; see ASA-RSCH-TGSM-001's pending need) | UNKNOWN | — |
| Expression via a long-premium directional vertical | Option buyers pay the embedded-leverage/VRP premium (FRAZZINI-PEDERSEN-2022, COVAL-SHUMWAY-2001); no study compares option vs stock expression of the same signal | negative/absent | ASA-RSCH-FAM-DIRECTIONAL-001 |

**Specific adversarial findings (INFERENCE):**

1. The skew-stretch threshold (z <= -2.0) and the 60/40 observation window are ASA policy parameters. No external source recovered here supports those values.
2. Published smirk and skewness effects are mostly *long-short* and concentrated in hard-to-borrow stocks. A single-name, long-biased vertical captures the part that MURAVYEV-PEARSON-POLLET-2025 finds largely disappears.
3. The sign conflict in the risk-neutral skewness literature means the direction implied by "stretched skew" is itself evidence-contested.

**Status unchanged: TRIAGE.** Component research has begun. Two components carry negative evidence, and the combination remains unsupported externally. A status change would need DEEP_RESEARCH on full texts (in particular MURAVYEV-PEARSON-POLLET-2025 residual predictability for low-fee stocks).

## Research history

- 2026-09-25: created as TRIAGE from ASA internal specification; no external synthesis.
- 2026-09-26 (ASA-RES-SPRINT-001): component-level external evidence mapped; negative and contradictory component evidence recorded; status unchanged (TRIAGE).

## Provenance

See `research/sources/ASA-PRIOR-SKEW-MOMENTUM-001.yaml` (internal specification). External component sources: `XING-ZHANG-ZHAO-2010`, `CREMERS-WEINBAUM-2010`, `STILGER-KOSTAKIS-POON-2017`, `CONRAD-DITTMAR-GHYSELS-2013`, `MURAVYEV-PEARSON-POLLET-2025`, `KOZHAN-NEUBERGER-SCHNEIDER-2013`, `GOYAL-SARETTO-2009`, `GOYAL-SARETTO-2022-IPCA`, `HORENSTEIN-VASQUEZ-XIAO-2026`, `BALI-HOVAKIMIAN-2009`, `FRAZZINI-PEDERSEN-2022`, `COVAL-SHUMWAY-2001`.
