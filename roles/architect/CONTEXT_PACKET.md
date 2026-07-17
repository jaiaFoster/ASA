# Architect Context Packet

Concise briefing for a newly instantiated Architect.

## What ASA 2 Is

ASA 2 (Algorithmic Strategy Application 2) is being rebuilt separately from the legacy ASA system. The repository currently contains governance infrastructure and POS scaffolding only. No application code, trading strategies, broker integrations, or financial logic exist yet.

## Repository

```
https://github.com/jaiaFoster/ASA
main branch — current state
```

## Governance Corpus

| Document | Path | Status |
|----------|------|--------|
| PM-SPEC v0.2 | `governance/frozen/PM-SPEC-v0.2.md` | Draft (not formally accepted) |
| ARCH-SPEC v0.2 | `governance/frozen/ARCH-SPEC-v0.2.md` | Draft (not formally accepted) |
| RISK-001 | `governance/frozen/RISK-001` | Draft |
| RES-001 | `governance/frozen/RES-001-v0.2.md` | Frozen |
| RES-002 | `governance/frozen/RES-002-v0.2.md` | Frozen |
| POS-RS | `governance/frozen/POS-RS-v0.2.md` | Frozen |
| GOV-AMD-001 | `governance/amendments/GOV-AMD-001.md` | All amendments Proposed (none Accepted) |

Frozen documents must not be edited. Amendments are proposed but not binding.

## Current POS Prototype

The current POS (`main` branch state) includes:
- 6 YAML schemas: work-item, assignment, worker-result, review, evidence, decision
- A deterministic validator (`tools/pos/validate.py`)
- A deterministic generator (`tools/pos/generate.py`)
- A CI workflow (`.github/workflows/validate-pos.yml`)
- 33 tests (`tests/pos/`)

POS-BOOTSTRAP-02 (on branch `pos-bootstrap-02`, PR #2) adds:
- A 7th schema: risk-record
- Lifecycle records for the first work item (ASA2-WORK-001 through ASA2-DECISION-001)
- 70 tests and cross-record validation
- It is pending Founder merge

## Known Problem: Current POS is Too Heavy

The Founder has explicitly directed:

1. The 7-record mandatory lifecycle is too documentation-heavy for normal work
2. Process should scale with actual risk
3. Founder merge = acceptance — no separate decision record needed for ordinary work
4. GitHub stores PR state, merge identity, diff, CI status — POS should reference these, not duplicate them
5. The Manager and Architect are supposed to design the operating system
6. The current POS is scaffolding, not the final design

## Your First Assignment

**ARCH-POS-001 — Design Lean POS v1**

See `roles/architect/FIRST_ASSIGNMENT.md` for the full specification.

Goal: Design a simplified Git-backed Project Operating System that preserves:
- Clear authority
- Bounded work
- Deterministic validation
- Traceability for high-risk work
- Risk-scaled process

While eliminating:
- Mandatory multi-record lifecycle for every work item
- Duplication of GitHub data
- Process overhead that costs more than the risk justifies

## Constraints

- Do not implement Lean POS v1 in the first assignment — design only
- Do not modify frozen governance documents
- Do not merge, deploy, or accept work
- Do not instantiate additional agents
- No application code in scope

## Immediate Next Steps

1. Read `roles/architect/FIRST_ASSIGNMENT.md`
2. Inspect the current POS implementation
3. Confirm scope and constraints with Manager
4. Produce the Lean POS v1 design document
5. Return design to Manager for implementation planning
