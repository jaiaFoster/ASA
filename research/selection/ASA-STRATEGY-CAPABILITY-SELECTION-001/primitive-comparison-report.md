# Capability-Primitive Comparison — Report

- **Selection exercise:** ASA-STRATEGY-CAPABILITY-SELECTION-001
- **Basis:** `main` @ `4e56c608`, applying:
  - ASA-FOUNDER-STRATEGY-SELECTION-DIRECTIVES-001 (Founder);
  - ASA-ARCH-STRATEGY-SELECTION-THRESHOLDS-001 plus its clarifications (ROLE-ARCH).
- **Data:** [`primitive-comparison-matrix.yaml`](primitive-comparison-matrix.yaml). Raw architecture and evidence inputs sit beneath every derived value.
- **Status:** decision support only. **No primitive is selected.** Weighted values are **illustrative**, because official weights are Founder-owned and have not been supplied.

Every conclusion below is labelled by where it comes from: **[E]** external evidence, **[A]** architecture, **[W]** weighting or product choice.

## 1. Summary

1. **37 capabilities compared.** Primitives P01–P15 and A01–A17 cover all 19 researched families; X01–X04 are enabling capabilities added by Architecture. 8 are NATIVE baseline and 29 are candidates.
2. **Stable across every Pareto, lane and weighting variant:**
   - **A07, model-free risk-neutral moments,** is always on common-pool front 2 and analytic-lane front 1. Top-5 in 100% of weight samples. **[E]** HIGH phenomenon strength across 3 independent evidence clusters. **[A]** B2, no protected-contract change, architecture confidence MEDIUM.
   - **A12, liquidity / effective-spread measurement,** is always common-pool front 1. **[A]** reuse 19 at B1. Evidence does not discriminate for it, since it serves every family. Its role is QUALITY_INFRASTRUCTURE, so whether it competes in the common pool or its own lane is **[W]**.
   - **P13, A16, P08 and X02b are always on the last fronts (7–9).** **[E]** None has a credible use: every researched family using them has UNFAVORABLE evidence for return-seeking use (DP for P13 and A16; US and SK for P08; US for X02b).
   - **X02a** also has no credible use. It is last in the canonical and reach variants, but rises to front 4 under incremental burden (B1 once X01 is held). That rise is **[A]**, not evidence.
3. **P01 single leg** is expression-lane front 1 and common-pool front 2 in every variant. **[E]** HIGH/MEDIUM from index put-writing. **[A]** B3 additive contract. Top-5 in 100% of weight samples.
4. **The Architect's P09 correction (B4→B3) moves P09 from front 4 to front 3.** **[A]** Its only credible use is covered call (CC), and the faithful CC form also needs X01.
5. **Positions sensitive to policy:**
   - P03 (straddle), A06, A09, A14, A15 and X01 sit on fronts 2–3.
   - Their order depends on the reuse measure (the reach sensitivity moves P03 and X01 to front 2), incremental burden, and weights **[W]**.
6. **No primitive carries return evidence for an ASA expression.** Only XS-OPTION-RETURNS has favourable (factor-qualified) net-of-cost evidence. Advancing a primitive is not a claim of profitability.

## 2. Method

**Architecture inputs** are used as supplied:
- canonical reuse is the RES-001B §3 count;
- X01–X04 carry a separate `enabling_reuse_count`;
- the corrected P09 burden;
- populated architecture confidence;
- the HARD dependencies ruled by the Architect;
- the roles.

**Evidence** is derived from the RES-001C dataset:

| Measure | Definition |
|---|---|
| Phenomenon strength | RES-001D §3 *starting level* only. There is no inconsistency downgrade (Founder scrutiny-bias rule) and no indirectness downgrade for the phenomenon (Founder indirect-evidence rule). Bibliographic-only replications are not counted. |
| Direction | Kept separate from strength. |
| Credible use | A family with strength ≥ LOW and direction ≠ UNFAVORABLE. |
| E1 | The strongest credible strength among a primitive's families. |
| E2 | The confidence of that strongest use. |

**Comparison:**
- Layered Pareto fronts on E1, E2, reuse, and burden. They are computed for the common pool and for each role lane.
- A weighted matrix using the anchored-ordinal normalization from RES-001D §7.1.
- A weight-sensitivity check: 20,000 uniform draws over the evidence / reuse / burden weight simplex.

UNKNOWN is never scored as zero. P15 and X04 (whose only family, AR, is ungraded) carry the evidence interval 0–1.

