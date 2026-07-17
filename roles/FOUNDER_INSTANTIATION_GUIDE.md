# Founder Instantiation Guide

Practical steps to instantiate the Manager and Architect and start the first operating sequence.

---

## Instantiate the Manager

1. Create a new AI agent session with repository access to `https://github.com/jaiaFoster/ASA`.
2. Paste the full contents of `roles/manager/INSTANTIATION_PROMPT.md` as the system prompt.
3. Tell it to execute its startup checklist:
   > "Execute your startup checklist (`roles/manager/STARTUP_CHECKLIST.md`) and produce your first briefing."
4. Ask it for its first briefing:
   > "What is the current project state and what do you recommend we do next?"

**Copy-ready first message to the Manager:**
```
You are now active. Please execute your startup checklist (roles/manager/STARTUP_CHECKLIST.md) and produce your first briefing. Tell me: current state, active work, open PRs needing my attention, blockers, and your recommended next step. Then ask if you should proceed with assigning ARCH-POS-001 to the Architect.
```

---

## Instantiate the Architect

1. Create a new AI agent session with repository access to `https://github.com/jaiaFoster/ASA`.
2. Paste the full contents of `roles/architect/INSTANTIATION_PROMPT.md` as the system prompt.
3. Tell it to execute its startup checklist:
   > "Execute your startup checklist (`roles/architect/STARTUP_CHECKLIST.md`) and tell me what you found about the current POS implementation."
4. Assign ARCH-POS-001:
   > "Your first assignment is ARCH-POS-001. Read `roles/architect/FIRST_ASSIGNMENT.md` and confirm your understanding of the scope before starting."

**Copy-ready first message to the Architect:**
```
You are now active. Please execute your startup checklist (roles/architect/STARTUP_CHECKLIST.md). Inspect the current POS implementation (tools/pos/, project/schemas/). Then read your first assignment at roles/architect/FIRST_ASSIGNMENT.md and tell me: what are the key design questions, what constraints did you identify, and what do you need clarified before you start the design?
```

---

## First Operating Sequence

```
Step 1: Merge this PR (role-bootstrap-01) to main.
        → Constitutes acceptance of the role package.

Step 2: Instantiate the Manager.
        → Manager reads context and produces a briefing.

Step 3: Instantiate the Architect.
        → Architect inspects the current POS implementation.

Step 4: Tell the Manager the Architect is available.
        → Manager formally assigns ARCH-POS-001 to Architect.

Step 5: Architect produces Lean POS v1 design document.
        → Architect opens a PR with the design.

Step 6: Review the design PR and merge (or request changes).
        → Founder merge = design accepted.

Step 7: Manager converts design into implementation tickets.
        → Manager issues bounded tickets to workers.

Step 8: Workers implement on branches, open PRs.
        → Each Founder merge accepts that slice.
```

---

## Notes

- The Manager and Architect can operate independently or in parallel once both are instantiated.
- The Architect's design (Step 5) should be a document only — no POS code changes.
- Workers are temporary agents. The Manager issues worker assignments; only you can authorize a new worker type.
- GitHub merges are the acceptance mechanism. No separate paperwork required.
- The current POS on `main` is functional but provisional. Do not treat it as the final design.
