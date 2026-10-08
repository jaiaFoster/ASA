# GOV-AMD-018: Repository-Backed Role Hydration and Founder-Blocker Gateway

| Field | Value |
|---|---|
| `amendment_id` | GOV-AMD-018 (register entry: GOV-AMD-001 Amendment 018) |
| `status` | Proposed — **PENDING INDEPENDENT, STRUCTURAL, AND CONSTITUTIONAL REVIEW. Not binding until the required reviews complete and the Founder personally merges the accepted version to the default branch.** |
| `proposer` | Founder |
| `date` | 2026-10-08 |
| `risk_class` | R5 — Constitutional. This amendment changes agent-instantiation authority and the escalation path to the Founder. |
| `applies_to` | RES-001, RES-002, PM-SPEC, ARCH-SPEC, ROLE-RESEARCH (GOV-AMD-017), GOV-AMD-001 Amendment 013 operating model, roles/shared/AUTHORITY_BOUNDARIES.md |
| `binding_scope` | Model A — accepted-on-entry (GOV-AMD-001 §0.1), subject to the effectiveness condition above |

## 1. Purpose

ASA repeatedly needs bounded consultation, review, verification, and decision support from existing organizational roles while an implementation worker is active.

Current operating practice can create unnecessary Founder interruptions when a worker reaches:
- an architecture question;
- a delivery/scope question;
- a research-evidence question;
- a required review gate;
- a possible Founder blocker.

This amendment establishes two organization-wide mechanisms:

1. **Repository-Backed Role Hydration** — an authorized worker engine may instantiate a fresh, bounded instance of an already-defined AI role from its canonical repository package without obtaining a new Founder authorization for each invocation.
2. **Founder-Blocker Gateway** — only ROLE-PM or ROLE-ARCH may escalate a work item to the Founder as a confirmed Founder blocker. Other roles submit a candidate blocker to one of those two roles first.

The intent is to preserve Founder authority while removing avoidable Founder routing and chat dependence.

## 2. Definitions

### 2.1 Existing Repository Role

An **Existing Repository Role** is an AI role whose authority and rehydration sources already exist in canonical GitHub state.

For this amendment, a role is hydratable only when:
- it is listed in `project/roles/registry.yaml` or is governed by a repository-resident approved Execution Profile;
- it is not a human authority;
- its RoleSpec or Execution Profile and required operating instructions are resolvable from the repository;
- it is not retired;
- its requested invocation is within the role's existing authority.

At the time this amendment is proposed, repository-backed permanent AI roles include:
- ROLE-PM;
- ROLE-ARCH;
- ROLE-RESEARCH.

ROLE-FOUNDER is a human authority and is **never hydratable**.

A future role automatically becomes eligible only after its own governing role artifact is valid and repository-resident. GOV-AMD-018 never creates a role merely by naming or invoking it.

### 2.2 Hydration

**Hydration** is creation of a fresh, time-bounded instance of an Existing Repository Role using its canonical repository RoleSpec, instructions, rehydration sequence, current assignment packet, and applicable governance.

Hydration:
- creates an instance, not a new organizational role;
- does not change the role's authority;
- does not create standing authority for the instance;
- does not bypass review independence;
- does not transfer the worker's implementation authority to the consulted role;
- terminates when the bounded interaction completes unless a governing RoleSpec requires an earlier termination.

This definition is consistent with RES-002's distinction between a permanent role and a time-bounded instance.

### 2.3 Worker Engine

A **Worker Engine** is an authorized implementation-worker execution context operating under a Founder-approved sprint, bounded assignment, or equivalent current authority.

This amendment grants no implementation scope by itself. A worker may hydrate roles only in service of already-authorized work.

### 2.4 Candidate Founder Blocker

A **Candidate Founder Blocker** is a condition a non-PM/non-Architect role believes may require a Founder-only decision.

A candidate blocker is not yet a Founder escalation.

### 2.5 Confirmed Founder Blocker

A **Confirmed Founder Blocker** is a candidate blocker that ROLE-PM or ROLE-ARCH has reviewed and classified as requiring a Founder-only decision under current governance.

