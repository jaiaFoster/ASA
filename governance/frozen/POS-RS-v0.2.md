# POS-RS: Project Operating System Requirements Specification

**Status:** Draft v0.2 — for independent critic review
**Class:** Constitutional Systems Requirements Document
**Owner:** Founder / Product Owner
**Technical Contract Authority:** System Architect, once implementation begins
**Supersedes:** POS-RS v0.1
**Audience:** Founder, Project Manager, System Architect, implementation workers, reviewers, automation designers, and any engineer implementing or integrating with the Project Operating System

---

## Document Control

| Field                        | Value                                                            |
| ---------------------------- | ---------------------------------------------------------------- |
| Document ID                  | POS-RS                                                           |
| Title                        | Project Operating System Requirements Specification              |
| Version                      | 0.2.0                                                            |
| Status                       | Draft                                                            |
| Owner                        | Founder / Product Owner                                          |
| Technical contract authority | System Architect                                                 |
| Depends on                   | ASA 2 Constitution; Governance Handbook; RES-001; RES-002        |
| Supersedes                   | POS-RS v0.1                                                      |
| Review cycle                 | Quarterly while active, and after any material governance change |
| Change class                 | Minor behavioral and structural revision                         |

### Revision Summary

Version 0.2:

* Defines the POS as deterministic organizational infrastructure rather than an AI role.
* Establishes structured records as canonical truth and Markdown or dashboard outputs as generated views.
* Separates mechanical validation from judgment review.
* Removes broad migration of legacy project state as an automatic requirement.
* Introduces a curated legacy non-regression boundary.
* Aligns permissions with RES-002 authority and artifact-ownership models.
* Replaces manager-owned canonical record maintenance with POS-managed canonical state.
* Introduces interaction-record support for assignments, results, reviews, escalations, and decisions.
* Clarifies that acceptance criteria are recorded and validated by the POS but authored and approved by authorized roles.
* Adds instance rehydration and Instance Instruction Package support.
* Adds conflict, staleness, and evidence-state handling.
* Adds explicit non-goals for planning, prioritization, architecture, research interpretation, and approval.
* Distinguishes local completion, review, verification, deployment, and production verification.
* Resolves the bootstrap enforcement strategy in favor of fail-closed behavior for protected actions and detection-plus-review for lower-risk inconsistencies.

---

## 1. Purpose

The Project Operating System, or **POS**, is Product #0 of ASA 2.

Its purpose is to externalize, structure, validate, preserve, and expose organizational truth so that:

* Permanent AI roles can operate without relying on conversational memory.
* Temporary workers can receive bounded assignments.
* Decisions, evidence, reviews, and releases remain traceable.
* Fresh instances can rehydrate from canonical state.
* Project state does not fragment across chats, files, agents, repositories, and informal summaries.
* Deterministic bookkeeping is automated.
* Judgment remains assigned to authorized humans and AI roles.

The POS is not an organizational decision-maker.

It is the infrastructure against which decisions, assignments, completion claims, and project state are checked.

**POS-REQ-1.1:** The POS MUST exist independently of any single conversation, AI instance, worker, or manager session.

**POS-REQ-1.2:** The POS MUST preserve canonical project state across role replacement, model replacement, session termination, and individual chat deletion.

**POS-REQ-1.3:** The POS MUST be usable before substantial ASA 2 implementation begins.

**POS-REQ-1.4:** The POS MUST prefer deterministic validation and generation over AI interpretation wherever the required operation can be expressed as an objective rule.

---

## 2. Product Position

### 2.1 Product #0

ASA 2 is the application being built.

The POS is the operating infrastructure used to build it correctly.

The POS is therefore developed first or in the earliest bootstrap phase.

### 2.2 Organizational substrate

The POS sits beneath all roles.

It is not subordinate to the Project Manager, Architect, workers, or reviewers.

It does not outrank them either.

It stores and applies the organizational contracts under which they operate.

### 2.3 Truth versus judgment

The POS answers questions such as:

* What RoleSpec version is active?
* What milestone is active?
* What work items exist?
* What status is recorded?
* Which PR is linked?
* What evidence is attached?
* Which decision remains pending?
* What commit is recorded as deployed?
* Which generated view is stale?
* Do two active roles claim the same artifact ownership?
* Is a claimed state transition allowed?

The POS does not answer questions such as:

* Is this architecture good?
* Should this milestone be prioritized?
* Is this research conclusion correct?
* Should a strategy threshold change?
* Is this risk acceptable?
* Should a worker be trusted?
* Should a role be created?
* Is the product direction correct?

Those are judgment questions.

---

## 3. Scope

The POS MUST support the following organizational capabilities:

