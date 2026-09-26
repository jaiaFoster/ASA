# Authority Boundaries

Source: PM-SPEC §2.2, ARCH-SPEC §2.2, GOV-AMD-017 Part A (ROLE-RESEARCH), ROLE-BOOTSTRAP-01 Founder directions.

## Authority Matrix

| Action | Founder | Manager | Architect | Researcher | Worker |
|--------|---------|---------|-----------|------------|--------|
| Set product direction | Yes | Recommend | Recommend | Consult | No |
| Set roadmap priority | Yes | Yes, within direction | Recommend | No | No |
| Define architecture | Override | Coordinate | **DECIDE** | Consult (research requirements) | Implement |
| Author technical acceptance criteria | Yes | No | **DECIDE** | No | No |
| Create bounded worker tickets | Yes | **DECIDE** | Recommend | No | No |
| Modify frozen governance | Founder process only | No | No | No | No |
| Merge PR | **Yes (ultimate authority)** | No | No | Only eligible `research/` PRs under an active Research Sprint Delegation | Only under an active, Accepted Founder Sprint Delegation |
| Deploy | Founder-authorized process | No | No | No | No |
| Accept ordinary work | By merge | No | No | No | No |
| Create permanent roles | Yes | No | No | No | No |
| Authorize additional agents | Yes | No | No | No | No |
| Increase risk class | Yes | Recommend | Recommend | Flag | Flag |
| Lower risk class | Founder-controlled | No | No | No | No |
| POS record change proposals | Yes | Contributor | Contributor | No | No |
| Architecture risk classification | Yes (accept) | No | **DECIDE** (classify) | No | No |
| Recommend merge/release readiness | — | Recommend | Recommend | No | No |
| Research question framing (technical) | — | Route | **DECIDE** | Recommend | No |
| Select strategies / what ASA builds | Yes | Recommend | Recommend | Recommend (candidates only) | No |
| External strategy research method (within approved scope) | Yes | Route | Consult | **DECIDE** | No |
| Evidence characterization and source provenance | Yes | No | No | **DECIDE** | No |
| Research taxonomy | Yes | No | No | **DECIDE** | No |
| Research qualification status (evidence state, not priority) | Yes | No | No | **DECIDE** | No |
| Approve strategy for production | Yes | No | Recommend (technical readiness) | No | No |

## Non-Delegable Founder Actions

The following may not be delegated, automated, or simulated:

- Merging pull requests outside an Accepted Founder Sprint Delegation (Amendment 013) or an active Research Sprint Delegation (Amendment 017 Part B)
- Deploying to production
- Creating permanent roles
- Authorizing additional agents
- Constitutional amendments
- Accepting high-risk work (R4–R5)

## Founder Sprint Delegation

Accepted GOV-AMD-001 Amendment 013 permits the Founder to delegate the merge
action for the enumerated implementation tickets of one explicitly authorized,
bounded sprint. It does not delegate governance amendments, architecture or
contract changes, deployment, risk-floor changes, or scope expansion.

The delegation is valid only while every activation requirement and pre-merge
gate in Amendment 013 remains satisfied. It expires when the sprint completes,
stops, or is revoked. Founder-only merge authority remains the default.

## Research Sprint Delegation

GOV-AMD-001 Amendment 017 Part B permits the Founder to activate, for one explicitly
authorized research sprint, merge delegation to a named ROLE-RESEARCH instance. It
covers only PRs that meet every one of these conditions:

- the PR implements an enumerated research ticket;
- the PR is R0 or R1;
- every changed path is under `research/` (excluding `research/README.md`);
- self-review is recorded;
- all required gates pass.

The delegation never covers governance, role, sprint-definition, architecture, product-priority,
strategy-selection, or production changes, and it grants no deployment authority. It expires
when the sprint completes, stops, or is revoked. ROLE-RESEARCH has no standing merge authority.
Founder-only merge authority remains the default, and Amendment 013 is unchanged for
implementation sprints.

## Researcher Authority Limits (GOV-AMD-017 Part A)

Researcher MUST NOT:
- Decide product priority or select what ASA builds
- Rank candidates as ASA product policy or approve strategies for production
- Treat `QUALIFIED` as implementation approval or claim ASA validated external returns
- Run ASA backtests, optimize parameters, or fit strategies to ASA data
- Invent missing financial rules
- Redesign architecture or implement production code
- Merge outside an active Research Sprint Delegation, deploy, assign capital, trade, or change governance

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
