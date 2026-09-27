# Research PR Self-Review — ASA-RES-STRATEGY-QUALIFICATION-002

Recorded per `roles/researcher/REVIEW_TEMPLATE.md` (GOV-AMD-017 Part B item 3). Reviewed 2026-09-27 against branch `claude/asa-options-strategy-research-q9tf9p`, based on `main` @ 63f824c.

| Check | Result |
|---|---|
| Sprint / ticket | ASA-RES-STRATEGY-QUALIFICATION-002, a single assignment supplied to the Researcher (not a sprint-definition file). Enumerated: no activation file exists. |
| Changed paths | Only under `research/sprints/ASA-RES-STRATEGY-QUALIFICATION-002/` and `research/sources/`. Only `.md` and `.yaml` files. `research/README.md`, `research/catalog.yaml`, catalog `status_semantics` and the strategy dossiers are untouched. |
| Delegation live | **No.** There is no `docs/sprints/` activation file for this assignment, so there is no Founder activation merge. This follows the Founder's standing preflight requirement. |
| Untrusted content | Source PDFs and web pages were treated as data. A web-search snippet describing a BXMD volatility input could not be traced to a Cboe BXMD document and was **not** used; the BXMD spec records this. No embedded instructions were encountered or followed. |
| Risk class | R0/R1: research documents and data only. No code, governance, role, contract or sprint-definition change. |
| Evidence classes | Every source claim is REPORTED, DERIVED, INFERENCE or UNKNOWN. New source records carry `verification_depth: full_text_reviewed` only where the full text was actually read. Existing records keep their original fields and gain an appended `qualification_002_verification` block. |
| Contradictions | Recorded per lane and per specification. Examples:<br>• GXZ vs ALX era conflict;<br>• the GXZ working paper vs published abstract (3.00% vs 3.34%);<br>• PUT's post-launch Sharpe vs the S&P 500;<br>• Israelov-Nielsen's uncompensated timing risk;<br>• MPP's internal skew-definition wording;<br>• Cao-Han quintile vs decile cost results. |
| Invented rules | None. Missing rules are UNKNOWN or AMBIGUOUS_SELECTION, and each DERIVED interpretation states its basis:<br>• zero-delta weight equivalence;<br>• strict "below";<br>• Ln(PRICE) formation date;<br>• calendar-day DTE for ALX. |
| Status semantics | The qualification states are the assignment's six. No lane ranking, build order or implementation recommendation is made. Catalog lifecycle statuses are unchanged. |
| History | Prior source-record content is preserved. One correction was made during drafting, before any commit: the January 2013 working paper is by Xing and Zhang only, and is recorded as the precursor of the published Gao-Xing-Zhang article. |
| Adversarial self-check | Findings that changed the output:<br>• The Cao-Han alternate was first drafted as RESEARCH_REJECT. Footnote 18 shows the decile variant survives a 50% effective spread, so it was corrected to INSUFFICIENT_EVIDENCE.<br>• Heston reversal and composite figures were mis-transcribed in the lane-6 draft and corrected against Table 13.<br>• The Carr-Wu eq. (49) integrand was garbled in extraction; the registry records the form consistent with the source's own eq. (47), labelled DERIVED.<br>• The MPP bid filter was verified as "greater than 0.1" in the source footnote. |
| Mechanical checks | Every DF-, gate, specification and source ID referenced across the sprint files resolves to a registry entry or source record, and every relative link resolves. The specification, qualification-matrix and capability-map sets are identical (14 each). |
| `research_library.py` | `OK: research library is consistent` |
| Required gates (local) | See the PR description for the run results of `pytest tests/pos`, `pre_push_check.py`, `check_integrity.py`, `check_entrypoints.py` and CURRENT_STATE regeneration. Remote CI must also pass. |
| Blocking issues | No activation file (above). |

Outcome: **Founder merge required.** The work is within ROLE-RESEARCH scope, but there is no Founder-merged activation, so the delegated-merge conditions are not met. No `CLOSURE.md` is written.