**The evidence-confidence thresholds are a Research proposal pending Founder approval** (Architect clarification 8). They affect only E2 and the confidence-aware profile.

## 3. Family evidence profiles

Unchanged from ANALYSIS-002; values are in the matrix file.

| Direction for return-seeking use | Families |
|---|---|
| FAVORABLE_QUALIFIED | XR |
| QUALIFIED | PW, CC, SV, VX, EV, OS |
| UNRESOLVED | DR, TS, XM, XL, CA, AR (AR ungraded) |
| UNFAVORABLE | TH, CL, US, SK, DP, DX |

## 4. Pareto fronts

| Front | Common pool (canonical) | Reach sensitivity | Incremental-burden sensitivity |
|---|---|---|---|
| 1 | A12 | A12 | A12 |
| 2 | P01, A06, A07 | P01, **P03**, A06, A07, **X01** | P01, A06, A07 |
| 3 | P03, P09, A09, A14, A15, X01 | P09, A09, A14, A15 | P03, P09, **P10**, A09, A14, A15, X01 |
| 4 | P10, P11, P12, P14, A08 | P10, P11, P12, P14, A08 | P11, P12, P14, A08, **A17**, **X02a** |
| 5 | P04, A10, A11 | same | same |
| 6 | P05, P07, P15, X03, X04 | same | same |
| 7 | P08, A17 | P08, A17 | P08 |
| 8 | A16, X02b | same | same |
| 9 | P13, X02a | P13, X02a | P13 |

**Role lanes** (canonical measures), available if you prefer separate advancement lanes:

| Lane | Front 1 | Front 2 | Front 3 | Later |
|---|---|---|---|---|
| EXPRESSION | P01 | P03, P09 | P10, P11, P12, P14 | P04 · P05, P07, P15 · P08 · P13 |
| ANALYTIC | A06, A07, A15 | A09, A14 | A17 | |
| DATA | A08 | A10, A11 | A16, X02b, X04 | |
| ENABLING_CONTRACT | X01 | X03 | X02a | |
| QUALITY_INFRASTRUCTURE | A12 | | | |

The **reach** sensitivity uses `documented_dependency_reach_count`, which covers RES-001B §3 plus §4.3 expression dependencies, excluding replication-only needs. P03 goes from 4 to 7, P01 from 4 to 5, and X01 from 4 to 6. It is **not** the canonical metric (Architect clarification 4).

## 5. Primitive table (candidates)

Arch conf = architecture confidence.