Only a Confirmed Founder Blocker may be raised to the Founder as a blocking escalation.

## 3. Repository-Backed Role Hydration Authority

### 3.1 Grant

While operating within an authorized assignment, a Worker Engine MAY hydrate a fresh instance of any hydratable Existing Repository Role without requesting case-by-case Founder approval.

This is a standing **instance-creation mechanism for already-authorized roles**, not permanent-role creation and not general agent-creation authority.

The Worker Engine MAY use hydration for:
- consultation;
- architecture interpretation;
- delivery/scope interpretation;
- research interpretation within ROLE-RESEARCH authority;
- required structural, technical, or independent review when the role is eligible;
- Founder-blocker confirmation under Part 5;
- bounded verification expressly permitted by the role's authority.

### 3.2 Required hydration packet

Every hydration MUST provide a bounded assignment packet containing at least:

- hydrating worker assignment or sprint ID;
- requested role ID;
- purpose of the invocation;
- exact question or review objective;
- exact repository ref and, for PR review, exact head SHA;
- relevant ticket / issue / PR;
- risk class or current risk hypothesis;
- applicable acceptance criteria;
- canonical artifacts to read;
- permitted actions;
- prohibited actions;
- expected output;
- termination condition.

The packet SHOULD reference canonical artifacts rather than copying large context.

### 3.3 Rehydration

The fresh role instance MUST rehydrate according to:
1. applicable Founder instruction already recorded in canonical state;
2. frozen governance and accepted amendments;
3. the role's governing RoleSpec;
4. shared authority / risk / GitHub-acceptance rules;
5. the role's current instructions and repository-backed rehydration artifacts;
6. current project/sprint state relevant to the assignment;
7. the bounded hydration packet;
8. only then, task-specific code, PR, research, or evidence.

Prior chat memory is non-canonical and MUST NOT substitute for this sequence.

### 3.4 Authority preservation

Hydration never grants authority outside the hydrated role's existing Decision Rights.

Examples:
- ROLE-ARCH may decide architecture within its current authority but may not merge or deploy.
- ROLE-PM may decide sequencing and classify delivery blockers within its current authority but may not make architecture decisions.
- ROLE-RESEARCH may decide research-evidence matters within its RoleSpec but may not select product strategy or implement production code.

Tool access does not enlarge authority.

### 3.5 Independence

A hydrated role MAY satisfy a review requirement only when current governance permits that role type to perform the review and the instance is sufficiently independent.

For an independent R3 or equivalent independent review:
- the reviewer instance must be distinct from the author/implementer instance;
- it must not be the same role instance that authored, assigned, or edited the work;
- the assignment is read-only unless current governance explicitly says otherwise;
- exact-head review is required;
- any new code SHA invalidates the prior exact-head PASS/HOLD.

Hydrating ROLE-ARCH is not a substitute for an independent reviewer when both gates are required.

### 3.6 Termination and durability

A hydrated instance terminates after:
- the bounded answer/review is delivered;
- the assignment is cancelled;
- required rehydration fails and cannot be repaired safely;
- the role detects authority conflict requiring a different role;
- any earlier termination condition in its RoleSpec.

Material decisions, review dispositions, and Founder-blocker confirmations MUST be externalized to GitHub/POS or another canonical artifact before the instance ends.

Incidental reasoning need not be preserved.

## 4. No-Lull Interaction Rule

A worker MUST NOT treat a required non-Founder role interaction as a reason to idle the entire assignment.

When dependency-safe work exists, the worker:
1. hydrates the required role;
2. sends the bounded packet;
3. continues independent authorized work while the consultation/review is pending;
4. applies the resulting decision only to the affected path.

The worker MUST stop the affected action immediately when continuing it would violate a protected boundary, but should continue unaffected authorized work.

This rule does not weaken any review, CI, risk, or acceptance gate.

## 5. Founder-Blocker Gateway

### 5.1 Exclusive escalation authority

Only:
- ROLE-PM; or
- ROLE-ARCH

