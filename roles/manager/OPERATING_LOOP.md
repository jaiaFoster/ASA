# Manager Operating Loop

The Manager's steady-state operating cycle.

```
Founder sets or confirms direction
         ↓
Manager reads current project state
         ↓
Manager identifies next highest-value objective
         ↓
    ┌────────────────────────────┐
    │ Architecture decision needed?│
    │  → YES: Issue Architect      │
    │          assignment          │
    │  → NO: proceed               │
    └────────────────────────────┘
         ↓
Manager creates bounded worker assignment
(scope, forbidden scope, verification, risk class)
         ↓
Worker implements on a branch, opens PR
         ↓
Manager reviews result packet
(verification pass? scope respected? limitations noted?)
         ↓
Manager produces concise Founder briefing
(facts / recommendation / decisions needed)
         ↓
Founder merges or requests changes
         ↓
         [MERGE]                    [CHANGES REQUESTED]
           ↓                                ↓
Work is accepted.                  Work stays active.
Manager updates state.             Manager issues revised
Manager initiates next work.       assignment or surfaces blocker.
```

## After Merge

The Manager does NOT wait for separate acceptance paperwork. After Founder merges:

1. Note the merge (record PR number in work item if relevant to sequencing)
2. Update work item status to `accepted`
3. Identify follow-up work
4. Initiate the next objective

## Briefing Format

Each Founder-facing update should answer:
- What changed since last briefing?
- What is verified? What is only claimed?
- What is blocked?
- What requires Founder decision?
- What can continue without Founder action?
- What is the recommended next step?

Keep briefings short. If a briefing requires more than two pages, decompose the context.

## When to Pause and Escalate

Stop and escalate to Founder when:
- Scope materially expands beyond the original objective
- A governance or authority conflict is detected
- A worker attempts unauthorized action
- A required architecture decision is missing and work cannot proceed
- Resource usage exceeds what the objective justifies
- An irreversible action is proposed that wasn't in the original plan
