# Claude Morning Briefs

This directory is the durable archive of Founder-facing morning briefs.

The briefs are valuable **user/production observations**. They are not canonical
financial or system truth and must not override repository contracts merely
because a brief says something happened.

## Daily intake

The daily brief task should commit each completed brief into this directory.

Preferred format for new briefs:

```
claude-morning-briefs/YYYY-MM-DD.md
```

If a run produces more than one brief, use a stable suffix such as
`YYYY-MM-DD-preopen.md` or `YYYY-MM-DD-postopen.md`.

Do not overwrite historical briefs.

The existing backlog archive
`asa_briefs_backlog_2026-10-08_to_2026-11-12.zip` is the initial historical
intake source. The engineering worker may unpack it locally for review but
should not commit duplicate extracted copies solely for inspection.

## Automation (current)

`.github/workflows/morning-brief-engineer.yml` (08:00 America/Phoenix) enqueues intake issues;
Claude Routine A (09:00) triages them; Claude Routine B (10:00) implements `engineering-ready`
issues. Ownership, state model, and recovery: `WORKER_OWNERSHIP.md`. Routine instructions:
`routines/`. Setup: `ROUTINE_SETUP.md`. The daily producer task may write to `briefs/`; discovery
scans both roots, but prefer `claude-morning-briefs/YYYY-MM-DD.md`.

## Engineering follow-through (manual activation, legacy)

After a new brief is committed, invoke the reusable bounded worker assignment:

`project/workers/MORNING-BRIEF-ENGINEER-v1.md`

Minimal activation instruction:

> Rehydrate from current main. Read
> `project/workers/MORNING-BRIEF-ENGINEER-v1.md`, then process every
> unreviewed item under `claude-morning-briefs/`. Reconcile observations
> against canonical repo state, fix bounded defects, and use GOV-AMD-018 to
> hydrate ROLE-ARCH for architecture-sized/new-feature findings. Implement the
> Architect-approved direction when it remains inside current authority.
> Update the engineering review cursor and case index.

## Bookkeeping artifacts

- `ENGINEERING_REVIEW_CURSOR.yaml` — intake cursor only; not project status.
- `ENGINEERING_CASE_INDEX.md` — derived crosswalk from recurring user symptoms
  to canonical issues/tickets/PRs; never a replacement for the canonical
  backlog/POS.

## Principles

- Deduplicate recurring evidence into one engineering case.
- Preserve exact brief dates as production evidence.
- Fix root causes, not brief wording.
- Never infer that zero PASS means a defect without proving evaluation
  completeness.
- Never change strategy semantics merely to make the brief look better.
- If the brief exposes a larger missing capability, consult Architect and then
  build the approved solution rather than only filing a vague future ticket.