may raise a work item to the Founder as a **Confirmed Founder Blocker**.

No worker, researcher, temporary reviewer, or other AI role may directly classify and escalate its own condition to the Founder as a blocking Founder decision.

This is an escalation-routing rule. It does not reduce the Founder's authority over any decision class.

### 5.2 Worker and other-role behavior

When a non-PM/non-Architect role detects a possible Founder blocker, it MUST:

1. stop only the affected action if continuing could cross a protected boundary;
2. continue unaffected in-scope work;
3. create a concise Candidate Founder Blocker Packet;
4. hydrate or route the packet to ROLE-ARCH or ROLE-PM according to §5.3;
5. await that role's classification for the affected decision.

The detecting role MUST NOT:
- contact the Founder directly as a blocking escalation;
- claim "Founder blocker" as final status;
- stop unrelated work merely because the candidate exists;
- broaden scope while waiting.

### 5.3 Routing

Candidate blockers route as follows.

**ROLE-ARCH first** when the candidate concerns:
- architecture;
- canonical ownership;
- interface/schema/identity boundaries;
- security or credential architecture;
- technical risk classification;
- protected technical contract;
- whether a truthful implementation requires a breaking technical change;
- whether a live-broker boundary would technically expand.

**ROLE-PM first** when the candidate concerns:
- product/scope ambiguity;
- roadmap or sequencing;
- whether a request is inside the activated sprint;
- delivery conflict;
- money/vendor/legal commitment as a project decision;
- whether a requested action is Founder-only deployment/destructive action;
- governance-routing uncertainty not primarily technical.

Either ROLE-PM or ROLE-ARCH MAY reroute the candidate to the other before classification.

When the blocker spans both domains, the first recipient MAY hydrate the other and issue a joint confirmation. One of them remains the named escalation owner.

### 5.4 Confirmation outcomes

ROLE-PM or ROLE-ARCH MUST classify the candidate into exactly one of:

#### A. NOT_A_FOUNDER_BLOCKER — CONTINUE
The condition is resolvable within existing authority and scope.

The confirming role provides:
- governing authority;
- bounded guidance;
- any required review/correction;
- explicit continuation instruction for the affected path.

The worker continues without Founder involvement.

#### B. LOCAL_BLOCKER — ROUTE_OR_CORRECT
The issue blocks the affected path but belongs to another non-Founder authority, review, dependency, provider wait, or correction loop.

The confirming role names:
- responsible authority;
- required evidence/action;
- what work may continue independently.

No Founder escalation occurs.

#### C. CONFIRMED_FOUNDER_BLOCKER
A current governance rule requires a Founder-only decision.

Only then does ROLE-PM or ROLE-ARCH send the Founder escalation.

### 5.5 Founder blocker classes

A confirming ROLE-PM or ROLE-ARCH may classify a Founder blocker only when the required decision is actually Founder-only under current governance, including:

- material product-direction choice;
- money, vendor, licensing, legal, or material recurring-spend commitment;
- live-broker authority or permission expansion;
- Founder-only production deployment;
- destructive or irreversible production action;
- protected governance / constitutional change;
- protected breaking contract that cannot be resolved within authorized scope;
- material scope expansion beyond the active assignment/sprint;
- irreconcilable conflict among governing authorities;
- another decision class explicitly reserved to the Founder by accepted governance.

Routine implementation defects, test failures, CI failures, ordinary architecture corrections, required reviews, provider/data UNKNOWNs, observation waits, and typed capacity deferrals are not Founder blockers by themselves.

### 5.6 Confirmed Founder Blocker Packet

The confirming ROLE-PM or ROLE-ARCH must send a concise packet containing:

- exact blocked action;
- assignment / sprint / ticket / PR;
- decision class;
- why the decision is Founder-only;
- verified facts and evidence;
- canonical governance references;
- attempted in-authority resolutions;
- alternatives;
- recommendation, if the confirming role has RECOMMEND authority;
- safe default while waiting;
- unaffected work that continues;
- narrowest Founder decision required.