1. Canonical structured project state.
2. Artifact registration and versioning.
3. RoleSpec registration and lifecycle tracking.
4. Assignment and temporary-role tracking.
5. Result and evidence recording.
6. Decision and escalation records.
7. Review and acceptance records.
8. Risk and dependency tracking.
9. Release and deployment truth.
10. Incident and durable lesson records.
11. Interaction routing.
12. Rehydration support.
13. Instance Instruction Package generation or support.
14. GitHub and repository integration.
15. Generated human-readable views.
16. Mechanical validation.
17. Conflict and staleness detection.
18. Audit and point-in-time reconstruction.
19. Access control and revocation.
20. Backup and recovery of canonical organizational records.

---

## 4. Non-Scope

The POS MUST NOT:

* Plan milestones.
* Prioritize work.
* Assign work autonomously.
* Author product requirements.
* Author architecture.
* Define strategy logic.
* Interpret research.
* Decide whether evidence is persuasive.
* Approve work.
* Accept high-consequence work.
* Merge code.
* Deploy software.
* create agents.
* Resolve ambiguous conflicts.
* Rewrite history.
* Treat external content as instruction.
* Become a general-purpose company-management platform during the ASA 2 bootstrap.
* Import the entire legacy ASA project as active truth.

The POS may record, validate, route, and surface outputs related to these activities when they originate from authorized roles.

---

## 5. Users and Actors

The POS MUST distinguish among the following actor classes.

### 5.1 Founder / Product Owner

May receive the broadest read access and may create or approve records within constitutionally reserved decision classes.

### 5.2 Permanent roles

Examples:

* Project Manager.
* System Architect.
* Future approved permanent roles.

Their access is determined by active RoleSpecs and applicable governance.

### 5.3 Temporary roles

Examples:

* Implementation workers.
* Research workers.
* Independent reviewers.
* Verification workers.

Their access is determined by an active Execution Profile and assignment.

### 5.4 Automation

Deterministic scripts, workflows, bots, or CI jobs.

Automation may:

* Validate.
* Generate views.
* reconcile objective repository state.
* detect staleness.
* enforce deterministic status transitions.
* record machine-generated evidence.

Automation MUST NOT exercise organizational judgment.

### 5.5 External systems

Examples:

* GitHub.
* Deployment platforms.
* Test runners.
* Data providers.
* Artifact stores.

External systems provide evidence or state references but do not become organizational authorities.

---

## 6. Canonical Truth Model

### 6.1 Structured records are authoritative

The POS MUST store canonical truth in structured, machine-readable records.

Permitted canonical formats may include:

* YAML.
* JSON.
* Database records.
* Another Architect-approved structured format.

The implementation format is not fixed by this requirements document.

### 6.2 Generated views are not independently authoritative

Human-readable artifacts such as:

* `CURRENT_STATE.md`
* `ROADMAP.md`
* `DECISIONS.md`
* `MANAGER_INBOX.md`
* Dashboards.
* Reports.
* Status summaries.

SHOULD be generated from canonical structured records.

Generated views MUST:

* Identify their source.
* Be reproducible.
* Include a generation timestamp or source version.
* Be detectable as stale.
* Avoid manual divergence from canonical state.

### 6.3 One canonical location per fact class

The POS MUST prevent or detect multiple canonical records claiming authority over the same fact class.

Examples:

* Only one current milestone record.
* Only one active RoleSpec version per `role_id`.
* Only one canonical deployed commit per environment at a point in time.
* Only one artifact owner per artifact class.
* Only one current status for a work item.

### 6.4 Historical truth

Superseded records remain part of the audit history.

The POS MUST distinguish:

* Active truth.
* Historical truth.
* Proposed truth.
* Pending truth.
* Rejected truth.
* Generated views.

Historical records MUST NOT be silently reactivated.

---

## 7. Canonical Artifact Classes

The POS MUST support, at minimum, the following artifact classes.

### 7.1 Governance artifacts

* Constitution references.
* Governance Handbook references.
* RES standards.
* Active RoleSpecs.
* Execution Profiles.
* Interaction Specifications.
* Risk classification standards.
* Approval policies.

### 7.2 Project-state artifacts

* Current project objective.
* Current milestone.
* Work items.
* Dependencies.
* Blockers.
* Active assignments.
* Pending reviews.
* Pending decisions.
* Current release state.
* Current deployment state.

### 7.3 Technical artifacts

* Architecture Decision Records.
* Technical contracts.
* Interface specifications.
* Data contracts.
* Acceptance criteria.
* Verification plans.
* Migration plans.
* Rollback plans.

### 7.4 Interaction artifacts

* Assignment packets.
* Worker result packets.
* Research result packets.
* Review packets.
* Acceptance records.
* Escalation packets.
* Decision records.
* Manager inbox entries.
* Architect review requests.
* Founder approval requests.

### 7.5 Evidence artifacts

* Test results.
* CI results.
* Build results.
* Data citations.
* Research sources.
* Dry-run outputs.
* API responses.
* Deployment evidence.
* Production verification results.
* Screenshots where required.
* Logs.
* Performance measurements.
* Security scan results.

### 7.6 Operational knowledge artifacts

* Incident records.
* Root-cause analyses.
* Durable lessons.
* Non-regression requirements.
* Known failure modes.
* Approved legacy lessons.

