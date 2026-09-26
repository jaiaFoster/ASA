# ASA-RSCH-SPY-PCS-001 — SPY 30-DTE Put Credit Spread

## Identity

- **Strategy:** SPY 30-DTE Put Credit Spread
- **Family:** systematic option premium / defined-risk short volatility
- **Research status:** TRIAGE
- **Created:** 2026-09-25
- **Updated:** 2026-09-25

## Thesis

A practitioner-documented rule set sequentially sells defined-risk SPY put credit spreads near 30 calendar DTE, using approximately -0.30 delta for the short put and -0.10 delta for the long put, with one position active and the analyzed base variant held to expiration.

The hypothesized return source is the equity/index option volatility risk premium, expressed through a bounded-loss vertical rather than naked short-option exposure.

## Prior ASA research

STRATEGY-LIBRARY-001 recovered a public Option Alpha article sufficiently explicit to implement a faithful bounded strategy:

- SPY only;
- approximately 30 DTE;
- short put around -0.30 delta;
- long put around -0.10 delta;
- no entry filter for the selected base variant;
- one active position at a time;
- hold to expiration.

That work established **implementation explicitness**, not external empirical qualification.

The implementation subsequently traversed ASA's production trade-card path successfully. Production operability is not evidence that the strategy has favorable expected returns.

## External evidence state

The original practitioner source must be independently re-verified and its empirical claims extracted under research provenance rules.

Deep research must determine:

- exact sample period and number of trades;
- exact entry timing/frequency;
- treatment of overlapping opportunities and one-position constraint;
- pricing convention and slippage;
- commissions/fees;
- assignment/exercise assumptions;
- reported return, drawdown, win rate, expectancy, and risk-adjusted metrics;
- comparison among hold-to-expiration and managed variants;
- whether results are robust across volatility regimes;
- whether independent studies of comparable delta-targeted SPY put spreads support or contradict the reported effect.

## Specification

Current inherited rule description:

- **Underlying:** SPY.
- **Entry:** systematic/no signal filter in the base variant.
- **Expiration:** nearest approximately 30 calendar DTE.
- **Short strike:** put with absolute delta near 0.30.
- **Long strike:** put with absolute delta near 0.10.
- **Exit:** hold to expiration for the selected base variant.
- **Portfolio constraint:** one active position at a time.

Exact research specification remains provisional until the source is re-verified.

## Practical evidence required

Particular attention is required for:

- left-tail losses and gap risk;
- volatility clustering;
- credit received relative to width;
- transaction costs and bid/ask spread;
- early assignment and ex-dividend effects;
- capital definition and return denominator;
- overlapping-position suppression;
- capacity in SPY versus execution at quoted mid;
- survivorship/data-quality issues in historical option chains.

## ASA capability mapping

ASA currently possesses the basic data and structure support needed to represent this rule set:

- SPY real-time quote;
- option expirations and chains;
- bid/ask and delta where available;
- vertical structure resolution;
- modeled credit, bounded payoff, breakeven, and max loss/profit;
- deterministic proposal identity and forward modeled outcomes.

This implementation convenience does not affect the evidence rating.

## Adversarial questions

Before qualification, determine whether:

- the article's results depend materially on midpoint fills;
- a small number of crash losses dominates long-run expectancy;
- the tested period is unusually favorable to short volatility;
- unmanaged expiration exposure differs materially from more commonly cited managed-credit-spread results;
- the one-position constraint introduces path dependence;
- the strategy is simply another expression of known short-volatility beta;
- post-publication/live evidence shows degradation.

## Current assessment

- **Strongest support:** public practitioner methodology was explicit enough for faithful implementation.
- **Strongest contradiction:** not yet researched.
- **Evidence limitation:** no independent replication has yet been established in this library.
- **Qualification:** not qualified; TRIAGE.
- **Reason:** promising research target with a recoverable original source, but the empirical evidence has not yet undergone adversarial review.

## Provenance

See `research/sources/OA-SPY-PCS-2021.yaml`.
