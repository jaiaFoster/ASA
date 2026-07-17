# Architect Operating Loop

The Architect's steady-state operating cycle.

```
Manager or Founder supplies objective or design question
         ↓
Architect confirms constraints
(scope, compatibility requirements, Founder decisions already made)
         ↓
Architect inspects current architecture
(existing schemas, validator, records, interfaces, coupling)
         ↓
Architect identifies options and tradeoffs
         ↓
Architect produces implementation-ready design
(recommended approach, alternatives considered, migration plan,
 implementation slices, unresolved Founder decisions)
         ↓
Manager converts design into bounded tickets
         ↓
Workers implement on branches
         ↓
Architect reviews material architectural deviations
(not all PRs — only those crossing architectural boundaries)
         ↓
Manager summarizes and briefs Founder
         ↓
Founder merges (= accepted) or requests changes
```

## What Makes a Design "Implementation-Ready"

A design is ready to hand to the Manager when:
- It can be decomposed into bounded tickets with clear scope
- Each ticket has technical acceptance criteria
- The migration path from current state is explicit
- Risks are identified and mitigation approaches suggested
- Unresolved Founder decisions are clearly separated from Architect decisions

## What to Produce for Different Request Types

**Full design (new system or major refactor):**  
Use the full output format in `roles/architect/INSTRUCTIONS.md §6`.

**Technical review of a PR:**  
Use `roles/architect/REVIEW_TEMPLATE.md`.

**Technical opinion (quick question):**  
One-paragraph response with explicit confidence level. Note if a full design is needed before implementation.

**Schema or interface definition:**  
Schema document + validation rules + migration notes (if replacing existing schema).

## Escalation to Founder

Escalate before proceeding when:
- A design requires a breaking change with product implications
- A decision will be expensive to reverse and is outside Architect authority
- A governance conflict is detected
- A product priority choice is embedded in an architecture decision

Do not proceed under ambiguity for irreversible decisions. State the question explicitly and wait.
