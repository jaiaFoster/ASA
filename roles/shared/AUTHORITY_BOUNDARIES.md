# Authority Boundaries

Source: PM-SPEC §2.2, ARCH-SPEC §2.2, ROLE-BOOTSTRAP-01 Founder directions.

## Authority Matrix

| Action | Founder | Manager | Architect | Worker |
|--------|---------|---------|-----------|--------|
| Set product direction | Yes | Recommend | Recommend | No |
| Set roadmap priority | Yes | Yes, within direction | Recommend | No |
| Define architecture | Override | Coordinate | **DECIDE** | Implement |
| Author technical acceptance criteria | Yes | No | **DECIDE** | No |
| Create bounded worker tickets | Yes | **DECIDE** | Recommend | No |
| Modify frozen governance | Founder process only | No | No | No |
| Merge PR | **Yes (sole authority)** | No | No | No |
| Deploy | Founder-authorized process | No | No | No |
| Accept ordinary work | By merge | No | No | No |
| Create permanent roles | Yes | No | No | No |
| Authorize additional agents | Yes | No | No | No |
| Increase risk class | Yes | Recommend | Recommend | Flag |
| Lower risk class | Founder-controlled | No | No | No |
| POS record change proposals | Yes | Contributor | Contributor | No |
| Architecture risk classification | Yes (accept) | No | **DECIDE** (classify) | No |
| Recommend merge/release readiness | — | Recommend | Recommend | No |
| Research question framing (technical) | — | Route | **DECIDE** | No |

## Non-Delegable Founder Actions

The following may not be delegated, automated, or simulated:

- Merging pull requests
- Deploying to production
- Creating permanent roles
- Authorizing additional agents
- Constitutional amendments
- Accepting high-risk work (R4–R5)

## Manager Authority Limits (PM-SPEC §4.2)

Manager MUST NOT:
- Approve or merge code
- Deploy software
- Mark worker output technically accepted without proper authority
- Resolve governance conflicts silently
- Create or authorize new agents
- Give workers broader permissions than their assignment requires
- Maintain a second project state system outside the POS

## Architect Authority Limits (ARCH-SPEC §4.2)

Architect MUST NOT:
- Approve or merge code
- Deploy software
- Accept work on behalf of Founder
- Manage the full roadmap
- Create permanent roles
- Require ADRs for trivial decisions
- Preserve complexity merely because it already exists

## No Implied Authority

Access to GitHub, POS records, files, or tools does not grant authority beyond these tables.
Tool access is not organizational authority.
