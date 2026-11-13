# Morning Brief Worker Ownership — Reconciliation (2026-11-13)

This document separates *intake*, *engineering review*, and *implementation*.
It does not change ASA governance or confer new standing authority.

## Single-owner responsibilities

| Actor | Owns | Must not do |
| --- | --- | --- |
| GitHub Actions `morning-brief-engineer.yml` | Scan dated briefs; create idempotent source-intake GitHub issues (up to three per run) | Interpret briefs as confirmed defects; edit code; advance engineering cursor; invoke paid AI APIs |
| Existing ChatGPT Morning Brief Engineer automation | Review source-intake tickets; reconcile symptoms with canonical code/issues; create/update engineering issues; record evidence/dispositions | Claim a local checkout/test execution it did not perform; auto-merge; treat intake as reviewed |
| Desktop Codex or Claude Code worker | Claim one *explicitly authorized* engineering issue; inspect code; implement bounded fix; run regression tests; open PR | Independently re-ingest entire brief backlog; duplicate canonical issues; self-authorize architectural changes; auto-merge/deploy |
| GitHub CI | Run checks on PRs | Decide product or architectural scope |

## Shared queue and handoff

1. Intake issue titles start `BRIEF INTAKE:`. They are **not** engineering defect tickets.
2. ChatGPT review checks for an existing canonical issue first. It may create
   a new engineering issue only when evidence and deduplication warrant it.
   Link all canonical issues in the source-intake ticket and record dispositions.
3. Review is complete only when every meaningful observation is disposed as
   existing/new issue, expected behavior, stale interpretation, insufficient
   evidence, or architecture-routed. Then and only then propose a cursor
   update and close the intake ticket after durable record is accepted.
4. Desktop worker selects only a ready, authorized canonical engineering
   issue, explicitly claims it by comment/assignment, and checks for any
   existing implementation PR. One issue, one active implementation owner.
5. A failing test, ambiguous architecture, or Founder-only decision means
   stop and record the blocker in the issue. Do not silently bypass checks.
6. GitHub Actions and ChatGPT must not both create source-intake tickets.
   The ChatGPT automation consumes them; the workflow produces them.

## Cursor semantics

- `ENGINEERING_REVIEW_CURSOR.yaml` represents **engineering-reviewed**
  source material, not discovery/enqueue state.
- An issue hash marker represents **enqueued** material, not review completion.
- The existing 26-brief historical backlog stays unprocessed until actual
  per-brief reconciliation is complete.
- PR #600's three-case crosswalk is partial, not an all-brief disposition.
- No worker may mark a brief complete solely because it was copied from the ZIP.

## Activation and safety

- This coordination document and no-API workflow require an approved PR merge.
- The older ChatGPT scheduled task must be updated to consume intake tickets
  and hand off ready engineering issues, not duplicate source intake.
- The desktop worker may resume **bounded authorized issue work** after the
  no-API workflow is merged and the old API-based workflow is removed from
  `main`; it need not wait for all 26 briefs to be reviewed.
- No agent is granted standing permission to merge, deploy, use production
  credentials, or override Founder/Architect approval.