### 7.7 Release artifacts

* Release records.
* Deployment records.
* Environment records.
* Rollback targets.
* Production verification records.
* Release approvals.

---

## 8. Artifact Ownership and Contribution

### 8.1 Single ownership

Each canonical artifact class MUST have exactly one owner.

Ownership is defined by active governance records and RoleSpecs.

### 8.2 Contributor access

Contributors may create or modify records only through an owner-approved workflow.

The POS MUST distinguish:

* Owner.
* Contributor.
* Reviewer.
* Approver.
* Reader.
* Automation.

### 8.3 POS ownership

The POS itself owns only:

* Canonical record storage.
* Schema definitions.
* Record identity.
* History.
* Mechanical validation results.
* Generated views.
* Audit logs.
* Automation state.

The POS does not own the substantive decisions stored within those records.

### 8.4 Attribution

Every judgment-bearing record MUST identify:

* Originating role.
* Originating instance.
* Human authority, where applicable.
* Timestamp.
* Applicable RoleSpec version.
* Assignment or decision reference.
* Evidence references.

---

## 9. Work-Item Model

The POS MUST maintain work items independently from artifacts.

### 9.1 Required work-item fields

Each work item MUST include:

* Stable ID.
* Title.
* Purpose.
* Current status.
* Parent objective or milestone.
* Risk class.
* Priority, when assigned by an authorized role.
* Owner or assigned role.
* Dependencies.
* Blockers.
* Included scope.
* Excluded scope.
* Acceptance-criteria reference.
* Assignment reference.
* Evidence references.
* Review reference.
* Decision references.
* Repository references.
* Created timestamp.
* Last-updated timestamp.
* Closure reason where applicable.

### 9.2 Work-item state model

The POS MUST distinguish, at minimum:

* Proposed.
* Ready.
* Assigned.
* In progress.
* Blocked.
* Worker complete.
* Review pending.
* Changes requested.
* Accepted.
* Verified.
* Deployment pending.
* Deployed.
* Production verified.
* Closed.
* Rejected.
* Cancelled.
* Superseded.

The exact implementation may use a smaller normalized state machine with explicit evidence dimensions, but it MUST preserve these distinctions.

### 9.3 State-transition validation

The POS MUST mechanically validate allowed transitions.

Examples:

* `Proposed → Ready` requires required planning fields.
* `Ready → Assigned` requires an assignment packet.
* `Worker complete → Review pending` requires a result packet.
* `Review pending → Accepted` requires an acceptance record.
* `Accepted → Verified` requires required verification evidence.
* `Verified → Deployed` requires deployment evidence and authorization.
* `Deployed → Production verified` requires production verification evidence.

### 9.4 No inflated completion

The POS MUST NOT allow:

* Local completion to be represented as deployment.
* A merged PR to be represented as production verification.
* A passing test suite to be represented as acceptance where judgment review is required.
* A worker claim to be represented as verified evidence without supporting artifacts.

---

## 10. Assignment Requirements

### 10.1 Assignment record

Every temporary-role assignment MUST be represented as a structured record.

It MUST include:

* Assignment ID.
* Work-item ID.
* Assigning role.
* Assigned role or Execution Profile.
* Purpose.
* Included scope.
* Excluded scope.
* Required inputs.
* Expected outputs.
* Completion criteria.
* Applicable risk class.
* Acceptance authority.
* Context ceiling.
* Tool and repository permissions.
* Resource limits where applicable.
* Escalation triggers.
* Termination conditions.
* Base commit or source version where applicable.

### 10.2 Mechanical completeness

The POS MUST reject assignment creation when required fields are missing.

### 10.3 Substantive adequacy

The POS MUST NOT claim that an assignment is well designed merely because required fields exist.

The quality of:

* Scope.
* Acceptance criteria.
* Technical direction.
* Risk classification.
* Context selection.

requires authorized judgment review.

### 10.4 Temporary-role closure

Every temporary assignment MUST end in one of:

* Accepted.
* Rejected.
* Cancelled.
* Superseded.
* Resource limit reached.
* Unrecoverable failure.
* Explicitly abandoned with reason.

Indefinitely open temporary assignments are not permitted.

---

## 11. Worker and Research Result Records

### 11.1 Structured result packets

Workers MUST submit structured result records rather than relying only on chat summaries.

A result record MUST include:

* Assignment ID.
* Worker identity.
* Claimed outcome.
* Changed artifacts.
* Commit or branch references.
* Tests run.
* Evidence references.
* Scope deviations.
* Unresolved issues.
* New risks.
* Recommended next action.
* Whether the result is local, reviewed, deployed, or production verified.

### 11.2 No self-verification

A worker result is a claim, not independent proof.

The POS MUST distinguish:

* Worker-reported result.
* Machine-verified evidence.
* Reviewer conclusion.
* Acceptance decision.
* Production verification.

### 11.3 Research results

Research result records MUST include:

* Research question.
* Scope.
* Sources.
* Date of research.
* Findings.
* Confidence.
* Contradictions.
* Unsupported assumptions.
* Recommendation, where authorized.
* Manager disposition.
* Whether the result has been adopted as canonical knowledge.

Research does not become canonical project truth merely because a worker reports it.

---

## 12. Review and Acceptance

### 12.1 Review records

The POS MUST support a review artifact distinct from:

* Worker results.
* Decisions.
* Acceptance.
* Deployment authorization.

### 12.2 Review contents

A review record MUST include:

* Reviewed assignment or artifact.
* Reviewer identity.
* Applicable criteria.
* Evidence examined.
* Findings.
* Defects.
* Risk assessment.
* Outcome.
* Required changes.
* Unresolved uncertainties.

### 12.3 Acceptance records

Acceptance is a judgment-bearing action.

An acceptance record MUST include:

* Acceptance authority.
* Work item.
* Criteria reference.
* Review references.
* Evidence references.
* Accepted scope.
* Excluded or deferred scope.
* Conditions.
* Date.
* Applicable risk policy.

### 12.4 Risk-based separation

The POS MUST mechanically enforce the acceptance separation required by the Governance Handbook.

For example:

* Low-risk work may permit assigner acceptance.
* Higher-risk work may require an independent review.
* Protected work may require Founder approval.
* The assigning worker MUST NOT accept its own output.

### 12.5 Criteria ownership

The POS stores and validates acceptance-criteria records.

It does not author them.

Acceptance criteria are authored or approved by the authority defined in relevant RoleSpecs, technical standards, and interaction contracts.

---

## 13. Decision and Escalation Records

### 13.1 Decision record

Every material decision MUST be represented by a structured decision record.

Required fields:

* Decision ID.
* Decision class.
* Question.
* Decision authority.
* Status.
* Options considered.
* Decision.
* Rationale.
* Evidence.
* Affected artifacts.
* Effective date.
* Reversibility.
* Review date where applicable.
* Supersession reference.

### 13.2 Decision states

Supported states MUST include:

* Proposed.
* Pending consultation.
* Pending approval.
* Approved.
* Rejected.
* Deferred.
* Superseded.
* Revoked.

### 13.3 Authority validation

The POS MUST validate that the actor recording a DECIDE action holds DECIDE authority for that decision class under the active governance and RoleSpec versions.

A mismatch MUST be blocked for protected decisions and flagged for review for lower-risk records.

### 13.4 Escalation records

Escalation records MUST include:

* Exact question.
* Decision class.
* Escalation recipient.
* Trigger.
* Evidence.
* Recommendation where authorized.
* Safe default.
* Blocking behavior.
* Response status.

### 13.5 No silent conflict resolution

Where evidence, decisions, or canonical artifacts conflict, the POS must create or require a conflict record.

It MUST NOT choose the “most likely” interpretation autonomously.

---

## 14. Evidence Model

### 14.1 Typed evidence

Evidence MUST be typed.

Examples:

* `test_result`
* `ci_result`
* `commit_reference`
* `pull_request_reference`
* `research_source`
* `data_snapshot`
* `api_response`
* `deployment_record`
* `production_verification`
* `security_scan`
* `performance_measurement`
* `manual_observation`

### 14.2 Evidence metadata

Evidence records MUST include:

* Source.
* Timestamp.
* Producer.
* Related work item or decision.
* Environment.
* Version or commit where applicable.
* Integrity reference where applicable.
* Confidence or verification status.

### 14.3 Evidence completeness

The POS MUST detect missing evidence required by:

* Risk policy.
* Interaction specifications.
* RoleSpecs.
* Acceptance criteria.
* Release policy.

### 14.4 Evidence appropriateness

The POS MAY mechanically validate obvious type requirements.

Examples:

* Deployment claims require deployment evidence.
* Production verification claims require environment-specific verification.
* CI claims require a CI result.
* Research claims require source references.

The POS MUST NOT determine whether evidence is persuasive when interpretation is required.

---

## 15. Project State and Roadmap

### 15.1 Canonical state

The POS MUST maintain a compact canonical current-state record containing:

* Current approved objective.
* Current milestone.
* Active work items.
* Blockers.
* Pending decisions.
* Pending reviews.
* Current deployment.
* Current verified release.
* Next approved actions.
* Last reconciliation timestamp.

### 15.2 Roadmap

The roadmap MUST distinguish:

* Proposed milestones.
* Approved milestones.
* Active milestone.
* Deferred milestones.
* Completed milestones.
* Cancelled milestones.

### 15.3 Roadmap authority

The POS records roadmap decisions.

It does not prioritize or approve the roadmap.

### 15.4 Generated summaries

The POS SHOULD generate concise summaries for:

* Founder.
* Project Manager.
* Architect.
* Worker inboxes.
* Release review.

Generated summaries MUST reference canonical records rather than duplicate their full contents.

---

## 16. RoleSpec and Execution Profile Support

### 16.1 RoleSpec registration

The POS MUST store:

