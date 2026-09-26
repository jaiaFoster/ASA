# Research PR Self-Review — ASA-RES-SPRINT-001 (RES-001A–D)

Recorded per `roles/researcher/REVIEW_TEMPLATE.md` (GOV-AMD-017 Part B item 3). Reviewed 2026-09-26 against branch `claude/asa-options-strategy-research-q9tf9p`, which is based on `main` @ a4f58b7.

| Check | Result |
|---|---|
| Sprint / ticket | `ASA-RES-SPRINT-001` / RES-001A, RES-001B, RES-001C, RES-001D, one commit per ticket. Enumerated in the sprint definition supplied to the Researcher: **yes**. |
| Changed paths | All under `research/sources/`, `research/strategies/`, `research/catalog.yaml`, `research/sprints/ASA-RES-SPRINT-001/`. Only `.md` and `.yaml` files. `research/README.md` untouched. Catalog `status_semantics` untouched. Verified with `git diff --name-only origin/main...HEAD`. |
| Delegation live | **No.** `docs/sprints/ASA-RES-SPRINT-001.yaml` does not exist on `main`, so there is no Founder activation merge. `research_delegation.py` cannot evaluate a missing file. |
| Untrusted content | The VILKOV-0DTE repository README directs readers to KNOWN-ISSUES.md; this was treated as provenance only. OpenAlex returned an unrelated abstract for SIMON-CAMPASANO-2014, recorded as a data-quality finding with no claims taken. No embedded instructions were followed. |
| Risk class | R0/R1: research documents and data only. No code, governance, role, sprint-definition, or contract change. |
| Evidence classes | Every source claim carries REPORTED / DERIVED / INFERENCE / UNKNOWN. Each source records `verification_depth` (bibliographic_only, bibliographic_and_abstract, search-summary, full_text, primary page/repository). No claim is asserted beyond its verified depth. |
| Contradictions | Recorded per family (Contradictory / Failed replication / Post-publication sections), and summarized in RES-001A §5. Families with none found say so explicitly with a coverage reference. |
| Invented rules | None. Missing parameters are UNKNOWN. Family specifications quote source rules only. |
| Status semantics | Statuses describe evidence only. No QUALIFIED or REJECTED status was assigned (qualification needs full-text DEEP_RESEARCH). There are 6 INSUFFICIENT_EVIDENCE and 1 DISCOVERED outcomes, each with a stated basis. |
| History | SPY-PCS and Skew Momentum: prior conclusions preserved, extensions appended, statuses unchanged (TRIAGE), superseded lines marked rather than deleted. OA-SPY-PCS-2021: inherited fields preserved; re-verification appended. |
| Adversarial self-check | One citation misuse was found and corrected before submission. BAKSHI-KAPADIA-2003 had been cited as support for "far-OTM puts are most expensive"; its abstract reports smaller delta-hedged underperformance away from the money, so it is now recorded as contrary nuance in FAM-DEFINED-RISK and SPY-PCS. Catalog-to-dossier provenance and all cited source IDs were cross-checked mechanically (0 problems). |
| Independence rule | Evidence codings (RES-001C `evidence.*`) were assigned before, and independently of, the ASA capability mapping. Capability mapping appears after the assessment in every dossier. |
| Selection boundary | No weights, scores, rankings, winners, finalists, or implementation recommendations (RES-001D §10). Capability reuse counts (RES-001B §4) are explicitly labelled non-recommendations. |
| `research_library.py` | `OK: research library is consistent` |
| Required gates (local) | `pytest tests/pos` 699 passed / 1 skipped. Lean validator PASS. Frozen governance integrity OK. CURRENT_STATE.md regeneration unchanged. Entrypoint invariants OK. `pre_push_check.py` 5/5 PASS. Remote CI must also pass on the PR. |
| Blocking issues | Delegation not activated (above). |

Outcome: **Founder merge required.** The work is in scope and passes local gates, but no Founder-merged activation of ASA-RES-SPRINT-001 exists on `main`, so the Part B delegated-merge conditions are not met. For the same reason no `CLOSURE.md` is written. See `README.md` in this directory.
