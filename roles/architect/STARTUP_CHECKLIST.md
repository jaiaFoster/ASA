# Architect Startup Checklist

Run this when the Architect is first instantiated or rehydrated.

## Step 1 — Read Role Instructions

- [ ] Read `roles/architect/INSTRUCTIONS.md`
- [ ] Read `roles/shared/AUTHORITY_BOUNDARIES.md`
- [ ] Read `roles/shared/RISK_SCALED_PROCESS.md`
- [ ] Read `roles/shared/GITHUB_ACCEPTANCE_MODEL.md`

## Step 2 — Read Source Specifications

- [ ] Read `governance/frozen/ARCH-SPEC-v0.2.md` — your role specification
- [ ] Read `governance/frozen/RISK-001` — risk classification standard
- [ ] Check `governance/amendments/GOV-AMD-001.md` amendment statuses (013 Accepted; 001–012 Proposed)
- [ ] Note: PM-SPEC and ARCH-SPEC are Draft v0.2, not yet formally accepted

## Step 3 — Inspect Current Repository State

- [ ] Run `git log --oneline -5` — confirm current commit
- [ ] Run `git status --short` — confirm clean working tree
- [ ] List `project/schemas/` — current record schemas
- [ ] List `project/work/`, `project/assignments/`, etc. — current records

## Step 4 — Inspect Current POS Implementation

Read and analyze:
- [ ] `tools/pos/schemas.py` — schema registry, constants
- [ ] `tools/pos/validate.py` — validation logic
- [ ] `tools/pos/generate.py` — generation logic
- [ ] `tools/pos/transitions.py` — state transition maps
- [ ] `project/schemas/work-item.schema.yaml` and sibling schemas

Identify:
- [ ] Which record types are currently mandatory for every work item?
- [ ] What information does the POS duplicate from GitHub?
- [ ] What state is maintained manually vs. generated?
- [ ] What validation checks are structural vs. lifecycle vs. authority?
- [ ] Which records exist in the bootstrap prototype that may not be needed for routine work?

## Step 5 — Assess Current Problems

Note your findings on:
- [ ] Duplicated state (POS records that mirror GitHub data)
- [ ] Manual bookkeeping (things a person must type that could be inferred)
- [ ] Mandatory ceremony (required records regardless of risk class)
- [ ] Assumptions in the current design that should be made explicit or replaced

## Step 6 — Read the First Assignment

- [ ] Read `roles/architect/FIRST_ASSIGNMENT.md` (ARCH-POS-001)
- [ ] Confirm constraints and scope with Manager before proceeding
- [ ] Read `roles/architect/CONTEXT_PACKET.md` for project context

## Step 7 — Produce a Design Plan

Before implementing anything:
- [ ] State the problem clearly
- [ ] Identify what questions must be answered before design can proceed
- [ ] Draft the design questions the Founder must decide vs. those the Architect decides
- [ ] Confirm with Manager that the plan scope is appropriate

**Produce a design plan, not implementation. The Manager will convert the design into bounded tickets.**
