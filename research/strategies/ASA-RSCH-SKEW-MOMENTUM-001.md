# ASA-RSCH-SKEW-MOMENTUM-001 — Skew Momentum

## Identity

- **Strategy:** Skew Momentum
- **Family:** options relative value / directional vertical
- **Research status:** TRIAGE
- **Created:** 2026-09-25
- **Updated:** 2026-09-25

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
- **Strongest contradiction:** not yet established.
- **Evidence limitation:** no research-grade external synthesis for the combined strategy.
- **Qualification:** not qualified; TRIAGE.

## Provenance

See `research/sources/ASA-PRIOR-SKEW-MOMENTUM-001.yaml`.
