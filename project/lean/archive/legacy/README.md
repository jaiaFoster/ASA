# Legacy POS Historical Records Archive

This directory contains pre-Lean POS historical records, archived in LEAN-POS-09 (CUTOVER-04).

## Status: noncanonical

**These records must not be used for current work tracking.**
They are retained as immutable historical artifacts only.

No file content was rewritten during archival. `git mv` preserved bytes exactly.
Git history preserves the original locations (`project/work/`, `project/assignments/`, etc.)
and all content at every prior commit.

## Contents

| Directory | Original path | Record type |
|---|---|---|
| `work/` | `project/work/` | Work items (ASA2-WORK-*) |
| `assignments/` | `project/assignments/` | Assignments (ASA2-ASG-*) |
| `results/` | `project/results/` | Worker results (ASA2-RESULT-*) |
| `decisions/` | `project/decisions/` | Decisions (ASA2-DECISION-*) |
| `reviews/` | `project/reviews/` | Reviews (ASA2-REVIEW-*) |
| `evidence/` | `project/evidence/` | Evidence (ASA2-EVIDENCE-*) |
| `risks/` | `project/risks/` | Risk records (ASA2-RISK-*) |
| `BOOTSTRAP_STATUS.yaml` | `project/BOOTSTRAP_STATUS.yaml` | Legacy bootstrap state |

## Operational truth

- **Current project state:** [`project/lean/state/project-state.yaml`](../state/project-state.yaml)
- **Operational record:** GitHub issues, PRs, reviews, CI checks, and merges
- **Git history:** complete record of all prior file locations and content
