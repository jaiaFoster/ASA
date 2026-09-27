# ASA-STRATEGY-CAPABILITY-SELECTION-001

These are comparison artifacts for ASA's first capability-primitive selection exercise, which follows ASA-RES-SPRINT-001.

**Status: decision support. No primitive, family, or strategy is selected here.** The Founder-owned selection decision, when made, is to be recorded separately from these files, so that research evidence, architectural classification, and the product decision stay distinguishable.

## Files

| File | Content |
|---|---|
| [`primitive-comparison-matrix.yaml`](primitive-comparison-matrix.yaml) | Machine-readable matrix: 37 capabilities with architecture fields (as supplied), evidence fields (derived), and comparison fields (derived), plus family evidence profiles, Pareto fronts, and bundle marginal costs |
| [`primitive-comparison-report.md`](primitive-comparison-report.md) | Human-readable comparison with every conclusion labelled [E] evidence, [A] architecture, or [W] weighting |

## Inputs and ownership

| Input | Owner | Location |
|---|---|---|
| Evidence corpus | ROLE-RESEARCH | `research/sprints/ASA-RES-SPRINT-001/`, `research/strategies/`, `research/sources/`, `research/catalog.yaml` |
| ASA-FOUNDER-STRATEGY-SELECTION-DIRECTIVES-001 | Founder | supplied in session 2026-09-27; **not yet on `main`** |
| ASA-ARCH-STRATEGY-SELECTION-THRESHOLDS-001 and clarifications | ROLE-ARCH | supplied in session 2026-09-27; **not yet on `main`** |

The Founder directive and the Architect packet are referenced by ID, not copied. The architecture values the matrix uses are recorded field by field, with their source noted, so that the matrix is reproducible. Committing the two source packets to their owners' locations would make the provenance fully durable.

## Boundaries

- The weighted values are illustrative. Official weights are Founder-owned and have not been supplied.
- The evidence-confidence thresholds are a Research proposal pending Founder approval.
- No reported return, cost, or risk figure from external research is attributed to any ASA expression.
- These files do not modify the research corpus or the Architect's classifications.
