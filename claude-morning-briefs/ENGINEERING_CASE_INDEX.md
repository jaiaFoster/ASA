# Morning Brief Engineering Case Index

**Status:** Derived crosswalk only — not canonical backlog or project status.

This index lets the Morning Brief Engineer consolidate repeated user-visible
symptoms across days without creating one issue per brief.

Canonical state remains in GitHub issues/PRs, sprint artifacts, architecture
records, and the POS.

| Case | User-visible symptom | First seen | Latest seen | Canonical owner / reference | Engineering disposition | Recurrence |
|---|---|---|---|---|---|---|
| BRIEF-DISCOVERY-001 | Brief calls registered strategies unrecognized/experimental and interprets zero PASS/WATCH without canonical typed health | 2026-10-08 | 2026-11-12 | [#540](https://github.com/jaiaFoster/ASA/issues/540), canonical /api/v1/capabilities | OPEN — brief projection must use canonical strategy discovery and typed evaluation state; verify against current code before implementation | open |
| BRIEF-READINESS-001 | Screening PASS/WATCH can coexist with unavailable trade proposals; user-facing narrative needs distinct screening validity versus execution readiness | 2026-10-20 | 2026-11-12 | [#541](https://github.com/jaiaFoster/ASA/issues/541), [#437](https://github.com/jaiaFoster/ASA/issues/437) (closed) | OPEN — preserve fail-closed trade-proposal and exact-leg boundaries; investigate current projection against closed earnings fix | open |
| BRIEF-FRESHNESS-001 | Age-based freshness may disagree with market-session or row freshness; stale evidence can look fresh | 2026-10-27 | 2026-11-12 | [#436](https://github.com/jaiaFoster/ASA/issues/436) (closed), [#540](https://github.com/jaiaFoster/ASA/issues/540) | RECURRENCE NEEDS VERIFICATION — distinguish legitimate stale underlying observation from false-fresh presentation before reopening | open |

## Maintenance rules

- One recurring root problem should normally have one row.
- Link the row to the existing canonical issue/ticket/PR instead of duplicating it.
- Update `Latest seen` when a later brief provides new evidence.
- Mark recurrence closed only after the relevant acceptance path proves the
  symptom no longer occurs; issue closure alone is not enough when the brief
  provides contrary production evidence.
- Brief prose is evidence of user experience, not authority for strategy,
  architecture, or financial semantics.

## Intake progress (2026-11-13)

The 26 extracted dated briefs (2026-10-08 through 2026-11-12) are available on `main`. This first-pass crosswalk consolidates recurring observations against existing canonical issues. It is **not** a completed per-observation reconciliation or implementation review. The archive remains `processed: false` in the cursor until all observations receive durable dispositions. Do not interpret this index as acceptance or close any issue based solely on brief prose.
