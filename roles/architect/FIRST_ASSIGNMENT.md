# ARCH-POS-001 — Design Lean POS v1

**Assignment ID:** ARCH-POS-001  
**Issued by:** Manager (on behalf of Founder)  
**Risk class:** R2 (Technical Change — POS infrastructure redesign)  
**Output:** Design document at `docs/lean-pos-v1-design.md` (or equivalent path agreed with Manager)

---

## Objective

Design a simplified Git-backed Project Operating System (POS) that supports ASA 2's operating model:
- Founder sets direction and merges PRs
- Manager coordinates work
- Architect owns system design
- Workers implement bounded assignments
- GitHub PR workflow is the acceptance mechanism

The design must reduce manual documentation while preserving:
- Clear authority (who may do what)
- Bounded work (explicit scope and forbidden scope)
- Deterministic validation (same input → same result)
- Traceability (enough state to audit decisions after the fact)
- Risk-scaled process (more rigor for higher-risk work)
- Safe escalation for high-risk work

---

## Context

The current POS prototype requires 7 records for a complete lifecycle:
1. Work item
2. Risk record
3. Assignment
4. Worker result
5. Review
6. Evidence
7. Decision

The Founder has directed that this is too heavy for ordinary R1–R2 work. GitHub already stores: PR state, merge identity, who merged and when, diff, CI runs, review comments. The POS should reference this data, not duplicate it.

**The Architect must design from scratch, treating the current prototype as a useful reference implementation, not the target.**

---

## Required Design Questions

Answer all of the following:

### 1. Canonical state
- What information is truly canonical and must be stored in the POS?
- What information already exists in GitHub and should only be referenced?
- What should be generated from canonical state rather than manually maintained?

### 2. Record types
- Which current record types should be removed entirely?
- Which current record types should be retained?
- Which should be optional (required only above a certain risk class)?

### 3. Work item format
- What is the smallest useful work-item record?
- What fields are always required vs. risk-class-conditional?
- How should PR number, branch name, base commit, head commit, and merge commit be represented?
- Can merge state be read from GitHub automatically, or must it be manually entered?
- How should Founder merge acceptance be reflected in the record?

### 4. Risk-scaled process
- What process applies at R0–R1?
- What process applies at R2?
- What extra controls apply at R3?
- What additional review applies at R4–R5?
- When is an Architect review required?

### 5. Generator views
- What views should the generator create?
- What data sources should each view read?
- What should appear in CURRENT_STATE, MANAGER_INBOX, and WORKER_CONTEXT?

### 6. Validator scope
- What should the validator check?
- What should the validator explicitly **not** decide (authority boundary)?
- What checks are structural? What checks are lifecycle? What checks are risk-enforcement?

### 7. Migration
- What migration path converts existing prototype records to the new format?
- What current files can be deprecated or removed?
- What is the implementation sequence (ordered)?

---

## Preferred Lean Direction

Seriously evaluate a structure similar to:

```
project/
├── state.yaml          — current phase and project status
├── roadmap.yaml        — ordered objectives
├── work/
│   └── WORK-001.yaml   — one file per work item
└── generated/
    ├── CURRENT_STATE.md
    ├── MANAGER_INBOX.md
    └── WORKER_CONTEXT.md
```

Do not adopt this exact structure if a better design emerges. The goal is the simplest structure that serves the actual operational needs.

---

## Potential Consolidated Work Record

Evaluate whether a single record like this replaces the current 7-record lifecycle:

```yaml
id: WORK-001
title: Build Lean POS commands
status: active          # proposed | active | review | accepted | rejected | cancelled
objective: >
  ...
owner_role: implementation_worker
risk_class: R2
scope:
  allowed:
    - tools/pos/
    - project/schemas/
  forbidden:
    - governance/frozen/
execution:
  branch: lean-pos-commands
  base_commit: abc1234
  pull_request: null      # GitHub PR number after opening
  head_commit: null       # filled after implementation
  merge_commit: null      # filled after Founder merge
architecture_review:
  required: false
  reference: null
verification:
  commands:
    - python -m pytest tests/ -v
    - python tools/pos/validate.py
  summary: null          # filled by worker after running
result:
  summary: null          # filled by worker
  limitations: []
timestamps:
  created_at: "2026-07-17T00:00:00Z"
  updated_at: "2026-07-17T00:00:00Z"
```

After Founder merge, status becomes `accepted` and `merge_commit` is filled.

The Architect must determine:
- Which fields should be manually entered vs. inferred from GitHub
- Whether separate risk records are ever needed, or always embedded
- Whether separate review records are ever needed, or always GitHub PR comments
- What the minimal schema looks like for R0–R1 vs. R2 vs. R3+

---

## Required Output

The Architect must produce an implementation-ready design document containing:

1. **Recommended model** — the proposed POS structure with rationale
2. **Removed record types** — what is eliminated and why
3. **Retained record types** — what stays and why
4. **Optional high-risk artifacts** — what is only required at R3+
5. **Risk-scaled process table** — per-class requirements
6. **GitHub integration model** — GitHub stores X; POS stores Y; POS references Z
7. **Data schemas** — YAML schema definitions for all record types
8. **Validation rules** — what the validator checks per record type and risk class
9. **Generator views** — what each generated file contains and from what source
10. **Migration plan** — how to convert existing prototype records
11. **Implementation tickets** — ordered list of bounded tickets the Manager can assign
12. **Test strategy** — what tests verify the new POS design
13. **Unresolved Founder decisions** — specific questions requiring Founder input

---

## Explicit Constraint

**The Architect must not implement Lean POS v1 in this assignment.**

Produce the design document only. The Manager will issue implementation tickets after Founder reviews the design.

---

## Acceptance

This assignment is accepted when:
- A design document exists at the agreed path
- All 20 design questions are answered
- Implementation tickets are defined and ordered
- Unresolved Founder decisions are clearly listed
- The Manager confirms the design is implementation-ready
- The Founder merges the PR containing the design document