| ID | Role | E1 / E2 [E] | Credible uses | Unfavorable | Reuse [A] | Burden standalone → intrinsic [A] | Contract | Arch conf | Common front | Equal-weight (illustr.) |
|---|---|---|---|---|---|---|---|---|---|---|
| A12 | QUALITY_INFRA | HIGH / M (non-discriminating) | 12 | 6 | 19 | B1 | NONE | HIGH | 1 | .92 |
| A07 | ANALYTIC | HIGH / LM | OS, XL, SV | SK | 4 | B2 | NONE (rates conditional) | MEDIUM | 2 | .75 |
| A06 | ANALYTIC | HIGH / LM | OS | SK | 2 | B1 | NONE | HIGH | 2 | .75 |
| P01 | EXPRESSION | HIGH / M | PW, CA | TH, DX | 4 | B3 | ADDITIVE_PUBLIC | HIGH | 2 | .67 |
| P03 | EXPRESSION | HIGH / LM | SV, EV, XM, XR | — | 4 | B3 | ADDITIVE_PUBLIC | HIGH | 3 | .67 |
| P09 | EXPRESSION | HIGH / M | CC | TH, CL | 3 | **B3** (corrected) | ADDITIVE_PUBLIC | HIGH | 3 | .67 |
| A09 | ANALYTIC | MOD / LM | EV, TS | — | 2 | B1 | NONE | HIGH | 3 | .67 |
| A14 | ANALYTIC | HIGH / LM | SV, XR | SK, DP | 4 | B3 | NONE (analytical) | MEDIUM | 3 | .67 |
| A15 | ANALYTIC | HIGH / M | PW, SV, VX | — | 3 | B3 | UNKNOWN | HIGH | 3 | .67 |
| X01 | ENABLING | HIGH / M | PW, DR | US, SK | enabling 4 | B4 | IDENTITY_BEARING | HIGH | 3 | .58 |
| P10 | EXPRESSION | HIGH / LM | SV, XR | SK, DP | 4 | B4 → B3 given A14 | ADDITIVE_PUBLIC | MEDIUM | 4 | .58 |
| P11 | EXPRESSION | HIGH / LM | SV, TS | SK | 3 | B3 | ADDITIVE_PUBLIC | HIGH | 4 | .67 |
| P12 | EXPRESSION | HIGH / LM | XR, XM, XL | — | 3 | B3 | NONE (not proven) | HIGH | 4 | .67 |
| A08 | DATA | HIGH / LM | XR, XM, XL | — | 3 | B3 | ADDITIVE_PUBLIC | HIGH | 4 | .67 |
| P14 | EXPRESSION | MOD / M | VX | — | 1 | B4 | IDENTITY_BEARING | HIGH | 4 | .33 |
| P04 | EXPRESSION | HIGH / LM | SV | US | 2 | B3 | ADDITIVE_PUBLIC | HIGH | 5 | .58 |
| A10 | DATA | HIGH / LM | OS, XR | — | 2 | B3 | ADDITIVE_PUBLIC | HIGH | 5 | .58 |
| A11 | DATA | HIGH / LM | OS, XR | — | 2 | B3 | ADDITIVE_PUBLIC | HIGH | 5 | .58 |
| P05 | EXPRESSION | LOW / LM | DR | US | 2 | B3 | ADDITIVE_PUBLIC | HIGH | 6 | .42 |
| P07 | EXPRESSION | MOD / LM | TS | — | 1 | B3 | ADDITIVE_PUBLIC | HIGH | 6 | .42 |
| P15 | EXPRESSION | UNKNOWN | — (AR ungraded) | — | 1 | B3 | ADDITIVE_PUBLIC | HIGH | 6 | .17–.50 |
| X03 | ENABLING | HIGH / L | CA | — | enabling 1 | B4 | IDENTITY_BEARING | not stated | 6 | .42 |
| X04 | DATA | UNKNOWN | — (AR ungraded) | — | enabling 1 | B3 | ADDITIVE_PUBLIC | not stated | 6 | .17–.50 |
| P08 | EXPRESSION | NONE credible | — | US, SK | 2 | B3 | ADDITIVE_PUBLIC | HIGH | 7 | .25 |
| A17 | ANALYTIC | MOD / L | XM | — | 1 | B3 → B2 given A08 | NONE | HIGH | 7 | .42 |
| A16 | DATA | NONE credible | — | DP | 1 | B3 (raw) | ADDITIVE_PUBLIC | HIGH | 8 | .17 |
| X02b | DATA | NONE credible | — | US | enabling 1 | B3 | ADDITIVE_PUBLIC | not stated | 8 | .17 |
| P13 | EXPRESSION | NONE credible | — | DP | 1 | B4 | ADDITIVE_PUBLIC (likely) | HIGH | 9 | .08 |
| X02a | ENABLING | NONE credible | — | US | enabling 1 | B4 (via X01) → B1 | NONE | MEDIUM | 9 | .08 |

**Baseline (NATIVE):** P02 vertical (credible use DR only, LOW), P06 calendar (TS and EV, MODERATE, evidence from non-calendar forms), and A01–A05 and A13. **[A]** Native support is an architectural advantage, not evidence.

## 6. Bundles with marginal cost (Architect clarification 7)

Each primitive is charged its burden after the HARD dependencies already present in the bundle, or native, are removed. Costs are listed, not summed.

A family is "faithful" when its evidenced form becomes expressible. Credible families are in **bold**; UNFAVORABLE families are in plain text.

| Bundle (in build order) | Marginal burdens | Families made faithfully expressible | Replication-only needs (research planning, not architecture) |
|---|---|---|---|
| A12 | B1 | — (serves cost measurement for all) | — |
| A07 | B2 | — alone | — |
| A07, A10, A11 | B2, B3, B3 | **OS** | A08 for signal history |
| P03, A09 | B3, B1 | **EV** | A08 |
| P03, P12 | B3, B3 | **TS** (straddle-sort form) | A08 |
| P03, P12, A07 | B3, B3, B2 | **TS**, **XL** | A08 |
| P03, P12, A08, A17 | B3, B3, B3, **B2** (A08 not re-charged) | **TS**, **XM** | — |
| P03, P12, A14, P10 | B3, B3, B3, **B3** (not two hedging subsystems) | **TS**, **XR** | A08 |
| X01, P03 | B4, B3 | **SV** (index straddle form) | — |
| X01, P01, P05 | B4, B3, B3 | **PW**, **DR** (CNDR/BFLY form); DX | — |
| X01, P01, P05, P09 | B4, B3, B3, B3 | **PW**, **DR**, **CC**; TH, CL, DX | — |
| X01, P01, P05, X02a | B4, B3, B3, **B1** | **PW**, **DR**; US, DX | X02b for 0DTE replication |
| P09 | B3 | CL only (QQQ collar; CC and TH need X01) | — |
| A14, P10 | B3, B3 | — alone | — |

