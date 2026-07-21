# Manager Context Packet

Concise briefing for a newly instantiated Manager.

## What ASA 2 Is

ASA 2 (Algorithmic Strategy Application 2) is being rebuilt separately from the legacy ASA system. This repository currently contains governance infrastructure and POS scaffolding. Application code is not present. No trading strategies, broker integrations, or financial logic are in scope for this Manager instance yet.

## Repository

```
https://github.com/jaiaFoster/ASA
main branch — production state
```

Key locations:
- `governance/frozen/` — Frozen normative documents (PM-SPEC, ARCH-SPEC, RISK-001, etc.)
- `governance/amendments/GOV-AMD-001.md` — Amendment register (013 Accepted; 001–012 Proposed)
- `project/` — POS records (canonical operational state)
- `project/generated/` — Generated views (not canonical)
- `tools/pos/` — Validator and generator
- `roles/` — Role packages (this directory)

## Governance Status

- PM-SPEC v0.2 and ARCH-SPEC v0.2 are Draft — not yet formally reviewed.
- GOV-AMD-001 Amendment 013 is Accepted and binding; Amendments 001–012 remain Proposed.
- Frozen documents under `governance/frozen/` must not be edited.
- Founder directions recorded in `roles/` take precedence over non-frozen bootstrap assumptions.

## Current POS Status

The current POS prototype (POS-BOOTSTRAP-01 on main branch) established:
- 6 YAML schemas for record types
- A deterministic validator
- A deterministic generator
- A CI workflow
- 33 tests

POS-BOOTSTRAP-02 (PR #2, branch `pos-bootstrap-02`) adds the full lifecycle implementation with 70 tests and additional schemas. It is pending Founder merge. Once merged, it will be accepted with no separate paperwork.

**The current POS is provisional scaffolding.** The Architect's first task (ARCH-POS-001) is to design Lean POS v1, which will reduce mandatory record types and eliminate unnecessary bookkeeping.

## Known Problem: Current POS is Too Heavy

The Founder has directed that:
- The 7-record lifecycle (work item + risk + assignment + result + review + evidence + decision) is too documentation-heavy for normal work
- Process requirements should scale with actual risk
- Founder merge = acceptance; no separate decision record needed
- GitHub already stores the evidence that currently gets duplicated in POS records
- The Manager and Architect are supposed to design the operating system going forward

## Immediate Objective

Work with the Architect to produce the Lean POS v1 design (ARCH-POS-001). The Architect will produce the design; the Manager will convert the design into implementation tickets.

## Current Limits

- No application code exists in this repository
- No broker or trading integrations
- No deployment infrastructure
- Both Manager and Architect are not yet instantiated (you are the first)
- Worker instantiation is Founder-authorized only

## Next Expected Action

1. Confirm Architect is instantiated or request Founder instantiate Architect.
2. Once Architect is available, assign ARCH-POS-001.
3. Receive Architect's Lean POS v1 design.
4. Convert design into implementation tickets.
5. Brief Founder on the proposed implementation sequence.

## Founder Relationship

The Founder is @jaiaFoster. Contact via GitHub PR comments or direct message. The Founder's time is valuable — frame all escalations as specific bounded questions with a recommended action and consequence of deferral.
