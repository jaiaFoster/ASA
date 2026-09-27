# Capability-Primitive Comparison — Report (v2)

- **Selection exercise:** ASA-STRATEGY-CAPABILITY-SELECTION-001
- **Basis:** `main` @ `4e56c608`
- **Governing method:** ASA-ARCH-STRATEGY-SELECTION-RESOLUTION-001 (ROLE-ARCH), **adopted by the Founder** on 2026-09-27, applied together with:
  - ASA-FOUNDER-STRATEGY-SELECTION-DIRECTIVES-001;
  - ASA-ARCH-STRATEGY-SELECTION-THRESHOLDS-001 and its clarifications.
- **Data:** [`primitive-comparison-matrix.yaml`](primitive-comparison-matrix.yaml)
- **Status:** Founder consideration set produced. **This is not a recommendation to implement any capability, and no implementation is authorized.**

Every conclusion is labelled by source: **[E]** external evidence, **[A]** architecture, **[M]** Founder-adopted method (weights and rules).

## 1. Result

**Method.** Role-stratified Pareto analysis, then official weighted scoring, then dependency-aware bundles, then sensitivity classification.

### Primitive consideration set

| Primitive | Role | Official score | Governing lane front | Sensitivity class |
|---|---|---|---|---|
| A12 liquidity / effective-spread measurement | QUALITY_INFRASTRUCTURE | 0.855 | 1 | **ROBUST** |
| P03 straddle | EXPRESSION | 0.655 | 2 | ROBUST_TO_MODERATE_SHIFTS |
| A07 model-free risk-neutral moments | ANALYTIC | 0.640 | 1 | **ROBUST** |
| P01 single option leg | EXPRESSION | 0.618 | 1 | WEIGHT-SENSITIVE |
| A15 generalized margin/capital model | ANALYTIC | 0.618 | 1 | WEIGHT-SENSITIVE |
| A14 dynamic delta-hedge simulation | ANALYTIC | 0.591 | 2 | WEIGHT-SENSITIVE |
| A06 skew/smirk history | ANALYTIC | 0.587 | 1 | WEIGHT-SENSITIVE |
| P09 stock + option overlay | EXPRESSION | 0.580 | 2 | WEIGHT-SENSITIVE |
| A08 historical option-price panel | DATA | 0.580 | 1 | WEIGHT-SENSITIVE |
| X01 index-option identity/root/settlement | ENABLING_CONTRACT | 0.568 | 1 | **conditional enabler** (required by the PW, CC and SV bundles; burden-sensitive) |

### Bundle consideration set

Marginal burdens are listed in build order, with shared dependencies charged once.

| Bundle | Family made faithfully expressible | Members (marginal burden) | Mean member score |
|---|---|---|---|
| Event volatility | EV (QUALIFIED) | P03 B3, A09 B1 | 0.612 |
| Index put writing | PW (QUALIFIED) | X01 B4, P01 B3 | 0.593 |
| Index short volatility | SV (QUALIFIED) | X01 B4, P03 B3 | 0.611 |
| Index covered call / BXM | CC (QUALIFIED) | X01 B4, P09 B3 | 0.574 |
| Option-implied information | OS (QUALIFIED) | A07 B2, A10 B3, A11 B3 | 0.583 |
| Cross-sectional option returns | XR (FAVORABLE_QUALIFIED) | A08 B3, P12 B3, A14 B3, P10 B3 (A14 not re-charged) | 0.569 |
| Shared quality layer | all | A12 B1, charged once platform-wide | — |

**Independent recomputation.** Every official score and bundle mean above was recomputed from the RES-001C dataset and the Architect's architecture fields. All of them match the values stated in the resolution.

## 2. Method as applied

- **Evidence utility (EU) [E][M].** For each family, EU = strength × direction × completeness confidence. A primitive takes the maximum over its non-UNFAVORABLE mapped families. UNGRADED strength is carried as an interval.
  - Strong evidence of an unfavorable outcome contributes 0.
  - No family's reported returns are transferred to a primitive.
