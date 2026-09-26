# RES-001D — Downstream Filtering Method Research

- **Sprint / ticket:** ASA-RES-SPRINT-001 / RES-001D (depends on RES-001A, B, C)
- **Date:** 2026-09-26
- **Companion:** [`RES-001D-dimension-dictionary.yaml`](RES-001D-dimension-dictionary.yaml)

This document builds the **measuring instrument, not the ranking**. It defines candidate dimensions, maps them to measured fields, and sets out the options (with their trade-offs) for missing data, normalization, aggregation, weighting, and sensitivity analysis. It chooses **no** weights, computes **no** scores, and declares **no** winners or finalists. It makes **no** implementation recommendation. Where it describes an option as "defensible", that is a methodological characterization, not a choice.

## 1. Measured facts vs decision variables

| Kind | Owner | Examples | Where |
|---|---|---|---|
| **Measured fact**: a coded, traceable statement about external evidence or structure | ROLE-RESEARCH | peer-reviewed source count, contradiction present, net-of-cost direction, rule precision, primitives required | `RES-001C-evidence-dataset.yaml` |
| **Proposed decision variable**: a construct built from facts whose direction, weight and use depend on an objective | downstream selection authority | evidence grade (D01), structural novelty (D12), reusable capability expansion (D13), generalization value (D14) | defined in the dictionary; **not computed** |
| **Decision policy**: objective, weights, gates, aggregation | downstream selection authority | everything in §8 | not defined here |

Every dimension in the dictionary carries a `role` field so the boundary stays explicit.

## 2. Candidate dimensions

The dictionary defines D01–D18. They cover every dimension the sprint lists: evidence strength, replication, rule precision, opportunity frequency, data accessibility, execution burden, implementation dependencies, structural novelty, reusable capability expansion, generalization, regime robustness, cost sensitivity, tail risk, and evidence uncertainty. It adds three: source quality, contradiction/failed replication, and evidence cluster.

**Directly measurable** (counts or coded categories already in the dataset):
- D02 replication count, D03 source tier, D04 contradiction flags, D05 post-publication direction;
- D06 rule precision, D07 opportunity frequency, D08 net-of-cost direction;
- D09 data accessibility, D10 execution burden, D11 dependency set;
- D16 tail class, D17 UNKNOWN count and depth mix, D18 cluster.

**Require ordinal/categorical construction by the downstream authority from traceable text:**
- D01 evidence grade (procedure in §3);
- D14 generalization;
- D15 regime robustness.

**Derived counts with a stated construction:** D12 and D13, from RES-001B §4.

## 3. Evidence grading procedure (for D01)

Finance has no standard evidence-grading system for strategies. The closest defensible structural analogue is GRADE (GUYATT-ET-AL-2008-GRADE). It separates **quality of evidence** from **strength of recommendation**, which is exactly the separation this sprint requires. Its domains adapt to option-strategy evidence as follows. The adaptation is an INFERENCE by the Researcher, not a finding of the GRADE source.

**Starting level by D03 source tier:**
- peer-reviewed with out-of-sample or independent replication: HIGH;
- peer-reviewed in-sample: MODERATE;
- institutional, working paper, or sponsor: LOW;
- practitioner-only or internal: VERY_LOW;
- bibliographic-only sources are not graded.

**Downgrade domains.** Each domain lowers the grade by one level when present. The trigger fields are traceable in the dataset and dossiers.

| Domain | Option-strategy meaning | Trigger (traceable) | Finance source motivating it |
|---|---|---|---|
| Risk of bias | Sponsor interest, publisher-selected variants, no cost model | `source_quality_tier` in sponsor/practitioner tiers; dossier limitations | — |
| Inconsistency | Credible sources disagree on sign or significance | D04 contradiction or failed replication | JENSEN-KELLY-PEDERSEN-2023 vs HOU-XUE-ZHANG-2020 show that method choice can flip conclusions |
| **Indirectness** | Evidence is for a different structure, underlying, horizon or side. Examples: SPX evidence used for SPY; straddle-sort evidence used for calendars; stock-return evidence used for an option expression; hedged evidence used for unhedged structures | dossier "Unresolved rule gaps"; RES-001B hybrid classification | — |
| Imprecision | Point estimates, samples or costs unrecovered | D17 (UNKNOWN count, abstract-only depth) | — |
| Multiple testing / publication bias | Many related signals, selected variants, no post-publication evidence | D05 = none_found or negative; many sibling signals in the same cluster | HARVEY-LIU-ZHU-2016 (t > 3.0 hurdle), MCLEAN-PONTIFF-2016 (58% post-publication decline), BAILEY-LOPEZDEPRADO-2014-DSR, BAILEY-ET-AL-2016-PBO |

