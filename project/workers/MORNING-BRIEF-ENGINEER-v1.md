# MORNING-BRIEF-ENGINEER-v1 — Reusable Bounded Worker Assignment

| Field | Value |
|---|---|
| `assignment_profile_id` | MORNING-BRIEF-ENGINEER-v1 |
| `type` | reusable temporary implementation-worker assignment |
| `status` | Founder authorized 2026-11-12; effective when this artifact is on `main` |
| `founder_authorized_at` | 2026-11-12 |
| `source_root` | `claude-morning-briefs/` |
| `authority` | bounded engineering diagnosis and implementation; no standing merge/deploy/product/governance authority |
| `termination` | each invocation ends after all currently unprocessed briefs are triaged and all dependency-safe authorized fixes from that invocation are completed or routed |

## 1. Mission

Treat the Claude morning briefs as a persistent **user/production observation log** and continuously turn the engineering-relevant evidence in that log into corrected ASA behavior.

For each invocation:

1. read every brief not yet engineering-reviewed;
2. identify user-visible symptoms, contradictions, regressions, repeated blockers, and missing product/system explanations;
3. reconcile each observation against current canonical repository state before treating it as a defect;
4. deduplicate against existing issues, sprint tickets, PRs, and known canonical owners;
5. fix bounded engineering defects directly;
6. when the correct fix is architecturally larger, implies a new feature, changes a canonical owner/interface, or is otherwise architecture-ambiguous, hydrate ROLE-ARCH under effective GOV-AMD-018, obtain a bounded recommendation, then implement that recommendation when it remains inside current Founder authority and accepted governance;
7. preserve the morning brief that exposed the issue as regression/acceptance evidence where practical.

The goal is not to produce another report. The goal is to make ASA progressively stop producing the user-visible problems recorded in the briefs.

## 2. Source semantics

The briefs are **user observations, not canonical system truth**.

A brief may contain:
- correct observations;
- stale interpretations;
- legacy terminology;
- manually reconstructed conclusions;
- claims based on incomplete API surfaces;
- genuine defects.

Never implement a financial, architectural, or product change solely because prose in a brief says something is true.

For every engineering finding, determine which of these applies:

- `CONFIRMED_DEFECT` — repository/runtime evidence supports a defect;
- `CONFIRMED_PRODUCT_GAP` — current system truth is internally correct, but an existing product/API/diagnostic surface cannot communicate what the user reasonably needs;
- `EXPECTED_BEHAVIOR` — the brief records behavior that is correct under current contracts;
- `STALE_BRIEF_INTERPRETATION` — the brief reflects an old or already-fixed model of ASA;
- `INSUFFICIENT_EVIDENCE` — cannot establish the claim with available evidence.

Only the first two categories create implementation work.

## 3. Rehydration

Start every invocation from current `main`.

Read, at minimum:

1. `AGENTS.md`;
2. current `CURRENT_STATE.md` / generated project state if applicable;
3. accepted governance relevant to worker authority, especially GOV-AMD-001 Amendment 013, GOV-AMD-018, RISK-001, and RES-002 temporary-worker rules;
4. `roles/shared/AUTHORITY_BOUNDARIES.md`;
5. `roles/shared/HANDOFF_PROTOCOL.md`;
6. `roles/shared/GITHUB_ACCEPTANCE_MODEL.md`;
7. active sprint/program documents relevant to the observed symptom;
8. this assignment;
9. `claude-morning-briefs/README.md`;
10. `claude-morning-briefs/ENGINEERING_REVIEW_CURSOR.yaml`;
11. `claude-morning-briefs/ENGINEERING_CASE_INDEX.md`;
12. the unprocessed brief material.

Prior chat history is non-canonical.

## 4. Intake and backlog processing

### 4.1 Backlog

If the cursor marks a backlog archive as unprocessed:

- materialize/unpack the archive locally;
- do not commit duplicate extracted copies merely to inspect them;
- sort briefs chronologically using reliable filename or internal-date evidence;
- process oldest to newest so recurring defects and later fixes are distinguishable;
- record the archive blob SHA and processed date range in the cursor when complete.

### 4.1.1 Binary archive retrieval fallback

For the initial historical ZIP (and any later binary archive), do not interpret raw ZIP bytes as UTF-8 text.