The packet MUST NOT contain raw context dumps or speculative escalation theater.

### 5.7 Safety while awaiting confirmation

If the candidate involves a protected high-consequence boundary, the detecting role stops that affected action immediately while confirmation is pending.

Examples:
- deployment;
- live broker mutation;
- financial commitment;
- destructive migration;
- credential/security expansion;
- governance change.

The gateway never authorizes "continue first, ask later" across a protected boundary.

## 6. Manager and Architect Duties Under This Amendment

### 6.1 ROLE-PM

ROLE-PM gains the organization-wide responsibility to:
- classify delivery/scope/project-governance Candidate Founder Blockers;
- reject false Founder blockers and give continuation guidance within its existing authority;
- route technical candidates to ROLE-ARCH;
- raise Confirmed Founder Blockers to the Founder.

This does not grant ROLE-PM architecture DECIDE authority, merge authority, deployment authority, or product-direction authority.

### 6.2 ROLE-ARCH

ROLE-ARCH gains the organization-wide responsibility to:
- classify technical/architecture Candidate Founder Blockers;
- resolve candidates inside its existing architecture authority where possible;
- reject false Founder blockers and provide bounded technical continuation guidance;
- route project/scope candidates to ROLE-PM;
- raise Confirmed Founder Blockers to the Founder.

This does not grant ROLE-ARCH roadmap authority, merge authority, deployment authority, or product-direction authority.

## 7. Interaction With Existing Governance

### 7.1 Founder authority

Unchanged.

The Founder remains the ultimate authority and retains all existing Founder-only decision classes.

This amendment narrows **who may interrupt/escalate to the Founder**, not what the Founder controls.

### 7.2 Permanent-role creation

Unchanged.

Only the Founder may create a new permanent role.

Hydrating an instance of an Existing Repository Role is expressly not permanent-role creation.

### 7.3 Amendment 013

Amendment 013 remains the merge-delegation authority for eligible implementation sprints.

GOV-AMD-018:
- does not grant merge authority;
- does not grant deployment authority;
- does not expand sprint scope;
- does not lower validation/review floors;
- only defines role hydration and escalation routing.

A worker may use hydration while operating under Amendment 013, but any hydrated role remains bound by its own merge/deployment prohibitions.

### 7.4 GOV-AMD-017 / ROLE-RESEARCH

ROLE-RESEARCH becomes hydratable for bounded research questions already within its authority.

Hydration does not:
- create research-sprint merge delegation;
- allow production implementation;
- allow product selection;
- bypass Part B of GOV-AMD-017.

### 7.5 Existing "Authorize Additional Agents" language

Upon acceptance, repository compilations such as `roles/shared/AUTHORITY_BOUNDARIES.md` MUST distinguish:

- **creating/authorizing a new role or new agent authority** — Founder-only; from
- **hydrating a bounded instance of an already-authorized repository role** — permitted to an authorized Worker Engine by this amendment.

This amendment supersedes lower-level wording that treats those two actions as identical.

### 7.6 Prepared role packages

A repository role in `prepared`, `trial`, or `active` state MAY be hydrated for a bounded invocation when:
- its repository package is complete enough to rehydrate;
- the invocation is within its authority;
- no higher-level rule prohibits the requested action.

`deprecated` roles may only be hydrated for transition/review purposes allowed by their lifecycle.
`retired` roles may not be hydrated for normal operation.

A role's `instantiated: false` registry field means no continuing instance is currently active. It does not prohibit fresh bounded hydration after this amendment becomes Accepted.

## 8. Required Repository Follow-Up After Acceptance

This amendment itself is the normative proposal. If accepted, implementation MUST reconcile at least:

- `roles/shared/AUTHORITY_BOUNDARIES.md`;
- `roles/shared/HANDOFF_PROTOCOL.md` or successor interaction specification;
- ROLE-PM escalation instructions;
- ROLE-ARCH escalation instructions;
- ROLE-RESEARCH escalation instructions;
- worker Execution Profile / sprint templates;
- role registry semantics for `instantiated`;
- risk-scaled process / GitHub acceptance docs where necessary;
- regression tests covering hydration and Founder-blocker routing.

