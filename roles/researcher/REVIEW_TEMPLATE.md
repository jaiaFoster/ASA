# Research PR Self-Review

Post this on every research PR before any delegated merge (GOV-AMD-017 Part B item 3).

| Check | Result |
|---|---|
| Sprint / ticket | `<SPRINT-ID>` / `<TICKET>` (enumerated: yes/no) |
| Changed paths | all under the sprint's `allowed_paths` in `research/`; `research/README.md` untouched |
| Risk class | R0 / R1 (anything higher is not delegable) |
| Evidence classes | every material claim is REPORTED / DERIVED / INFERENCE / UNKNOWN with a recoverable source |
| Contradictions | failed replications and contradictory evidence recorded, or explicitly "none found" |
| Invented rules | none; missing parameters are UNKNOWN |
| Status semantics | status reflects evidence only; no priority, selection, or validation claim |
| History | prior conclusions preserved on any status change |
| `research_library.py` | OK |
| Required gates | CI, POS Validation, library validation, governance integrity, scope check: all pass |
| Blocking issues | none / listed |

Outcome: **eligible for delegated merge** / **Founder merge required** (state why).