* RoleSpec identity.
* Version.
* Status.
* Owner.
* Effective date.
* Governance dependencies.
* Authority table.
* Artifact ownership.
* Regression results.
* Supersession history.

### 16.2 Structural validation

The POS MUST validate RoleSpecs against RES-002 for:

* Required sections.
* Required metadata.
* Semantic-version format.
* Unique active version.
* Artifact-owner conflicts.
* Duplicate DECIDE authority.
* Missing rehydration references.
* Missing regression-test references.
* Missing interaction contracts.

### 16.3 Judgment boundaries

The POS MUST NOT claim to determine:

* Whether a role’s organizational purpose is coherent.
* Whether its authority is wise.
* Whether a role should exist.
* Whether its context ceiling is appropriate.
* Whether its regression scenarios are sufficient.

Those require structural and authority review.

### 16.4 Execution Profiles

The POS MUST support lightweight temporary-role profiles containing:

* Purpose.
* Scope.
* Authority.
* Inputs.
* Outputs.
* Forbidden actions.
* Acceptance owner.
* Resource limits.
* Termination conditions.

---

## 17. Rehydration and Instance Support

### 17.1 Rehydration bundles

The POS MUST be able to produce a bounded rehydration bundle for each permanent role.

The bundle MUST follow the active RoleSpec’s ordered rehydration sequence.

### 17.2 Freshness

The POS MUST indicate:

* Record versions.
* Last-updated times.
* Whether required records are missing.
* Whether a generated view is stale.
* Whether conflicting canonical records exist.

### 17.3 Incomplete rehydration

If required rehydration inputs are missing or conflicting, the POS MUST mark the bundle incomplete.

It MUST NOT silently fill gaps with:

* Archived chat summaries.
* Legacy project content.
* Superseded records.
* Worker prose.
* Guessed defaults.

### 17.4 Instance Instruction Package

The POS SHOULD support deterministic generation of an Instance Instruction Package containing:

* Active role identity.
* Applicable RoleSpec content.
* Applicable global governance.
* Current task.
* Relevant state.
* Context ceilings.
* Prohibitions.
* Escalation rules.
* Interaction contracts.
* Source-version references.

The compiler MAY be deferred during bootstrap, but the POS data model MUST not prevent later implementation.

---

## 18. Interaction and Message Routing

### 18.1 Structured routing

Assignments, results, reviews, escalations, and decisions MUST be routed through structured records tied to project artifacts.

### 18.2 Manager inbox

The POS SHOULD generate a concise manager inbox containing:

* New worker results.
* Pending reviews.
* Conflicts.
* Blockers.
* Decisions awaiting manager action.
* Stale assignments.
* Failed validations.

### 18.3 No untracked lateral worker coordination

Temporary workers MUST NOT create authoritative work dependencies through untracked direct coordination.

Where worker-to-worker communication is allowed, it must:

* Be authorized by the assignment.
* Be recorded.
* Remain visible to the assigning role.
* Not grant expanded authority.

### 18.4 Chat is not the record

Chat may be used for reasoning and interaction.

Material outputs must be externalized into POS records before they are treated as project truth.

---

## 19. Automation Requirements

### 19.1 Deterministic operations

Automation SHOULD perform:

* Schema validation.
* ID uniqueness checks.
* Version checks.
* Status-transition validation.
* Dependency validation.
* Ownership-conflict detection.
* Authority-reference validation.
* Evidence-presence checks.
* Generated-view creation.
* Generated-view staleness detection.
* GitHub merge reconciliation.
* Commit existence verification.
* CI-state reconciliation.
* Assignment staleness detection.
* Pending-decision reminders.
* Release-record reconciliation.

### 19.2 No judgment writes

Automation MUST NOT create judgment-bearing decisions such as:

* Architecture approval.
* Work acceptance.
* Risk acceptance.
* Strategy approval.
* Product prioritization.
* Role approval.

### 19.3 Fail-closed protected actions

Automation MUST block protected actions when deterministic prerequisites are absent.

Examples:

* Missing deployment approval.
* Invalid RoleSpec authority.
* Missing required review.
* Missing required acceptance record.
* Unauthorized threshold change.
* Duplicate active artifact ownership.

### 19.4 Detection for lower-risk ambiguity

For lower-risk inconsistencies that cannot be safely blocked without excessive friction, automation MAY:

* Flag.
* Open a reconciliation item.
* Notify the Manager.
* Prevent final closure while allowing unaffected work to continue.

---

## 20. GitHub and Repository Integration

### 20.1 Repository references

The POS MUST support references to:

* Repository.
* Branch.
* Commit.
* Pull request.
* Issue.
* Tag.
* Release.
* CI run.
* Artifact.

### 20.2 Objective reconciliation

The POS SHOULD retrieve objective repository state automatically.

Examples:

* PR merged or open.
* Commit exists.
* Default branch head.
* CI status.
* Changed files.
* Release tag.

### 20.3 No duplicate manual state

Information available reliably from GitHub SHOULD NOT require repeated manual entry.

### 20.4 Multiple repositories