Indirectness is the domain most specific to options, and it is systematically present in this landscape. The best-evidenced families are studied on SPX, delta-hedged, or as cross-sectional portfolios. The structures ASA has discussed most are unhedged single-name or ETF verticals and condors. A grading that ignores indirectness would transfer evidence to those structures without support.

**Upgrade (optional):** independent replication across markets (D02 ≥ 1 with a different universe), or net-of-cost positive evidence (D08 = positive).

**Illustrative application.** This shows how the procedure works and is not a grade. The downstream authority owns D01. FAM-VRP-DEFINED-RISK starts at LOW (sponsor/practitioner tier). It then triggers risk of bias, indirectness (the parent-premium evidence is for PUT/SHORT-VOL), and imprecision. The procedure would therefore place it at the floor. Whether that matters is a downstream decision.

## 4. Missing data and UNKNOWN handling

**Principle.** UNKNOWN means *not recovered*. It is not zero, not negative, and not average. The dataset already keeps UNKNOWN, `none`, and `none_found` as distinct values.

| Option | Mechanism | Prevents false zeroes? | Trade-off |
|---|---|---|---|
| M1 Categorical UNKNOWN | UNKNOWN is its own level in every categorical/ordinal dimension; aggregation methods that cannot accept it must use M2–M5 | yes | Some aggregation methods cannot use it directly |
| M2 Interval (bounds) scoring | Score each candidate twice, UNKNOWN at the worst and at the best feasible level; report the interval | yes | Honest, but intervals may overlap heavily (itself informative) |
| M3 Available-case renormalization | Drop the dimension for that candidate and renormalize the remaining weights; report coverage | yes, but hides uncertainty | Candidates with less evidence can score higher by having fewer dimensions |
| M4 Explicit uncertainty dimension | Keep UNKNOWN out of each dimension and carry D17 as a separate penalty dimension whose weight is chosen downstream | yes | Makes the penalty size an explicit policy choice |
| M5 Coverage gate | Exclude candidates below a minimum coverage from compensatory scoring; report them separately | yes | Non-compensatory; the threshold is a policy choice |
| ✗ Zero imputation | UNKNOWN → 0 | **no** | Violates the sprint's unknown rule; listed only to exclude it |
| ✗ Mean imputation | UNKNOWN → cross-family mean | **no** | Manufactures values; violates the unknown rule |

**Researcher characterization (INFERENCE):** M1 + M2 + M4 together preserve the most information and are the least exposed to the M3 pathology. Choosing among them is downstream.

## 5. Double counting and correlated dimensions

### 5.1 Dimension correlation

Five groups (G1–G5) are defined in the dictionary. Rules:
- **G1 evidence:** use D01 **or** its components (D02–D05, D15, D17). Using both counts the same evidence twice.
- **G3 architecture:** D12 (novelty) and D11 (dependencies) are the same information with opposite sign. Use only one. D13 depends on D11.
- **G2 implementability:** D08, D10 and D11 share drivers (legs, hedging, liquidity). If more than one is used, the downstream authority should document their assumed overlap. It can also group them hierarchically, giving the group one weight split within it.

### 5.2 Evidence-cluster double counting

Families that harvest the **same premium** share evidence (dictionary D18). For example, C_VRP_INDEX covers put writing, covered calls, short vol, defined-risk, 0DTE, tail hedging, collars, and index skew. Rules:

1. A source cited in several families of one cluster counts **once per cluster** when judging whether the *premium* is supported.
2. Evidence for the seller side of a premium is evidence **against** the buyer side. It must not count as support for both (e.g. BONDARENKO-2019-CBOE supports PUTWRITE and weighs against TAIL-HEDGE).
3. Within C_XS_OPTION_FACTORS, HORENSTEIN-VASQUEZ-XIAO-2026 and GOYAL-SARETTO-2022-IPCA indicate that nominally separate anomalies load on common factors. Counting each family's peer-reviewed sources independently would overstate breadth.

### 5.3 Hybrids

A hybrid such as Skew Momentum is assessed per component (RES-001B §1.1). The weakest essential component bounds the combination's evidence grade. Component evidence is not summed. This is a methodological option, marked INFERENCE. The alternative is to grade only studies of the exact combination, which here yields UNGRADED.

## 6. Research quality vs product utility vs architectural value

The dictionary assigns each dimension to one **axis**:
- `research_quality`: D01–D08, D15, D17, D18;
- `implementation_burden`: D09–D11;
- `architectural_value`: D12–D14;
- `risk`: D16.

**Rule:** ROLE-RESEARCH never merges axes. A downstream authority may combine them only in a stated objective. Any combined output must still report each axis separately. That makes it visible when, for example, high architectural value is offsetting weak evidence. The independence rule applies: axis `implementation_burden` and axis `architectural_value` inputs must never feed D01.