- **Breadth [E][M].** Distinct credible evidence clusters ÷ 4, capped at 1. This is independent of source counts and of architectural reuse.
- **Architecture [A][M].** Architecture confidence multiplies the architecture subtotal. Reuse confidence multiplies the reuse term. Neither is an additive reward.
- **Official score [M]:**

  score = 0.35·EU + 0.15·breadth + arch_conf · (0.25·reuse·reuse_conf + 0.25·burden)

  Standalone scoring uses the effective standalone burden. Bundles use the marginal burden once HARD dependencies are held.
- **Governing Pareto [M].** Computed within role lanes. The common pool, the random-weight pass rates, and the score-component axes (§5) are sensitivities only.
- **Advancement [M]:**
  - A substantive primitive advances when it is on lane front ≤ 2 and its score is ≥ 0.58 (lower bound for intervals).
  - An enabling contract advances conditionally, when it is on lane front 1 and a faithful advancing bundle requires it.
  - A bundle advances when it makes a QUALIFIED or FAVORABLE_QUALIFIED family faithfully expressible, its mean member score is ≥ 0.55, it excludes replication-only data, and it charges shared dependencies once.

**Architecture reconciliation applied:**

| Item | Value applied |
|---|---|
| A12 | reuse confidence MEDIUM |
| A16 | role ANALYTIC; effective standalone B4, intrinsic B3 once X01 is held |
| X02a | role DATA; B4 standalone, B1 after X01; confidence MEDIUM |
| X02b | role DATA; confidence HIGH |
| X03 | confidence HIGH |
| X04 | role DATA; confidence MEDIUM; its consumer links remain conditional |
| X01 | enabling reach 7 (PW, CC, SV, DR, US, SK, DP). HARD for PW, CC, SV, US, SK, DP; conditional for DR |

## 3. Governing lane fronts

| Lane | Front 1 | Front 2 | Front 3 | Later |
|---|---|---|---|---|
| EXPRESSION | P01 | P03, P09 | P10, P11, P12, P14 | P04 · P05, P07, P15 · P08 · P13 |
| ANALYTIC | A06, A07, A15 | A09, A14 | A17 | A16 |
| DATA | A08 | A10, A11 | X02b, X04 | X02a |
| QUALITY_INFRASTRUCTURE | A12 | | | |
| ENABLING_CONTRACT | X01 | X03 | | |

These are the fronts stated in the resolution. They are reproduced exactly by Pareto analysis on four axes:
- E1: the strongest credible phenomenon strength;
- E2: its completeness confidence;
- canonical reuse (the enabling count for X capabilities);
- effective standalone burden.

## 4. Candidates that do not advance, and why

| Candidate | Score | Reason | Source |
|---|---|---|---|
| A09 expected move | 0.568 | below 0.58; survives inside the event-volatility bundle | [M] |
| A10, A11 borrow fee, signed volume | 0.555 | below 0.58; survive jointly inside the option-information bundle | [M] |
| P12 cross-sectional portfolio | 0.580 | lane front 3; survives inside the cross-sectional bundle | [M] |
| P11 option strip | 0.561 | lane front 3 | [M] |
| P10 delta-hedged option | 0.524 | lane front 3; B4 standalone; survives inside the cross-sectional bundle | [A][M] |
| P04 strangle | 0.462 | lane front 4; its only credible use (SV) is covered by P03 | [E][A] |
| P05 four-leg wings | 0.307 | DR evidence LOW/UNRESOLVED and the US use is unfavorable. **This is an evidence limitation, not a structural judgement.** | [E] |
| P07 diagonal, A17 option-return history | 0.280, 0.254 | local reuse and weak evidence; A17 depends HARD on A08 | [E][A] |
| P14 volatility futures | 0.310 | MODERATE evidence and B4 instrument work; the VX bundle mean of 0.31 is below 0.55 | [E][A] |
| X03 cross-asset | 0.205 | B4 identity-bearing; weak evidence completeness | [A][E] |
| P15, X04 parity and rates | 0.138–0.236, 0.124–0.223 | evidence UNGRADED; **Research hold, with an interval rather than a synthetic score** | [E] |
| P08, X02a, X02b | ≤ 0.200 | their only use is ultra-short (US), which is UNFAVORABLE | [E] |
| P13, A16 | 0.062 | their only use is dispersion (DP), which is UNFAVORABLE | [E] |

