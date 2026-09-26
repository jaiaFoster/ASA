# ASA-RSCH-TGSM-001 — Trend-Gated Sector Momentum

## Identity

- **Strategy:** Trend-Gated Sector Momentum (TGSM / production identity S001)
- **Family:** sector rotation / tactical allocation / momentum + trend conditioning
- **Research status:** TRIAGE
- **Created:** 2026-09-25
- **Updated:** 2026-09-25

## Thesis

The strategy combines cross-sectional sector momentum with an absolute/trend gate and a defensive allocation rule. The proposed mechanism is that relative-strength persistence selects stronger sectors while the trend gate reduces exposure when selected sectors lose positive trend.

This is a research characterization, not a claim that the combined strategy is externally validated.

## Existing ASA evidence

ASA already contains unusually rigorous internal research infrastructure for TGSM:

- immutable evidence qualification;
- preregistration before result-bearing output;
- content-addressed experiment/replay identity;
- production S001 interpretation reused by the research seam;
- explicit benchmark, hypothesis, robustness, cost, and walk-forward definitions.

The prior research concluded **DATA_LIMITED**. No result-bearing historical experiment was executed because ASA lacked a qualified corpus simultaneously providing point-in-time sector membership, total-return history, three-month Treasury total return, and authoritative historical trading-session evidence.

Therefore:

- no return, volatility, drawdown, turnover, robustness, or OOS result is established by ASA;
- H1-H5 remain inconclusive;
- current membership was not projected backward;
- adjusted close was not relabeled as total return;
- no proxy defensive asset was substituted.

## External evidence state

External literature has **not yet been synthesized under ROLE-RESEARCH's evidence standard**.

Deep research must separately examine:

1. cross-sectional momentum in equities and sectors;
2. time-series/absolute momentum or moving-average trend filters;
3. sector rotation using relative strength;
4. defensive/cash-or-Treasury substitution;
5. evidence on combining relative momentum with trend gating;
6. post-publication persistence, decay, crowding, transaction costs, and parameter sensitivity.

No qualification status should be assigned until primary papers and meaningful replication/contradictory literature are recovered.

## Specification inherited from ASA

The production/research definition uses sector-level cross-sectional selection and trend-conditioned target allocation. Exact current S001 semantics remain defined by the canonical ASA strategy documents and runtime; this dossier does not supersede them.

Research-relevant required evidence includes:

- authoritative point-in-time eligible sector universe;
- split-and-dividend-adjusted or equivalent total-return history for sectors and benchmark;
- completed-month momentum observations;
- completed-month trend observations;
- canonical defensive total-return evidence;
- authoritative historical session calendar;
- point-in-time information availability.

## Practical evidence still required

External research must establish, where available:

- turnover and rebalance frequency;
- transaction-cost assumptions;
- performance before and after realistic costs;
- drawdowns and crash behavior;
- sensitivity to lookback and trend-window choices;
- concentration and diversification properties;
- regime dependence;
- publication-date persistence;
- whether results reduce to standard momentum/trend factors.

## ASA capability mapping

### Existing

- provider-neutral market-data acquisition;
- immutable/canonical evidence projection;
- deterministic sealed replay;
- completed-month SMA analytics;
- trailing momentum/total-return analytical definitions;
- cross-subject/cohort knowledge;
- S001 interpretation and allocation semantics.

### Missing for historical research reproduction

- authoritative historical point-in-time sector membership;
- qualified long total-return history for sectors/SPY;
- canonical three-month Treasury total-return history;
- qualified historical exceptional-session calendar.

These gaps affect ASA reproduction only and must not reduce or increase the credibility assigned to external research.

## Adversarial questions

Before qualification, explicitly test whether:

- combined TGSM results add value beyond ordinary momentum or trend individually;
- performance is concentrated in a small set of crises;
- Treasury/cash assumptions create hidden return differences;
- sector ETF inception and survivorship choices bias long samples;
- current sector membership is improperly projected backward in published replications;
- results depend strongly on one lookback or rebalance convention;
- turnover and taxes/costs materially reduce reported returns;
- post-publication evidence shows decay.

## Current assessment

- **Strongest supporting evidence:** not yet established under the external-literature standard.
- **Strongest contradictory evidence:** not yet established.
- **Unresolved:** external evidence base for the exact combined strategy.
- **Qualification:** not qualified; TRIAGE.
- **Reason:** substantial ASA internal work exists, but external primary/replication evidence has not yet been synthesized.

## Provenance

See `research/sources/ASA-PRIOR-TGSM-001.yaml`.
