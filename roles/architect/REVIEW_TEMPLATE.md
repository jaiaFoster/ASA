# Architect Review Template

Use this for architectural review of PRs or implementation proposals. Not required for all PRs — see trigger rules in `roles/architect/INSTRUCTIONS.md §3`.

---

## Review: [Work Item or PR ID]

**PR:** [GitHub link]  
**Branch:** [branch-name]  
**Reviewer:** ASA System Architect (ROLE-ARCH)  
**Scope of review:** [What was reviewed — be explicit about what was NOT reviewed]

---

## Architectural Consistency

Does this change conform to existing architectural decisions and contracts?

- [ ] System boundaries respected
- [ ] Interfaces match existing contracts
- [ ] Canonical data ownership unchanged (or migration plan exists)
- [ ] No new implicit coupling introduced

**Notes:** [findings or "consistent"]

---

## Canonical-State Integrity

Does this change maintain clean separation between canonical and derived state?

- [ ] Canonical state is stored in one place
- [ ] Generated views are not treated as canonical
- [ ] GitHub data is referenced, not duplicated
- [ ] No competing sources of truth introduced

**Notes:** [findings or "intact"]

---

## Unnecessary Complexity

Does this change introduce complexity without clear present value?

- [ ] No premature abstractions
- [ ] No speculative platform features
- [ ] No duplication of logic already present
- [ ] Complexity is proportional to the problem solved

**Notes:** [findings or "proportionate"]

---

## Migration Risk

If this change modifies existing schemas, interfaces, or records:

- [ ] Migration path is defined
- [ ] Existing records remain valid or migration is provided
- [ ] Backwards compatibility is addressed or breaking change is explicit

**Notes:** [findings or "no migration needed"]

---

## Security Boundaries

- [ ] No new credentials or secrets in scope
- [ ] No new untrusted inputs without validation
- [ ] No implicit trust grants

**Notes:** [findings or "no security surface"]

---

## Testability

- [ ] New behavior is testable with the existing test infrastructure
- [ ] Tests cover the acceptance criteria
- [ ] Failure modes are tested, not just the happy path

**Notes:** [findings or "adequately tested"]

---

## Reversibility

- [ ] This change can be reverted without data loss, or irreversibility is explicit and accepted
- [ ] Irreversible decisions have been escalated to Founder if required

**Notes:** [findings or "reversible"]

---

## Implementation Deviations

Did the implementation deviate from the design?

[ ] No material deviations  
[ ] Deviations noted below — [describe]

---

## Summary

**Technical conformance:** [Pass / Fail / Pass with notes]  
**Architecture impact:** [None / Minor / Material — describe if material]  
**Recommendation:** [Merge ready / Changes needed — specify what]

This review covers technical conformance only. It does not constitute Founder acceptance, merge authorization, or deployment authorization.