**Bundles that do not advance:**
- **Direction not FAVORABLE_QUALIFIED or QUALIFIED** **[E]**: TS, XL, XM, DR, AR, CA (UNRESOLVED) and CL, TH, US, SK, DP, DX (UNFAVORABLE).
- **Mean member score below 0.55** **[M]**: VX.

## 5. Sensitivity

**Profiles.** The resolution names three profiles but does not give their weights. Two strengths were therefore applied, and both are recorded in the matrix:

| Profile | Moderate | Strong |
|---|---|---|
| Evidence-heavy | .40 / .20 / .20 / .20 | .50 / .20 / .15 / .15 |
| Architecture-leverage | .30 / .10 / .35 / .25 | .25 / .10 / .40 / .25 |
| Burden-averse | .30 / .10 / .20 / .40 | .25 / .10 / .15 / .50 |

Weights are in the order EU / breadth / reuse / burden.

**Classes:**

| Class | Primitives | Basis |
|---|---|---|
| ROBUST (passes 0.58 under all strong profiles) | **A12, A07** | [E]+[A] for A07; [A] for A12 |
| ROBUST_TO_MODERATE_SHIFTS | **P03** | fails only strong burden-aversion (0.537) |
| WEIGHT-SENSITIVE | P01, A15, A14, P09, A08 (below 0.58 under burden-aversion); **A06** (below 0.58 under evidence-heavy: 0.565–0.566) | [M] |
| Conditional enabler | X01 (0.375 under strong burden-aversion) | [A] |

**Supplemental: random-weight pass rate.** This is the share of 20,000 uniform weight vectors under which the score is ≥ 0.58.

| Primitive | Pass rate |
|---|---|
| A12 | 1.00 |
| A07 | .98 |
| P03 | .78 |
| P01, A15 | .55 |
| A14 | .44 |
| A06, X01 | .37 |
| P09, A08 | .34 |

**Common pool (sensitivity only):**
- Front 1: A12, X01.
- Front 2: A06, A07, A09, P03.
- Front 3: A14, A15, P01.

## 6. Findings for Architect and Founder attention

These do not change the consideration set.

1. **Two sensitivity labels differ from the resolution.**
   - **A06:** the resolution calls it robust. It falls below 0.58 under both evidence-heavy strengths, because its evidence rests on a single cluster (OS, breadth 0.25). It is therefore classed WEIGHT-SENSITIVE.
   - **P03:** the resolution also calls it robust. It stays above 0.58 under moderate profiles but falls to 0.537 under strong burden-aversion.

   Both labels depend on the unstated profile weights; the resolution's labels hold only under milder profiles than those tested here.
2. **P09's lane front depends on the Pareto axes.** Under the governing axes (§3), P09 is on expression front 2 and advances. If the lane Pareto is instead computed on the official score's own components (EU, breadth, confidence-adjusted reuse, burden), P01 and P03 dominate P09 on breadth, P09 falls to front 3, and it would not advance. The governing fronts are those stated in the Founder-adopted resolution. The alternative is recorded in the matrix as `sensitivity_lane_fronts_score_component_axes`.
3. **The Founder directive and both Architect packets are not on `main`.** They are referenced by ID. Committing them to their owners' locations would complete provenance.

## 7. Boundaries preserved

- No reported return, cost, or risk figure from external research is attributed to any ASA expression. Advancement is not a profitability claim.
- Unresolved returns and costs advance unchanged and remain research needs for any advancing item (Founder directive).
- The research corpus and the Architect's classifications are unmodified. Architecture values appear exactly as supplied and reconciled.
- The Founder-owned decision about what, if anything, to pursue from this consideration set is to be recorded separately from these files.
