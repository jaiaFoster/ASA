# ASA-RES-SPRINT-001 — Options Strategy Landscape and Evidence Framework

This is the working record for the sprint and the handoff for any replacement Researcher. It is not the closure record.

## Authority state (verified 2026-09-26 on `main` @ a4f58b7)

| Check | Result |
|---|---|
| GOV-AMD-017 on `main`, Founder-merged | yes (#497, a4f58b7) |
| `docs/sprints/ASA-RES-SPRINT-001.yaml` on `main` | **absent** |
| Founder activation merge | **not found** |
| `research/sprints/ASA-RES-SPRINT-001/CLOSURE.md` on `main` | absent |

The sprint definition reached the Researcher through the session request, but no Founder-merged activation file exists. Under `roles/researcher/STARTUP_CHECKLIST.md` §4, **no delegated merge authority exists**.

The research was carried out as an assignment within ROLE-RESEARCH's DECIDE authority (research method, evidence characterization, provenance, taxonomy, status). It is submitted for a **Founder merge**, not a delegated merge.

`CLOSURE.md` is deliberately not written. The closure record requires the activating Founder merge commit, which does not exist. Writing one would also end a delegation that never started.

## Deliverables

| Ticket | Artifact | State |
|---|---|---|
| RES-001A | [`RES-001A-landscape.md`](RES-001A-landscape.md), plus 92 source records in `research/sources/` | complete |
| RES-001B | [`RES-001B-taxonomy.md`](RES-001B-taxonomy.md) | complete |
| RES-001C | 19 family dossiers `research/strategies/ASA-RSCH-FAM-*-001.md`; [`RES-001C-evidence-dataset.yaml`](RES-001C-evidence-dataset.yaml); extensions to SPY-PCS and Skew Momentum | complete |
| RES-001D | [`RES-001D-filtering-method.md`](RES-001D-filtering-method.md), [`RES-001D-dimension-dictionary.yaml`](RES-001D-dimension-dictionary.yaml) | complete |
| Self-review | [`SELF-REVIEW.md`](SELF-REVIEW.md) | complete |

## How to continue (replacement Researcher)

1. Rehydrate per `roles/researcher/STARTUP_CHECKLIST.md`.
2. If the Founder later activates the sprint, write `CLOSURE.md` citing the activating merge and every delegated merge.
3. The next research need is recorded per family in `research/catalog.yaml` (`next_research_need`). The dominant gap is full-text recovery: most sources are verified at `bibliographic_and_abstract` depth, so sample periods, cost treatments, and exact rules are often UNKNOWN.
4. Do not treat any coding in `RES-001C-evidence-dataset.yaml` as a ranking. RES-001D defines how a downstream authority may use it.