**[A] + [E], derived:**
- **P03 is the most shared expression primitive.** It appears in the event, cross-section, hedge, and index-volatility bundles and is charged once.
- **X01 is charged once for all index-faithful families.** Its credible payoff is PW, DR, CC, and SV, provided P01/P05/P09/P03 are also present.
- **Several credible families need no new data to operate.** TS, XL, XR, and EV are expressible without A08; A08 is needed only to replicate their published evidence.

## 7. Weighted matrix (illustrative; the weights shown are not policy)

| Primitive | Equal | Evidence-led | Reuse-led | Burden-averse | Confidence-aware | Top-5 frequency (uniform weights) | 5–95% rank band |
|---|---|---|---|---|---|---|---|
| A12 | .92 | .94 | .94 | .88 | .95 | 1.00 | 1–1 |
| A07 | .75 | .81 | .75 | .69 | .78 | 1.00 | 2–4 |
| P01 | .67 | .75 | .69 | .56 | .80 | 1.00 | 3–5 |
| A06 | .75 | .81 | .69 | .75 | .78 | .66 | 2–13 |
| P03 | .67 | .75 | .69 | .56 | .73 | .56 | 4–6 |
| A09 | .67 | .69 | .62 | .69 | .68 | .44 | 3–18 |
| P09 | .67 | .75 | .69 | .56 | .80 | .34 | 5–7 |
| P11, P12, A08, A14, A15 | .67 | .75 | .69 | .56 | .73 (A15: .80) | .00 | 6–12 |
| X01 | .58 | .69 | .62 | .44 | .75 | .00 | 12–25 |
| … | | | | | | | full list in the YAML |

**Reading.** Evidence strength E1 saturates at HIGH for 16 primitives, so differences between them come mostly from reuse and burden **[A]**. The weighted matrix therefore differentiates on evidence only if your weights give real weight to confidence (E2), or add credible-use breadth as a dimension **[W]**.

## 8. Uncertainty preserved

- **Evidence.** 99 of 101 sprint sources are at abstract depth or shallower. Net-of-cost results, sample periods, and exact rules are mostly UNKNOWN. None was resolved here, and all advance unchanged (Founder unresolved-returns rule).
- **Evidence confidence** is a Research proposal (§2), not yet approved.
- **Architecture.** Provider-specific unknowns stay in `architecture_unknowns`. X02b, X03, and X04 have no architecture confidence stated in the clarifications, so they are recorded as "not stated".
- **Returns.** No reported return, Sharpe, or cost figure is attributed to any ASA expression.

## 9. Consistency notes for Architecture

These are recorded without changing any Architect value:
1. **A16:** its raw standalone burden is B3, but its ruled HARD dependency X01 is B4. By the effective-burden convention used for A17 and X02a, its standalone value would be B4. The matrix keeps B3 verbatim, and its front is unaffected (it has no credible use).
2. **A12:** reuse confidence HIGH on an "all" mapping, where §3.3 would give MEDIUM. The count is unaffected.
3. **X02b / X03 / X04:** architecture confidence not stated.
4. **P13:** "multi-underlying coordination" is treated as intrinsic to P13, not as a separate primitive.
5. **Primitive roles** were assigned by the selection worker from the Architect's descriptions. For example, A01 and A16 are DATA and A15 is ANALYTIC. They are open to Architect correction.

## 10. Decisions still required (Founder)

1. **Official weights** for the matrix. Decide whether E2 (confidence) and/or credible-use breadth are included (§7).
2. **One common pool, or separate role lanes** (§4).
3. **How many primitives or bundles advance, and whether the unit is a primitive or a bundle** (§6). This is a product threshold.
4. **Approval of the evidence-confidence proposal** (§2).

After those, recomputing is mechanical. Advancing items would go to separately activated research (full-text evidence and costs for their credible families) and to Architect design review.
