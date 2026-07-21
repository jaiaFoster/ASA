# GOV-AMD-001

## Constitutional Amendment Register

### Status: Draft v0.2 — revised per Supplementary Audit

**Revision note:** This version resolves all items in the Supplementary Audit's Section 6 recommendation (binding-status ambiguity, the RISK-001/tiering conflict, the two internal contradictions, and the missing lifecycle standard) plus Findings 7–10. Each changed amendment carries an inline `Audit disposition` note identifying what changed and why, so the revision is itself auditable against the document it responds to.

### Applies To

- RES-001
- RES-002
- PM-SPEC
- ARCH-SPEC
- POS-RS
- RISK-001

---

## 0. Amendment Lifecycle Standard

*(New section. Resolves Finding 1 [Critical], Finding 2, and the audit's Section 4 "Missing Governing Document" finding. This register does not get to demand rigor of every other document while leaving its own operating rules implicit — the same discipline RES-002 applies to RoleSpecs applies here to amendments.)*

### 0.1 Binding Model

**GOV-AMD-001-REQ-0.1.1:** This register adopts **Model A — accepted-on-entry**. An amendment is binding on the organization the moment its `Status` field (§0.2) is set to `Accepted`, not merely on eventual incorporation into a future major revision. The frozen v2 text of any document listed in "Applies To" is read as amended by every `Accepted` entry in this register until a superseding major revision (e.g., RES-001 v3.0) is published.

**GOV-AMD-001-REQ-0.1.2:** `Draft` and `Proposed` amendments are not binding and impose no obligation on any role. Only `Accepted` amendments alter organizational behavior.

**GOV-AMD-001-REQ-0.1.3:** Publication of a major revision incorporating an `Accepted` amendment changes that amendment's status to `Incorporated`; the amendment remains in this register as historical record (consistent with Amendment 012's treatment of constitutional documents as historical artifacts) but the incorporating document's text, not the amendment text, governs going forward.

**Rationale:** Given that several amendments here fix known, already-identified gaps in the frozen v2 text (Amendment 009 vs. the first audit's Defect #3; Amendment 010 vs. RISK-001's existing floor rule), Model B (binding only at incorporation) would leave identified defects live and unfixed for an indefinite, unscheduled period. Model A closes the gap immediately upon acceptance while preserving the audit trail Model B was also trying to protect.

### 0.2 Required Fields

**GOV-AMD-001-REQ-0.2.1:** Every amendment in this register MUST declare:

