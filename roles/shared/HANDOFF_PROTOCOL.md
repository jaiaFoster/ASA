# Handoff Protocol

Concise information contracts for role-to-role transfers.

## Manager → Architect

Use when Architect input is needed on a design question or review.

```
**Objective:** [what we're trying to accomplish]
**Current state:** [what exists now, with file/PR references]
**Constraints:** [time, compatibility, Founder decisions already made]
**Decisions needed:** [specific questions requiring Architect judgment]
**Required output:** [design doc / schema / review / recommendation]
**Return to:** Manager
```

## Manager → Worker

Use when issuing a bounded implementation assignment.

```
**Objective:** [one concrete outcome]
**Scope — allowed:** [paths, files, systems the worker may touch]
**Scope — forbidden:** [explicit exclusions]
**Base commit:** [SHA at assignment time]
**Verification:** [commands to run; expected pass condition]
**Expected result:** [what the worker submits when done]
**Escalation:** [conditions that require stopping and notifying Manager]
**Risk class:** [R0–R5]
```

## Worker → Manager

Use when submitting a completed assignment.

```
**Assignment:** [ID or title]
**PR:** [GitHub PR link]
**Summary:** [what was done, one paragraph max]
**Files changed:** [key paths]
**Verification:** [commands run and output summary]
**Tests:** [pass/fail count]
**Limitations:** [known gaps, deferred items, risks]
**Scope deviations:** [anything outside the original scope, if any]
```

## Architect → Manager

Use when delivering a design or review result.

```
**Assignment:** [ID or title]
**Recommendation:** [what to do]
**Architecture:** [key design decisions]
**Implementation slices:** [ordered list of tickets]
**Risks:** [what could go wrong]
**Unresolved decisions:** [questions requiring Founder or Manager input]
```

## Manager → Founder

Use when escalating a decision or summarizing a result for merge.

```
**What changed:** [one sentence]
**PR:** [GitHub PR link]
**Verification:** [tests pass / validator pass]
**Recommendation:** [merge / request changes / defer]
**Decision required:** [specific question, if any]
**Consequence of deferral:** [what blocks if Founder waits]
```

## Notes

- Handoffs should be brief. If a handoff is longer than one page, the scope is probably too large.
- Link to canonical files rather than copying content.
- Worker result packets do not need to repeat the assignment spec.
- Manager summaries for the Founder should separate: facts / recommendations / required decisions.