## 7. Normalization and aggregation options

### 7.1 Normalization

| Option | Suits | Caveat |
|---|---|---|
| Anchored ordinal map (e.g. VERY_LOW=0 … HIGH=3), anchors defined before seeing candidates | ordinal/categorical dimensions (most here) | Equal spacing is an assumption; state it |
| Log or capped counts (e.g. min(count, 3)) | D02, peer-reviewed counts | Otherwise large literatures (XS families) dominate through volume |
| Percentile rank within candidate set | counts | **Rank reversal**: results change when candidates are added or removed (TRIANTAPHYLLOU-2000, bibliographic) |
| Min-max | continuous | Same rank-reversal exposure; sensitive to outliers |
| No normalization (non-compensatory methods) | gates, Pareto, lexicographic | — |

### 7.2 Aggregation

| Method | Needs weights? | Handles UNKNOWN? | Compensatory? | Notes |
|---|---|---|---|---|
| Gates (screens) | no (thresholds) | via M5 | no | Transparent; thresholds are policy |
| Pareto dominance on axis vectors | **no** | with M2 intervals | no | Yields a non-dominated set, not a ranking. Weight-free, so it is the least policy-laden |
| Lexicographic ordering | order only | M1 | no | Requires ordering axes (policy) |
| Weighted sum (SAW) | yes | M2/M3/M4 | fully | Simple. Sensitive to normalization and correlated dimensions |
| TOPSIS / distance-to-ideal | yes | M2/M4 | yes | Rank-reversal exposure |
| Outranking (PROMETHEE/ELECTRE family) | yes + preference functions | M1 possible | partially | Handles ordinal data. More parameters |

## 8. Sensitivity to weighting

No result from a weighted method should be reported without sensitivity analysis. Options, following the global sensitivity-analysis requirements reviewed in SALTELLI-2002:

1. **One-at-a-time** perturbation (±50% per weight). Cheap, but it misses interactions.
2. **Weight-space sampling.** Draw weights uniformly from the simplex, or from a Dirichlet centred on the chosen weights. Report, for each candidate, the probability of falling in the top set and the rank interval.
3. **Stability intervals.** For each weight, find the range over which the top set is unchanged.
4. **Missing-data sensitivity.** Recompute under M2 lower/upper bounds.
5. **Normalization sensitivity.** Recompute under two normalization options from §7.1.

A downstream result is robust only if it is stable under options 2, 4 and 5. **Researcher observation (INFERENCE):** because most dimensions here are coarse ordinal codes with many UNKNOWNs, weight-sampling will likely show wide rank intervals. That is an accurate reflection of the evidence state, not a defect of the method.

## 9. Downstream selection input contract

A downstream selection authority can apply this framework without new Researcher evidence by supplying the following.

**Required inputs from the downstream authority:**

| # | Input | Allowed values |
|---|---|---|
| 1 | Objective statement | free text; must name the axis or axes it serves |
| 2 | Candidate set | subset of `records[*].research_id` in the RES-001C dataset |
| 3 | Dimensions used | subset of D01–D18, respecting §5.1 exclusions |
| 4 | Direction per dimension | higher-better / lower-better / target / gate-only |
| 5 | Missing-data policy | M1–M5 (not zero or mean imputation) |
| 6 | Normalization per dimension | §7.1 option |
| 7 | Aggregation | §7.2 method |
| 8 | Weights or weight distribution | if the aggregation requires them |
| 9 | Gates | thresholds on any dimension |
| 10 | Evidence-grade procedure | §3 as written, or a stated modification |
| 11 | Sensitivity analyses | at least §8 options 2, 4, 5 for weighted methods |

**What the research dataset guarantees:**
- Every coded value traces to a dossier section and to `research/sources/<id>.yaml`.
- UNKNOWN, `none`, and `none_found` are preserved distinctly.
- Evidence codings were assigned independently of implementation codings.
- Statuses describe evidence only.

**What the output of a downstream application must retain:**
- the per-axis results, alongside any combined result;
- the D17 uncertainty and the §8 sensitivity results;
- the source IDs behind each D01 grade;
- the cluster (D18) of each candidate.

**What still requires Researcher work (the known evidence gaps, not new invention):**
- full-text recovery for sources at abstract or search-summary depth;
- the independent-evidence gap for FAM-VRP-DEFINED-RISK;
- verification of the bibliographic-only sources (dispersion, dividend exercise, VIX basis, commodity VRP).

## 10. Completion statement

The instrument is complete to the sprint's standard. A downstream authority can choose an objective and a weighting policy and apply it to `RES-001C-evidence-dataset.yaml` using D01–D18 without asking the Researcher to invent evidence. Nothing here selects a strategy, sets a weight, or ranks a candidate.