| Field | Description |
|---|---|
| `amendment_id` | Sequential, permanent, never reused (mirrors RES-002 §19.2's no-reuse rule for RoleSpec versions). |
| `status` | `Proposed` \| `Accepted` \| `Rejected` \| `Superseded` \| `Incorporated` |
| `proposer` | Individual or role proposing the amendment. |
| `date` | Date of the status currently recorded. |
| `risk_class` | Per RISK-001 §8, the R-class of the amendment itself (an amendment to governance text is, per RISK-001 §8.3, at minimum R4; see §0.2.2). |
| `applies_to` | Which document(s) in the "Applies To" list this amendment modifies. |
| `binding_scope` | Per §0.1: confirms the amendment is governed by the accepted-on-entry model; no amendment may opt out of §0.1. |

**GOV-AMD-001-REQ-0.2.2:** Per RISK-001 §8.3, every amendment to this corpus is at minimum R4 (Organizational Governance); an amendment touching authority hierarchy, canonical-truth model, or the fixed roles/founder relationship itself is R5 (Constitutional) and requires the Constitutional Review defined in RISK-001 §11.4. Each amendment below states its Risk Class explicitly against this rule.

### 0.3 Acceptance Authority

**GOV-AMD-001-REQ-0.3.1:** Acceptance authority for any amendment is the Founder, consistent with RISK-001 §10.1's R4 row (Founder approval mandatory, no delegation).

**GOV-AMD-001-REQ-0.3.2:** Independent Review and Structural Review (RISK-001 §10.1's R4 row, RES-002 §20) are required **per amendment**, at the point of acceptance — not deferred to the eventual major-revision incorporation event. An `Accepted` amendment without a recorded review is invalid and must be treated as `Proposed` until review is completed.

**GOV-AMD-001-REQ-0.3.3:** An amendment classified R5 under §0.2.2 additionally requires Constitutional Review (RISK-001 §11.4) before it may be marked `Accepted`.

### 0.4 Conflict Resolution

**GOV-AMD-001-REQ-0.4.1:** Where two amendments in this register make incompatible claims about the same artifact or the same time period (as Amendments 007 and 011 did prior to this revision — see their entries below), the conflict MUST be resolved by revising one or both amendments before either may be marked `Accepted`. Two contradictory `Accepted` entries may not coexist.

**GOV-AMD-001-REQ-0.4.2:** A conflict discovered after both amendments are already `Accepted` is an incident (POS-RS §7.7), not a routine edit; resolution requires a new amendment explicitly superseding the narrower of the two, recorded with `status: Superseded` on the amendment being replaced.

### 0.5 Promotion Criteria (Register → Major Revision)

**GOV-AMD-001-REQ-0.5.1:** A major revision (e.g., RES-001 v3.0) incorporating this register's `Accepted` amendments MAY be proposed by the Architect or Founder when either: (a) an `Accepted` amendment's presence in the register, rather than in the base document, is causing rehydration cost or ambiguity for role instances (RES-002 §14, §15.4 packet-discipline concerns), or (b) a fixed review interval (proposed: every ten `Accepted` amendments, or annually, whichever comes first — see §12 Open Questions) has elapsed.

**GOV-AMD-001-REQ-0.5.2:** Promotion to a major revision requires Founder approval and full RISK-001 R4/R5 governance per the amendment's own classification, applied to the revision as a whole; it does not re-litigate individually already-`Accepted` amendments' substance, only their consolidation and wording.

---

## 1. Executive Summary of This Revision

This revision does not change the register's core purpose (freeze v2, route changes through numbered amendments, publish v3 later). It closes the specific gaps identified in the Supplementary Audit:

- §0 above resolves Finding 1 (binding status) and the audit's Section 4 finding (missing lifecycle standard).
- Amendment 001 is rewritten to reconcile with RISK-001 (Finding 2) and to actually define its three tier processes (Finding 3).
- Amendment 006 is rewritten to state explicitly that it changes document-tier labeling only, not RISK-001 classification for any specific change.
- Amendment 009 is rewritten with risk-tier scoping and an emergency-action exception (Finding 4).
- Amendment 011 is rewritten with a bootstrap carve-out reconciling it with Amendment 007 (Finding 5).
- Amendment 003 is amended to state which truth-domain a Founder Decision Record occupies (Finding 6).
- Amendment 008 is rewritten to name R4 explicitly (Finding 7).
- Amendments 005 and 010 are reworded as reaffirmations with pointers rather than independent restatements (Finding 8).
- Amendment 012 is rewritten to cross-reference Amendment 001's Tier A definition and to disambiguate from RISK-001's separate, work-item-level use of "Constitutional" (Finding 9).
- Amendment 002 gains one sentence mapping the Query Layer onto POS-RS's existing actor taxonomy (Finding 10).

---

# Amendment 001

## Split Constitutional and Engineering Governance

| Field | Value |
|---|---|
| `amendment_id` | 001 |
| `status` | Proposed *(not yet Accepted — see §0.3.2; requires Independent + Structural Review before acceptance)* |
| `proposer` | Founder |
| `risk_class` | R4 (document-tier labeling and process definition only; see reconciliation clause below for why it does not rise to R5) |
| `applies_to` | RES-001, RES-002, PM-SPEC, ARCH-SPEC, POS-RS, RISK-001 (labeling only) |

### Reason

The current governance corpus treats slow-changing constitutional principles and fast-changing engineering specifications as the same class of document. This creates unnecessary governance overhead while encouraging informal bypasses for routine engineering changes.

### Amendment

The governance corpus is divided into three **document tiers**, each with a defined process below.

**Tier A — Constitutional Principles.** Rarely amended. Examples: the Constitution, Authority Hierarchy, Organizational Philosophy, Decision Rights.
*Process:* Any change requires R5 classification per RISK-001 §8.3 regardless of the specific clause changed, full RISK-001 §10.1 R5 governance floor, and Constitutional Review (RISK-001 §11.4).

**Tier B — Governance Standards.** Occasionally amended. Examples: RES-001, RES-002, RISK-001.
*Process:* Default classification is R4 per RISK-001 §8.3. Full RISK-001 §10.1 R4 floor applies (Founder approval, Independent Review, Structural Review) for every change, without exception, since these documents define the mechanisms every other document depends on.

**Tier C — Engineering Specifications.** Frequently revised. Examples: PM-SPEC, ARCH-SPEC, POS-RS.
*Process:* A change classified, under RES-002 §19's existing MAJOR/MINOR/PATCH graduation, as **PATCH or MINOR and not touching Decision Rights (RES-002 §8), Artifact Ownership (RES-002 §11), or a Forbidden Action (RES-002 §10)**, may proceed under the lighter Tier C process: Architect or PM sign-off (per domain) plus a regression-test update (RES-002 §21), without requiring a separate R4 governance cycle for that specific change. A change classified **MAJOR under RES-002 §19**, or touching Decision Rights, Artifact Ownership, or Forbidden Actions regardless of its RES-002 version-bump size, is **R4 under RISK-001 §8 regardless of document tier** and MUST go through the full R4 floor. Tier assignment is a process-speed label for routine engineering detail; it is never a substitute for, or an override of, RISK-001's R-classification of a specific change.

**Audit disposition (Findings 2 and 3):** This amendment previously placed PM-SPEC, ARCH-SPEC, and POS-RS in a lower-friction tier with no reconciliation against RISK-001 §8's existing R4 placement of RoleSpecs and POS requirements, and deferred all three tier processes to an undefined future date. Both gaps are closed above: Tier C's process is now defined (not deferred), and it explicitly cannot be used to route an authority-, ownership-, or forbidden-action change around RISK-001's R4 floor — only genuinely routine engineering detail gets the lighter path. Tier B is stated as always-R4 with no PATCH/MINOR carve-out, since RES-001/RES-002/RISK-001 are the mechanisms other tiers depend on and do not have an analogous "routine detail" category the way a RoleSpec's responsibilities list does.

---

# Amendment 002

## Replace Policy Engine with Governance Query Layer

| Field | Value |
|---|---|
| `amendment_id` | 002 |
| `status` | Proposed |
| `proposer` | Founder |
| `risk_class` | R4 |
| `applies_to` | POS-RS (new component requirements) |

### Reason

The previous architecture introduced a runtime Policy Engine capable of producing governance conclusions. This creates ambiguity regarding delegated authority and risks software implicitly creating organizational policy. *(Note: "Policy Engine" refers to a prior architectural discussion not otherwise documented in the reviewed corpus; treated here as superseded context, not an active specification.)*

### Amendment

The Policy Engine concept is replaced with a read-only Governance Query Layer. The Query Layer:

- reads governance documents
- reads POS state
- returns applicable requirements
- reports missing evidence
- reports ambiguity
- recommends escalation targets

The Query Layer shall never:

- approve work
- reject work
- create policy
- resolve constitutional ambiguity
- substitute for Founder or delegated authority

**The Governance Query Layer is a form of Automation under RES-001 §2.5 and POS-RS §5's actor taxonomy; it does not constitute a sixth actor class alongside Founder, Permanent roles, Temporary roles, Automation, and External systems.**

**Audit disposition (Finding 10):** The final sentence above is new. It removes the ambiguity the audit identified — the Query Layer's read-only, escalate-don't-decide behavior already matches Automation's definition, but no prior draft said so explicitly.

---

# Amendment 003

## Separate Governance Truth from Operational Truth

| Field | Value |
|---|---|
| `amendment_id` | 003 |
| `status` | Proposed |
| `proposer` | Founder |
| `risk_class` | R4 |
| `applies_to` | POS-RS (artifact taxonomy clarification) |

### Reason

The previous architecture described the POS as "the source of truth." This is incomplete.

### Amendment

Two independent truth domains are established.

**Governance Truth** — maintained by the Constitution, Governance Standards, and Role Specifications. Defines what ought to happen.

**Operational Truth** — maintained by the POS. Defines what currently exists.

The Governance Query Layer correlates these two truth domains but owns neither.

**A recorded Founder Decision Record occupies both domains: it is Operational Truth in that the POS stores and dates it (POS-RS §7.6), and Governance Truth in that its content is binding on future organizational behavior until superseded (per Amendment 009). The Governance Query Layer must treat active Founder Decision Records as part of applicable governance when answering queries, not merely as historical evidence of something that happened.**

**Audit disposition (Finding 6):** The final paragraph is new. Without it, POS-RS §7.4's placement of Decision Records under POS-stored "interaction artifacts" would make them Operational Truth only under this amendment's own taxonomy — which would let a future role treat a recorded Founder decision as mere evidence rather than a binding rule, defeating Amendment 009's purpose. This closes that gap by stating explicitly that a Decision Record is dual-domain, and that the Query Layer must honor its governance weight, not just its historical existence.

---

# Amendment 004

## Governance Query Layer Must Escalate Unknowns

| Field | Value |
|---|---|
| `amendment_id` | 004 |
| `status` | Proposed |
| `proposer` | Founder |
| `risk_class` | R4 |
| `applies_to` | POS-RS (Query Layer behavior) |

### Reason

Novel organizational situations cannot always be resolved deterministically.

### Amendment

Whenever applicable governance cannot be determined uniquely, the Governance Query Layer shall:

- report the ambiguity
- identify the conflicting rules
- identify the missing information
- identify the required escalation authority (per RES-002 §16.2's requirement that escalations name a specific recipient and decision class)

It shall never infer new policy.

**Audit disposition:** No conflict found; the "required escalation authority" clause is cross-referenced to RES-002 §16.2 for precision, consistent with the audit's general preference for pointer-based rather than restated rules (Finding 8's logic applied prophylactically here).

---

# Amendment 005

## Governance Automation is Advisory

| Field | Value |
|---|---|
| `amendment_id` | 005 |
| `status` | Proposed |
| `proposer` | Founder |
| `risk_class` | R4 |
| `applies_to` | POS-RS (Query Layer / automation scope, as applied) |

### Reason

Governance software should reduce bookkeeping, not replace organizational judgment.

### Amendment

**This amendment reaffirms RES-001 §2.5 (deterministic work may be automated; judgment must remain explicitly assigned) and POS-RS §19.1–19.2 (Automation performs deterministic bookkeeping only; it does not decide) as applied specifically to the Governance Query Layer and any future governance-automation component. It does not introduce new restrictions beyond those already stated in RES-001 and POS-RS.**

For clarity in this specific application: the Query Layer may validate references, validate completeness, validate schemas, compute deterministic classifications, and detect inconsistencies. It shall not approve, reject, merge, deploy, create authority, or exercise discretion — these are restatements, for convenience, of the cited sections' existing rules, not independent rules of this amendment.

**Audit disposition (Finding 8):** Previously stated as an independent "may/shall not" list closely mirroring RES-001 §2.5 and POS-RS §19.1–19.2 without referencing them — a duplicate-source-of-truth risk (the exact pattern flagged as Defect #10 in the first audit). Now framed as an explicit reaffirmation with a pointer; the bulleted list is retained only as an illustrative restatement, explicitly marked as non-authoritative relative to the cited originals.

---

# Amendment 006

## POS-RS Document-Tier Reclassification (Labeling Only)

| Field | Value |
|---|---|
| `amendment_id` | 006 |
| `status` | Proposed |
| `proposer` | Founder |
| `risk_class` | R4 |
| `applies_to` | POS-RS (document-tier label only) |

### Reason

POS-RS describes implementation-facing requirements rather than constitutional authority, and Amendment 001 establishes a document-tier system reflecting that distinction.

### Amendment

POS-RS is labeled Tier C (Engineering Specification) under Amendment 001's document-tier system. **This labeling governs which process (per Amendment 001's Tier C definition) applies to a given future change to POS-RS; it does not alter POS-RS's Risk Class under RISK-001 §8, which remains R4 for POS-RS as a whole and for any specific change touching authority, ownership, or forbidden-action content, per Amendment 001's reconciliation clause. POS-RS's requirements remain fully authoritative; only the document-tier label, and the process available for genuinely routine changes to it, are affected by this amendment.**

**Audit disposition (Finding 2):** Previously stated that POS-RS "no longer occup[ies] the Constitutional tier," which read as a substantive downgrade conflicting with RISK-001's existing R4 placement. The revised text makes explicit that this amendment changes a process label, not a Risk Class, and that RISK-001's R4 floor is unaffected for any change that actually matters (authority, ownership, forbidden actions) — resolving the conflict the audit identified without abandoning the underlying goal of a lighter path for routine POS-RS engineering detail.

---

# Amendment 007

## Policy Implementation Roadmap

| Field | Value |
|---|---|
| `amendment_id` | 007 |
| `status` | Proposed |
| `proposer` | Founder |
| `risk_class` | R4 |
| `applies_to` | POS-RS (implementation sequencing) |

### Reason

The proposed governance architecture lacks a migration strategy.

### Amendment

Governance implementation proceeds in phases:

- **Phase 0.** Manual governance. Git. AGENTS.md maintained manually as an interim governance artifact under version control, per Amendment 011's bootstrap carve-out.
- **Phase 1.** Structured POS. Generated operational views. AGENTS.md becomes a generated view no later than this phase, per Amendment 011; manual edits to it are prohibited from Phase 1 onward.
- **Phase 2.** Validation tooling. Deterministic bookkeeping.
- **Phase 3.** Read-only Governance Query Layer.
- **Phase 4.** Additional automation only after demonstrated value.

No later phase may invalidate earlier governance requirements.

**Audit disposition (Finding 5):** Phase 0's reliance on manually-maintained AGENTS.md previously stood in direct, unreconciled contradiction with Amendment 011's blanket "generated view, not independently maintained" rule for the same artifact. The phase descriptions above now explicitly cross-reference Amendment 011's bootstrap carve-out (added there, see below) so the two amendments describe the same transition consistently rather than contradicting each other for the Phase 0–to–Phase 1 period.

---

# Amendment 008

## Governance Software Risk Tier

| Field | Value |
|---|---|
| `amendment_id` | 008 |
| `status` | Proposed |
| `proposer` | Founder |
| `risk_class` | R4 |
| `applies_to` | POS-RS, RISK-001 (application of existing classification, not a new class) |

### Reason

Governance software possesses organizational-authority amplification and therefore requires stronger verification than ordinary engineering work of similar technical surface, because a defect in it silently corrupts the enforcement of every other governance rule in the corpus.

### Amendment

**Software implementing governance-enforcement functions — the Governance Query Layer, POS validators, Risk classification logic, and governance-document generation tooling — is classified R4 under RISK-001 §8 regardless of its technical implementation surface. This applies even where the code would otherwise appear to be ordinary internal tooling (RISK-001 §8's R1 examples) or technical infrastructure (R2): governance-enforcement software is classified by its organizational function, not its technical footprint. Independent Review is mandatory prior to production use, consistent with RISK-001 §10.1's R4 row.**

**Audit disposition (Finding 7):** Previously required only "the organization's highest applicable engineering governance tier" without naming which RISK-001 class that is — a materially important gap, since R3 requires only Architect approval (Founder informed) while R4 requires mandatory Founder approval. The revised text names R4 explicitly and states the rationale (function over technical surface) so the classification cannot be argued down to R3 based on a component's apparent technical simplicity.

---

# Amendment 009

## Founder Instructions Become Decision Records

| Field | Value |
|---|---|
| `amendment_id` | 009 |
| `status` | Proposed |
| `proposer` | Founder |
| `risk_class` | R4 (this amendment governs how organizational-behavior-affecting decisions are recorded; it does not itself alter authority hierarchy, so it does not rise to R5) |
| `applies_to` | POS-RS (Decision Record requirements), RES-001/RES-002 (context-externalization requirements as applied to Founder input) |

### Reason

Founder instructions currently risk existing only in conversation history, which RES-001 §5.2 already prohibits as a system of record for any role — this amendment closes the corresponding gap for Founder-originated instructions specifically.

### Amendment

**Any Founder decision classified R2 or above (per RISK-001 §8) that is intended to affect future organizational behavior shall be recorded as a POS Decision Record before it is considered binding on any instance other than the one that received it directly.**

**Where immediate action is required to prevent harm, the receiving role may act on the instruction immediately and must record it as a Decision Record within the same working session.** This exception does not weaken the recording requirement; it sequences it after action only where recording-before-acting would itself cause harm, consistent with RISK-001 §10.1's escalation posture at R3+ (ambiguity halts pending resolution, but this is distinct from an emergency instruction already given, which is not ambiguous — it is simply not yet recorded).

Conversation history is evidence, not canonical governance, per RES-001 §5.2.

**Audit disposition (Finding 4):** Two gaps closed. First, the prior "any Founder decision" language was unscoped, creating either universal friction or selective non-compliance; it is now scoped to R2+ decisions per RISK-001 §8, consistent with how every other governance requirement in the corpus scales by Risk Class. Second, the prior text implied a Founder instruction was not actionable until recorded, sharpening rather than closing the open Emergency Authority gap; the new second paragraph adds an explicit act-now-record-after exception for harm-prevention scenarios, without weakening the underlying requirement that a record is still made, promptly, within the same session. Note: this amendment narrows but does not resolve the broader open Emergency Authority Standard gap (no defined process for authority when the Founder is unavailable) — that remains a separate, still-missing document.

---

# Amendment 010

## Deterministic Governance Floors

| Field | Value |
|---|---|
| `amendment_id` | 010 |
| `status` | Proposed |
| `proposer` | Founder |
| `risk_class` | R4 |
| `applies_to` | RISK-001 (reaffirmation, no new rule) |

### Reason

Risk classification exists to define minimum governance requirements, and this reaffirmation exists to ensure that principle is visible in the amendment register alongside the amendments that depend on it (Amendments 001, 006, 008, 009 all presuppose it).

### Amendment

**This amendment reaffirms RISK-001 §6.5 (no role may manually assign a Risk Class lower than the deterministic minimum) and §9.1.2 (manual overrides may only increase governance, never decrease it, and this is an absolute constraint outside the DECIDE/RECOMMEND tier system) exactly as already stated in RISK-001. It introduces no new rule and exists in this register only so that amendments referencing "the floor-never-lowers principle" have a register-local pointer rather than requiring readers to consult RISK-001 directly for a rule this register's other amendments frequently assume.**

**Audit disposition (Finding 8):** Previously restated RISK-001's floor rule independently ("Deterministic governance calculations establish minimum governance obligations... Manual overrides shall never reduce deterministic governance requirements") without pointing back to §6.5/§9.1.2 — the same duplicate-source risk as Amendment 005. Reworded as an explicit, non-authoritative pointer.

---

# Amendment 011

## Generated Operational Views

| Field | Value |
|---|---|
| `amendment_id` | 011 |
| `status` | Proposed |
| `proposer` | Founder |
| `risk_class` | R4 |
| `applies_to` | POS-RS (operational-artifact taxonomy) |

### Reason

Operational summaries should not become manually maintained organizational memory that silently diverges from the POS's canonical state, consistent with POS-RS §6.2.

### Amendment

Operational documents such as AGENTS.md, CURRENT_STATE.md, MANAGER_INBOX.md, and PENDING_DECISIONS.md are considered generated views of the POS rather than independently maintained canonical records.

**During Phase 0 (Amendment 007), AGENTS.md may be manually maintained as an interim governance artifact under version control; it becomes a generated view no later than Phase 1, at which point manual edits are prohibited.** This bootstrap carve-out mirrors POS-RS §28.3's equivalent fallback for other deferred features (a manually-generated artifact from canonical sources using a controlled template is distinguished there from an independently maintained canonical record, and the same distinction applies here).

**Audit disposition (Finding 5):** The bootstrap clause is new. Without it, this amendment's blanket rule directly contradicted Amendment 007's Phase 0 description of AGENTS.md as manually-maintained governance infrastructure for the same time period. The clause resolves the contradiction by giving AGENTS.md the same treatment POS-RS already gives other bootstrap-era artifacts elsewhere in the corpus, rather than inventing a new exception pattern.

---

# Amendment 012

## Constitutional Documents Remain Historical Artifacts

| Field | Value |
|---|---|
| `amendment_id` | 012 |
| `status` | Proposed |
| `proposer` | Founder |
| `risk_class` | R4 (clarifies scope of an existing term; does not itself alter authority hierarchy) |
| `applies_to` | RES-001, RES-002, RISK-001, PM-SPEC, ARCH-SPEC, POS-RS (scope clarification only) |

### Reason

The constitutional corpus should preserve the rationale and evolution of governance rather than function as a live operational database.

### Amendment

**"Constitutional documents," for purposes of this amendment, means Tier A documents as defined in Amendment 001 (the Constitution, Authority Hierarchy, Organizational Philosophy, Decision Rights) — not Tier B or Tier C documents, and not RISK-001's separate R5 "Constitutional" work-item risk classification (RISK-001 §8), which classifies individual changes rather than entire documents and applies across all three document tiers.** Tier A documents are normative and historical artifacts: they define enduring principles, provide organizational context, and record the evolution of governance. They inform the design and operation of the POS but are not generated from it and are not themselves operational state.

**Audit disposition (Finding 9):** "Constitutional" was previously used in three unreconciled scopes across the corpus (RISK-001's R5 work-item tier, Amendment 001's Tier A document class, and this amendment's unscoped use). This amendment now explicitly cross-references Amendment 001 and distinguishes itself from RISK-001's separate, work-item-level use of the same word, closing the terminology-drift pattern the audit identified as a recurrence of the first audit's Defect #9.

---

# Amendment 013

## Founder Sprint Delegation

| Field | Value |
|---|---|
| `amendment_id` | 013 |
| `status` | Accepted *(effective only when this entry reaches the default branch after the reviews and Founder merge required below)* |
| `proposer` | Founder |
| `date` | 2026-07-21 |
| `risk_class` | R4 (MAJOR change to the RISK-001 §10.1 merge-authority floor; it preserves the fixed Founder authority hierarchy rather than transferring ultimate authority) |
| `applies_to` | RISK-001, RES-001, RES-002, PM-SPEC, ARCH-SPEC, POS-RS |
| `binding_scope` | Model A — accepted-on-entry (§0.1), limited by the activation and expiry rules below |

### Reason

Founder-only merge authority remains the safe organizational default, but it creates an avoidable handoff inside a specifically identified, Founder-approved implementation sprint whose scope and validation gates are already fixed. The Founder needs a narrow, auditable way to delegate the mechanical merge action without transferring product direction, acceptance policy, deployment authority, governance authority, or the ability to waive required evidence.

### Amendment

The Founder may explicitly activate **Founder Sprint Delegation** for one identified implementation sprint with bounded scope.

Activation requires all of the following to be recorded in the sprint definition:

- explicit Founder authorization
- a unique sprint identifier
- an enumerated set of approved tickets
- bounded technical scope and explicit stop conditions
- required validation and self-review gates
- the delegate role or instance authorized to perform sprint merges

While the delegation is active, the identified delegate may implement approved tickets, create and update pull requests, execute validation, perform self-review, and merge only the pull requests that implement the enumerated sprint tickets.

Before every delegated merge, all of the following must be true and evidenced in the pull request or its checks:

- all required CI checks pass
- architecture validation passes
- deterministic replay validation passes
- immutable-contract validation passes
- deterministic-identity validation passes
- integrity validation passes
- no governance violation is present
- no unresolved blocking issue exists
- the pull request contains only the approved ticket scope

The delegate must not bypass branch protection, force a merge around a required check, lower a risk floor, redefine architecture or domain contracts, merge a governance or constitutional change, deploy software, or expand the sprint. A missing, unavailable, skipped, or failing required gate prevents delegated merge. Any ambiguity about scope, authority, or a required contract activates the sprint's stop condition and returns merge authority to the Founder.

Delegation is limited to the identified sprint and expires immediately when the sprint completes, the sprint stops, or the Founder revokes it. Outside an explicitly activated Founder Sprint Delegation, the Founder remains the sole merge authority. The Founder remains the ultimate authority at all times and may review, merge, decline, pause, or revoke any delegated sprint action.

GitHub remains the operational record for pull requests, reviews, checks, and merges. Every delegated merge must be identified in the sprint's final report. Delegation does not grant deployment authority and does not change the governance floor, acceptance evidence, review depth, or verification required by the underlying work item's Risk Class.

### Governance Reviews and Acceptance Record

**Founder approval:** The Founder explicitly approved this amendment and the bounded SPRINT-001 activation on 2026-07-21. The amendment itself must still be merged by the Founder under the pre-amendment Founder-only rule.

**Independent Review:** Completed by `/root/amd013_independent_review`, a reviewer instance distinct from the amendment author and assigner. Review record `GOV-AMD-001-013-IR-001` appears below. The review approves the design and structural conformance subject to successful POS Validation and Founder merge of the remediation PR.

**Structural Review:** The review must verify that the amendment changes only the merge-authority floor for an explicitly activated sprint; preserves the fixed Founder authority hierarchy, default-deny behavior, risk floors, review requirements, deployment authority, and canonical GitHub evidence; and introduces no standing merge authority.

**Regression evidence:** Governance tests must prove that default Founder-only authority remains, activation is scoped to one identified sprint and enumerated tickets, all required gates are mandatory, forbidden changes cannot be delegated, and expiry is explicit.

**Reversion path:** The Founder may revoke an active delegation immediately. Permanent reversion of this accepted entry requires a superseding Founder-approved amendment under the same R4 governance floor. No in-flight pull request retains delegated merge authority after revocation or expiry.

#### Review Record GOV-AMD-001-013-IR-001

| Field | Value |
|---|---|
| `review_id` | GOV-AMD-001-013-IR-001 |
| `subject` | GOV-AMD-001 Amendment 013 and SPRINT-001 v1.2 activation |
| `reviewer` | `/root/amd013_independent_review` |
| `reviewer_role` | independent structural reviewer |
| `date` | 2026-07-21 |
| `independence` | Reviewer is neither amendment author nor assigner |
| `independent_review` | Approved with activation conditions |
| `structural_review` | Approved with activation conditions |

The reviewer inspected PR #66, merge commit `8566e9dd26e151bc1e7c80733b221562b55911f0`, Issue #67, this amendment register, RISK-001, RES-001, RES-002, the operational authority documents, SPRINT-001 v1.2, governance regression tests, and GitHub validation evidence.

The review found that Amendment 013:

- preserves Founder ultimate authority and Founder-only merge authority by default
- preserves risk, review, acceptance, and deployment floors
- creates no standing worker merge authority
- delegates no governance, constitutional, architecture-contract, deployment, risk-floor, or scope-change authority
- identifies one sprint, one delegate role, and an enumerated ticket set
- defines explicit expiry and revocation
- prohibits branch-protection bypass and merge with missing or failing gates

The review classified the amendment as R4 and approved its independent and structural conformance. Activation remained blocked pending a successful POS Validation result and Founder merge of the remediation record. Issue #67 remains the incident record for the original out-of-sequence merge and may close only after those conditions are satisfied.

---

## 12. Open Questions

- **OQ-12.1:** §0.5.1's numeric promotion threshold ("every ten `Accepted` amendments, or annually") is a placeholder pending Founder decision; no evidence in the reviewed corpus fixes this number, and it should be set deliberately rather than defaulted.
- **OQ-12.2:** RISK-001 §9.1.2's Founder self-binding ambiguity (whether the Founder is themself bound by the floor-never-lowers rule, or only subordinate roles) was flagged in the RISK-001 audit as unresolved. This register does not resolve it — none of the twelve amendments touch RISK-001 §9.1.2's text directly — and it remains a candidate for a future amendment, not addressed by this revision.
- **OQ-12.3:** The still-missing Emergency Authority Standard, Interaction Specification Standard, Execution Profile Standard, Security/Credential Policy, and Release Governance documents (flagged across both prior audits) remain unscheduled. Amendment 007's roadmap does not currently allocate a phase to producing them; whether they should be added to that roadmap or tracked as separate future amendments is left open.