The POS MUST preserve repository namespaces and MUST NOT conflate:

* ASA 2 repositories.
* Legacy ASA repositories.
* Other company projects.
* External dependencies.

### 20.5 Canonical project repository

ASA 2 governance and POS records SHOULD live in one approved canonical repository or one clearly defined governance repository.

The exact repository structure is an architecture decision.

---

## 21. Legacy Context Boundary

### 21.1 No broad legacy ingestion

The POS MUST NOT automatically import the legacy ASA backlog, patch history, state files, or architecture as active ASA 2 truth.

### 21.2 Approved legacy packet classes

Legacy information may enter ASA 2 only through approved, bounded artifacts such as:

* Known Failure Modes.
* Safety Lessons.
* Financial-Loss Non-Regression Requirements.
* Approved Strategy Specifications.
* Provider Quirk Records.
* Behavioral Test Fixtures.
* Explicit Preserve/Redesign/Defer/Delete decisions.

### 21.3 Provenance

Every legacy-derived artifact MUST identify:

* Source.
* Curator.
* Date.
* Scope.
* Approval status.
* Whether it is historical evidence, current requirement, or non-regression guidance.

### 21.4 No silent promotion

Legacy content cannot become an active requirement without an explicit adoption decision.

---

## 22. Incident and Durable Knowledge Management

### 22.1 Incident records

Incident records MUST include:

* Trigger.
* Severity.
* Affected systems.
* Affected roles or artifacts.
* Timeline.
* Evidence.
* Immediate containment.
* Root cause, when determined.
* Corrective actions.
* Non-regression outcome.
* Related decisions.

### 22.2 Lessons

Durable lessons MUST be distinct from raw incident logs.

A lesson record should contain:

* Generalized lesson.
* Applicability.
* Evidence.
* Approved behavior change.
* Review date.
* Supersession status.

### 22.3 Knowledge-bloat control

Not every observation becomes a durable lesson.

A lesson should be retained only when it materially affects:

* Future decisions.
* Safety.
* Correctness.
* Architecture.
* Provider selection.
* Strategy behavior.
* Non-regression.

---

## 23. Release and Deployment Truth

### 23.1 Release record

Each release record MUST include:

* Release ID.
* Included work items.
* Commit or tag.
* Approved environment.
* Approval record.
* Deployment record.
* Verification plan.
* Rollback target.
* Status.

### 23.2 Deployment record

Each deployment record MUST include:

* Environment.
* Commit.
* Start time.
* Completion time.
* Result.
* Platform reference.
* Actor.
* Related release.

### 23.3 Production verification

Production verification MUST be represented separately from deployment success.

It MUST include:

* Environment.
* Commit identity.
* Verification actions.
* Results.
* Evidence.
* Known limitations.
* Verifier.
* Timestamp.

### 23.4 Split deployment truth

Where multiple services or environments exist, the POS MUST track them independently.

A successful deployment of one service MUST NOT imply project-wide deployment success.

---

## 24. Security and Access Control

### 24.1 Least privilege

Access MUST be restricted by:

* RoleSpec.
* Execution Profile.
* Assignment.
* Artifact class.
* Environment.
* Tool.
* Duration.

### 24.2 Credential handling

The POS MUST NOT expose raw credentials in:

* RoleSpec bundles.
* Worker packets.
* Generated summaries.
* Audit records.
* Logs.

Credential brokerage may be implemented separately.

### 24.3 Revocation

Access for any instance or automation identity MUST be revocable without editing the RoleSpec.

### 24.4 Untrusted content

External content MUST be labeled as data, not instruction.

The POS MUST preserve a trust boundary between:

* Governance instructions.
* Role instructions.
* Project records.
* Worker content.
* Research sources.
* External data.

### 24.5 Protected writes

Protected artifact classes MUST require the authorization defined by governance.

Examples:

* Constitution.
* Active RoleSpecs.
* Risk policy.
* Strategy thresholds.
* Deployment approvals.
* Artifact ownership.
* Security policy.

---

## 25. Auditability

### 25.1 Immutable history

Canonical judgment-bearing records MUST preserve immutable history.

Corrections are represented as:

* Superseding records.
* Amendments.
* Revocations.
* Explicit correction entries.

### 25.2 Point-in-time reconstruction

The POS MUST support reconstruction of:

* Active governance versions.
* Active RoleSpecs.
* Current milestone.
* Work-item state.
* Decisions.
* Architecture contracts.
* Deployment state.

for a specified historical point.

### 25.3 Actor traceability

Every write MUST identify:

* Actor type.
* Actor identity.
* Instance identity where applicable.
* Time.
* Source version.
* Related assignment or automation job.

### 25.4 Violation records

Permission violations, invalid transitions, authority conflicts, and attempted protected writes MUST be logged.

---

## 26. Reliability, Backup, and Recovery

### 26.1 Durability

The POS MUST protect canonical organizational state from loss under ordinary infrastructure failure.

### 26.2 Version control

Canonical governance records SHOULD be version-controlled in Git where practical.