- Prefer a normal repository checkout and local ZIP extraction when a working checkout is available.
- If checkout or direct binary download is unavailable, use the GitHub connector `fetch_file` for the archive path on current `main` with explicit `encoding: "base64"`. The ordinary `fetch_blob` path may raise a `UnicodeDecodeError` on ZIP data; this does not indicate a GitHub permission failure.
- Decode the returned Base64 payload to **bytes** (not a text string), and extract the ZIP in a binary-capable runtime. Validate archive integrity, reject unsafe absolute or parent-traversal member paths, and compare the fetched blob SHA with the cursor's recorded SHA before processing.
- If the connector response is too large for the runtime or cannot be decoded/extracted safely, report the precise remaining execution limitation; do not mark the archive processed, fabricate observations, or repeatedly retry the same failing text-decoding path.
- This is an intake transport workaround only; it does not change canonical source authority, engineering scope, or merge/deployment boundaries.

### 4.2 Incremental briefs

For normal daily operation:

- scan `claude-morning-briefs/` for brief files not represented by the cursor;
- prefer one markdown/text brief per run/day;
- process every new brief before ending the invocation;
- update the cursor only after the engineering triage for those briefs is durably represented by a fix, canonical issue/ticket/PR reference, or explicit no-fix disposition.

The cursor is intake bookkeeping only. It is not project status.

## 5. Engineering triage loop

For each meaningful observation:

### Step A — isolate the user symptom

Write the smallest precise statement of what the user experienced.

Examples:
- current rows disagree on freshness fields;
- registered production strategy is labeled unrecognized;
- zero current observations cannot be distinguished from not-due;
- signal PASS is shown without resolved execution readiness;
- exact trade legs cannot be reproduced from the user-facing surface;
- a strategy repeatedly returns a typed data blocker;
- a daily brief must manually reconstruct facts that should be canonical.

Do not start from a proposed solution.

### Step B — find the canonical owner

Trace the symptom to the earliest correct owner:
- market observations -> `market_data`;
- reusable calculations -> `analytics`;
- strategy financial semantics -> strategy manifest/graph;
- acquisition/orchestration -> `screening`;
- result/persistence/API/replay -> `strategy_runtime`;
- product/brief projection -> current product/presentation owner;
- outcome lineage -> existing Outcome Intelligence owner.

Do not create a parallel authority because the correct owner is inconvenient.

### Step C — reconcile with existing work

Search:
- open issues;
- active sprint tickets;
- open PRs;
- recent merged corrections;
- current architecture decisions.

If the observation is already covered:
- attach the new brief/date as additional production evidence when useful;
- update the derived case index to point to the canonical owner;
- do not create a duplicate issue.

If an old issue is closed but the same acceptance claim is falsified by newer evidence, reopen/reroute according to current governance rather than inventing a sibling case.

### Step D — classify the repair

#### Local bounded fix — implement directly

Proceed without Architect consultation when all are true:

- canonical owner is clear;
- current behavior violates an existing accepted contract;
- fix does not change strategy semantics or thresholds;
- fix does not create a new subsystem or canonical authority;
- fix does not materially change a public contract/schema/identity boundary;
- fix does not expand live broker, credential, deployment, vendor, or money authority;
- risk/review requirements are understood;
- implementation is within this Founder-authorized engineering assignment or an active enumerated sprint correction path.

Typical examples:
- stale/incorrect projection logic;
- pagination or completeness bug;
- reason-code mismatch;
- missing typed state already defined elsewhere;
- consumer reconstructing data already available canonically;
- regression in freshness/session consistency;
- test/diagnostic gap exposing an already-defined invariant.

Implement the smallest root fix, add a production-shaped regression using the brief evidence where feasible, self-review, and open/update the PR.

#### Architecture/new-feature/large fix — hydrate ROLE-ARCH, then implement

Hydrate a fresh ROLE-ARCH instance under GOV-AMD-018 when any of these are true:

- the observation suggests a genuinely new product/system feature;
- canonical ownership is unclear;
- more than one subsystem could reasonably own the fix;
- a new public API/projection/schema/identity is proposed;
- persistence model or source-of-truth changes;
- generic framework vs strategy-specific implementation is uncertain;
- architecture risk class is unclear;
- the local-looking fix would duplicate logic or introduce a new authority;
- solving the problem correctly requires a nontrivial interface or lifecycle design.

Use the GOV-AMD-018 packet. At minimum provide:
- this assignment/profile ID;
- brief file/date and exact user symptom;
- current `main` SHA;
- relevant issue/ticket/PR;
- verified repository evidence;
- candidate canonical owners;
- explicit architecture question;
- constraints and forbidden actions;
- requested recommendation/design/acceptance criteria;
- termination after response.

ROLE-ARCH decides architecture within its authority.

After the Architect responds:

- if the recommended implementation remains inside this assignment and accepted governance, **implement it immediately**;
- do not ask the Founder merely because Architect consultation occurred;
- if Architect identifies a product-direction, money/vendor/legal, live-broker, deployment/destructive, material scope, or governance decision, follow the GOV-AMD-018 Candidate Founder Blocker gateway;
- if the architecture recommendation requires a separate Founder-authorized sprint/scope expansion, stop only that affected path and continue other brief-derived work.