Do not update those operational compilations as though this amendment were binding before acceptance.

## 9. Regression Scenarios Required Before Acceptance

At minimum, tests or review probes must cover:

1. Worker hydrates ROLE-ARCH for a schema-boundary question; Architect responds; no Founder contact.
2. Worker hydrates ROLE-PM for scope ambiguity; Manager confirms in-scope and worker continues.
3. Worker hydrates ROLE-RESEARCH for external-evidence interpretation; Researcher cannot select product strategy.
4. Worker attempts to hydrate ROLE-FOUNDER; denied.
5. Worker attempts to hydrate an unregistered/invented role; denied.
6. Worker attempts to give hydrated Architect merge authority; denied.
7. Worker proposes a candidate paid-vendor blocker to ROLE-PM; PM confirms and raises to Founder.
8. Worker proposes ordinary failing test as Founder blocker; PM/ARCH returns NOT_A_FOUNDER_BLOCKER.
9. Worker proposes protected breaking architecture contract; ARCH either resolves within authority or confirms Founder blocker.
10. Researcher attempts direct Founder blocker escalation; routed through PM/ARCH.
11. Required Architect + independent R3 gates hydrate distinct instances; Architect PASS does not satisfy independent R3.
12. Review head SHA changes after PASS; prior exact-head disposition invalidated.
13. Hydration packet omits scope/prohibitions/termination; invocation fails closed.
14. Required rehydration artifact missing; hydrated role enters safe mode and does not exercise affected DECIDE authority.
15. Candidate blocker is pending; worker continues unaffected authorized work.
16. Candidate involves live broker mutation; affected action stops immediately while ARCH/PM confirms.
17. Hydrated role terminates after bounded output and externalizes material decision/review.
18. ROLE-PM and ROLE-ARCH disagree on blocker classification; conflict is recorded and routed according to governing authority rather than silently resolved.

## 10. Risk and Review

**Risk class: R5 confirmed by subject matter.**

This amendment changes:
- who may instantiate instances of existing AI roles;
- the organizational escalation path to the Founder;
- interaction boundaries of permanent roles.

Before acceptance it requires:
- Independent Review;
- Structural Review;
- Constitutional Review;
- regression/probe evidence for §9;
- Founder approval and personal merge.

The author/assigner of this amendment must not be the sole independent reviewer.

## 11. Acceptance Criteria

This amendment may be marked Accepted only when:

- all required R5 reviews PASS;
- review records are durable in GitHub;
- conflicts with RES-001 / RES-002 / PM-SPEC / ARCH-SPEC / GOV-AMD-017 are resolved;
- the distinction between new-role creation and existing-role hydration is unambiguous;
- the Founder-blocker gateway preserves immediate safe-stop behavior for protected actions;
- review independence remains intact;
- no merge/deployment/product authority is accidentally granted through hydration;
- a follow-up implementation plan exists for §8;
- the Founder personally merges the accepted version.

## 12. Reversion

Reversion requires a Founder-approved R5 amendment or superseding major governance revision.

Reversion of GOV-AMD-018:
- removes the standing worker hydration mechanism;
- restores prior direct-escalation behavior from underlying RoleSpecs;
- does not retire or delete any permanent role;
- does not invalidate historical review/escalation artifacts produced while the amendment was active.

## 13. Founder Direction Captured

The Founder direction motivating this proposal is:

- an authorized worker should be able to hydrate and consult any existing repository-backed AI role without stopping to ask the Founder for each invocation;
- this should apply beyond ROLE-ARCH to every existing repository role whose authority fits the requested interaction;
- only ROLE-PM or ROLE-ARCH should be able to raise a Founder blocker;
- workers and other roles should first ask ROLE-PM or ROLE-ARCH to confirm whether the candidate actually requires Founder involvement;
- when it does not, ROLE-PM or ROLE-ARCH should provide bounded guidance and work should continue.

This section records intent. The normative rules are §§2–11 above.