### 26.3 Backup

The POS MUST provide a tested backup and restoration path before it becomes the sole organizational record.

### 26.4 Restore validation

Restoration procedures MUST verify:

* Record integrity.
* History.
* Current state.
* Ownership references.
* Generated-view reproducibility.

### 26.5 Provider independence

Canonical truth SHOULD remain exportable independently of a single SaaS or hosting provider.

---

## 27. Performance and Usability

### 27.1 Rehydration usability

A fresh permanent-role instance must be able to retrieve required project state within one working session.

### 27.2 Scoped retrieval

The POS MUST support narrow retrieval by:

* Role.
* Work item.
* Milestone.
* Decision.
* Artifact class.
* Repository.
* Environment.
* Date.
* Status.

### 27.3 Concise summaries

Generated human summaries SHOULD be compact and decision-oriented.

The POS SHOULD prevent routine users from needing to inspect raw full-history records.

### 27.4 Large artifact handling

The POS SHOULD reference large artifacts rather than duplicating them across packets and views.

---

## 28. Bootstrap Requirements

The initial POS does not need to implement every future feature.

### 28.1 Minimum viable POS

The bootstrap version MUST support:

* Structured current state.
* Structured roadmap.
* Work items.
* Dependencies.
* Assignment records.
* Worker results.
* Decision records.
* Review records.
* Acceptance records.
* RoleSpec registration.
* Evidence references.
* GitHub references.
* Generated current-state and manager-inbox views.
* Mechanical validation.
* Audit history.
* Backup through Git.

### 28.2 Bootstrap may defer

The bootstrap version MAY defer:

* Full web UI.
* Multi-organization support.
* Advanced analytics.
* Automated Instance Instruction Package compilation.
* Complex permission brokerage.
* Real-time notifications.
* Cross-provider backup automation.
* Semantic search.
* Autonomous reconciliation.

### 28.3 Bootstrap safety

Deferred features MUST NOT be replaced by unsafe assumptions.

For example:

* If hard access enforcement is not complete, protected writes still require reviewed Git changes.
* If automated compilation is deferred, instance packages must be manually generated from canonical sources using a controlled template.
* If deployment integration is deferred, deployment evidence must still be recorded manually.

---

## 29. Versioning

### 29.1 POS software versioning

The POS implementation maintains its own software release version.

### 29.2 Hosted artifact versioning

Hosted governance and technical artifacts retain their own version schemes.

### 29.3 Schema versioning

Structured record schemas MUST be versioned.

### 29.4 Migration

Schema migrations MUST:

* Preserve history.
* Be reversible or have rollback guidance.
* Include validation.
* Not silently discard fields.
* Record migration provenance.

---

## 30. Validation Categories

The POS MUST distinguish among:

### 30.1 Schema validation

Examples:

* Required fields.
* Types.
* Enumerations.
* Format.

### 30.2 Referential validation

Examples:

* Referenced work item exists.
* RoleSpec exists.
* PR exists.
* Evidence exists.
* Dependency exists.

### 30.3 Consistency validation

Examples:

* One active RoleSpec per role.
* One artifact owner.
* No duplicate ID.
* No contradictory current deployment record.

### 30.4 Policy validation

Examples:

* Required review for risk class.
* Required Founder approval.
* Allowed state transition.
* Protected write authorization.

### 30.5 Judgment review

Examples:

* Criteria adequacy.
* Research correctness.
* Architecture quality.
* Risk acceptability.
* Product alignment.

Judgment review is never represented as a successful mechanical validation.

---

## 31. Generated Views

The bootstrap POS SHOULD generate:

1. `CURRENT_STATE.md`
2. `ROADMAP.md`
3. `MANAGER_INBOX.md`
4. `PENDING_DECISIONS.md`
5. `ACTIVE_WORK.md`
6. `RELEASE_STATUS.md`
7. `ROLE_REGISTRY.md`
8. `VALIDATION_REPORT.md`

These files are views.

Each MUST include:

* Canonical source reference.
* Generation time.
* Schema or generator version.
* Warning against manual editing.
* Conflict or stale-state banner when applicable.

---

## 32. Recommended Repository Shape

This section is non-binding and subject to Architect design.

```text
/project/
  schemas/
  state/
    current_state.yaml
    roadmap.yaml
  roles/
    permanent/
    execution_profiles/
  work/
    items/
    assignments/
    results/
    reviews/
    acceptances/
  decisions/
  architecture/
  interactions/
  evidence/
  incidents/
  lessons/
  releases/
  deployments/
  legacy_boundary/
  generated/
  automation/
```

The implementation may use a database while preserving an equivalent exportable structure.

---

## 33. Acceptance Requirements for POS v0.2 Design

Before a POS implementation is approved, the design must demonstrate:

1. Structured canonical records.
2. Generated views.
3. Role and artifact ownership validation.
4. Work-item state transitions.
5. Assignment/result/review/acceptance separation.
6. Decision authority checking.
7. GitHub reference handling.
8. Evidence typing.
9. Current-state reconstruction.
10. Rehydration support.
11. Legacy-boundary enforcement.
12. Audit history.
13. Backup and restore.
14. Mechanical-versus-judgment validation separation.
15. Protected-action fail-closed behavior.

---

## 34. Open Questions

### OQ-34.1

What structured storage format should be used for the bootstrap POS?

Candidate approaches include:

* Git-backed YAML.
* Git-backed JSON.
* SQLite plus generated exports.
* Hybrid Git plus database.

This is an Architect decision.

### OQ-34.2

Should GitHub Issues be canonical work items, or should they be mirrors of POS-owned work records?

The recommended direction is POS-owned structured records with GitHub references or generated issues, but this requires architecture review.

### OQ-34.3

Which protected actions must be enforced technically in the bootstrap release versus enforced through reviewed pull requests?

### OQ-34.4

Which generated views are required before the Project Manager begins operating?

### OQ-34.5

Should the Instance Instruction Package compiler be included in the first POS milestone or added after PM and Architect RoleSpecs stabilize?

### OQ-34.6

What organization-wide risk classification and approval matrix will the POS enforce?

### OQ-34.7

Which Interaction Specifications must be complete before POS implementation begins?

Likely initial contracts:

* Assignment Packet.
* Worker Result Packet.
* Review Record.
* Acceptance Record.
* Decision Record.
* Escalation Packet.
* Research Result Packet.

---

## 35. Draft Disposition

This document remains a draft pending:

1. Independent critic review.
2. Founder review.
3. Compatibility review against RES-001 and RES-002.
4. Compatibility review against the Project Manager RoleSpec.
5. Compatibility review against the System Architect RoleSpec.
6. Approval of the initial risk classification.
7. Approval of the initial Interaction Specification set.
8. Architect recommendation on bootstrap storage and GitHub integration.
9. Definition of POS v0.1 implementation acceptance criteria.

---

## Appendix A: Core Design Principles

| Principle                               | POS Interpretation                              |
| --------------------------------------- | ----------------------------------------------- |
| Project truth lives outside chat        | Structured records are canonical                |
| Automation should be boring             | Deterministic validation and generation only    |
| Roles decide; POS records               | No organizational judgment authority            |
| One fact, one owner                     | Canonical ownership validation                  |
| Evidence before status                  | Status transitions require evidence             |
| Completion is not deployment            | Distinct evidence states                        |
| Legacy knowledge crosses through a gate | Curated boundary artifacts only                 |
| Temporary roles are bounded             | Assignments and termination conditions          |
| Manager context remains concise         | Generated manager inbox and current-state views |
| History must remain reconstructable     | Immutable audit and version history             |

---

## Appendix B: Prohibited POS Anti-Patterns

| Anti-Pattern                                    | Reason                                  |
| ----------------------------------------------- | --------------------------------------- |
| AI librarian deciding what is true              | Reintroduces judgment and hallucination |
| Markdown files as separately maintained truth   | Creates drift                           |
| Manager manually editing multiple state files   | Multiplies inconsistency                |
| Worker result automatically marked verified     | Confuses claim with proof               |
| PR merged automatically marked production-ready | Skips review and deployment evidence    |
| Full legacy project import                      | Reintroduces entropic state             |
| POS approving architecture or research          | Infrastructure becomes authority        |
| Automatic approval on non-response              | Bypasses human rights                   |
| Duplicate work-item systems                     | Creates split-brain backlog             |
| Unstructured inbox files                        | Recreates chat-based entropy            |
| Permanent temporary assignments                 | Creates undocumented roles              |
| POS storing secrets in project records          | Expands security exposure               |
| Generated views manually edited                 | Breaks reproducibility                  |

---

## Appendix C: v0.1 to v0.2 Major Changes

| v0.1 Concept                                                     | v0.2 Disposition                                                         |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------ |
| POS supports roles as users                                      | Retained and clarified                                                   |
| PM writes canonical backlog and decision logs                    | Replaced with POS-owned records and role-attributed changes              |
| POS may validate role action outside permissions broadly         | Narrowed to deterministic authority and policy checks                    |
| Full legacy artifact ingestion                                   | Removed; replaced by curated legacy boundary                             |
| Worker inbox                                                     | Retained as structured assignment/result routing                         |
| Decision log                                                     | Expanded into decision and escalation records                            |
| Evidence required for completion                                 | Retained with typed evidence and evidence-state separation               |
| Role instantiation bundle                                        | Expanded into bounded rehydration and future instruction-package support |
| Automation computes drift                                        | Narrowed to objective drift signals and conflict detection               |
| GitHub integration                                               | Expanded to objective reconciliation                                     |
| Detection acceptable for bootstrap                               | Protected actions fail closed; lower-risk inconsistencies may be flagged |
| POS enforces review-ready requires Architect criteria and review | Generalized to policy- and risk-driven review requirements               |
| Temporary roles indirectly handled                               | Formalized through Execution Profiles                                    |