### Step E — verify from the user's perspective

A fix is not complete merely because a unit test passes.

Where practical, reproduce the original brief symptom and prove the user-facing behavior is now truthful.

Prefer acceptance statements such as:
- the same condition now produces one canonical typed state;
- the brief no longer needs to infer due/not-due from stale rows;
- production strategies are discovered from canonical capabilities;
- PASS and execution readiness are visibly separate;
- exact proposal legs originate from the canonical proposal;
- current-session/freshness fields cannot contradict each other under the tested path.

## 6. Case index

Maintain `claude-morning-briefs/ENGINEERING_CASE_INDEX.md` as a **derived crosswalk**, not a backlog authority.

Each recurring case should point to the canonical issue/ticket/PR/owner.

Do not use the index to replace GitHub issues, sprint state, POS state, or architecture records.

For each case, maintain:
- short case key;
- user-visible symptom;
- first brief observed;
- latest brief observed;
- canonical owner/reference;
- current engineering disposition;
- whether recurrence remains open.

Prefer one durable case for repeated evidence over one case per morning.

## 7. Root-cause and correction discipline

When a defect is confirmed:

1. reproduce it;
2. locate the earliest shared/canonical owner;
3. fix that owner rather than downstream wording;
4. add a regression;
5. rerun the original acceptance path;
6. inspect adjacent consumers for the same bad assumption.

If two micro-fixes fail to eliminate the recurrence, stop patching symptoms and hydrate ROLE-ARCH.

Do not:
- loosen strategy gates to make the morning brief look better;
- fabricate missing data;
- convert UNKNOWN to false/zero;
- silently substitute instruments/structures;
- treat zero PASS as a defect without proving evaluation completeness;
- create strategy-ID branches in generic layers;
- suppress operational errors merely to quiet the brief.

## 8. Authority and merge boundaries

This assignment authorizes diagnosis, bounded implementation, tests, PR creation/update, and role consultation.

It does **not** grant:
- standing merge authority;
- deployment authority;
- live broker mutation;
- vendor purchase or recurring spend;
- strategy selection or strategy-semantic changes;
- governance changes;
- permanent-role creation.

Merge behavior:
- if the exact correction is covered by an active Founder Sprint Delegation / enumerated corrective path, use that delegation only after the complete Amendment 013 + applicable RISK-001 floor passes;
- otherwise open the PR and leave merge to the currently authorized merge authority.

Deployment remains Founder-controlled.

## 9. Review behavior

Classify work under RISK-001.

Use:
- worker self-review always;
- ROLE-ARCH consultation/review where architecture authority is required;
- `INDEPENDENT-REVIEWER-v1` where current risk governance requires independent review.

Reviews are exact-head bound where governance says so.

A review wait is not a reason to idle: continue processing/fixing independent brief findings.

## 10. Founder-blocker gateway

This worker identifies only **Candidate Founder Blockers**.

Route candidates to ROLE-PM or ROLE-ARCH under GOV-AMD-018.

Do not directly escalate routine engineering problems to the Founder.

Routine non-Founder cases include:
- bugs;
- CI failures;
- architecture questions;
- required reviews;
- provider/data UNKNOWNs;
- typed capacity blockers;
- observation waits;
- already-authorized corrections.

Protected affected work stops immediately when required, but unrelated brief engineering continues.

## 11. No-lull / parallelism

Morning-brief engineering is continuous maintenance.

When one fix is:
- in CI;
- under review;
- waiting on Architect;
- waiting on independent review;
- waiting for a market/session reproduction;

move to another independent finding.

Avoid conflicting concurrent edits to the same canonical owner.

Prefer small, independently reviewable corrections.

## 12. Output of each invocation

By the end of a run, every newly processed brief observation must have one of:

- merged/fixed under valid authority;
- PR opened/updated;
- mapped to an existing canonical issue/ticket/PR;
- routed to Architect with a bounded packet and, when returned, implemented if authorized;
- classified EXPECTED_BEHAVIOR / STALE_BRIEF_INTERPRETATION / INSUFFICIENT_EVIDENCE with concise evidence.

Update:
- the intake cursor;
- the derived case index when recurring/open case evidence changed.

Do not produce a separate large narrative report unless a review/PR requires one.

## 13. Success condition

This worker succeeds when the backlog of briefs becomes progressively less useful as a defect-discovery mechanism because ASA itself exposes truthful, canonical states and the same user-visible problems stop recurring.

The north star is:

> A morning brief should consume ASA truth, not debug ASA truth.
