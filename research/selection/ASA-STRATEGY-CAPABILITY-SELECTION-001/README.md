# ASA-STRATEGY-CAPABILITY-SELECTION-001

These are comparison artifacts for ASA's first capability-primitive selection exercise, which follows ASA-RES-SPRINT-001.

**Status: Founder consideration set produced.** It is not a recommendation to implement any capability, and no implementation is authorized. The Founder's decision about what, if anything, to pursue is to be recorded separately from these files, so that research evidence, architectural classification, and the product decision stay distinguishable.

## Files

| File | Content |
|---|---|
| [`primitive-comparison-report.md`](primitive-comparison-report.md) | Consideration set, method as applied, governing lane fronts, non-advancing candidates with reasons, sensitivity, and findings |
| [`primitive-comparison-matrix.yaml`](primitive-comparison-matrix.yaml) | Machine-readable matrix covering 37 capabilities: architecture fields (as supplied and reconciled), evidence utilities, official score components, lane fronts, advancement, sensitivity, and bundles |

## Governing method

ASA-ARCH-STRATEGY-SELECTION-RESOLUTION-001, **adopted by the Founder** (2026-09-27). The steps are:
1. role-stratified Pareto analysis;
2. official weighted scoring (35% direction-adjusted evidence utility, 15% independent evidence-cluster breadth, 25% demonstrated reuse, 25% implementation burden);
3. dependency-aware bundles with marginal costing;
4. sensitivity classification.

## Inputs and ownership

| Input | Owner | Location |
|---|---|---|
| Evidence corpus | ROLE-RESEARCH | `research/sprints/ASA-RES-SPRINT-001/`, `research/strategies/`, `research/sources/`, `research/catalog.yaml` |
| ASA-FOUNDER-STRATEGY-SELECTION-DIRECTIVES-001 | Founder | supplied in session 2026-09-27; not yet on `main` |
| ASA-ARCH-STRATEGY-SELECTION-THRESHOLDS-001 and clarifications | ROLE-ARCH | supplied in session 2026-09-27; not yet on `main` |
| ASA-ARCH-STRATEGY-SELECTION-RESOLUTION-001 (Founder-adopted) | ROLE-ARCH / Founder | supplied in session 2026-09-27; review on PR #499; not yet on `main` |

The source packets are referenced by ID, not copied. The values the matrix uses are recorded field by field, with their sources noted.

## Boundaries

- No external return, cost, or risk figure is attributed to any ASA expression.
- These files do not modify the research corpus or the Architect's classifications.
