# Manager Startup Checklist

Run this checklist when the Manager is first instantiated or rehydrated after a significant gap.

## Step 1 — Confirm Repository

- [ ] Confirm repository: `https://github.com/jaiaFoster/ASA`
- [ ] Confirm current branch: should be `main`
- [ ] Check `git log --oneline -5` to confirm starting commit
- [ ] Check `git status --short` — working tree should be clean

## Step 2 — Read Role Instructions

- [ ] Read `roles/manager/INSTRUCTIONS.md`
- [ ] Read `roles/shared/AUTHORITY_BOUNDARIES.md`
- [ ] Read `roles/shared/GITHUB_ACCEPTANCE_MODEL.md`
- [ ] Read `roles/shared/RISK_SCALED_PROCESS.md`

## Step 3 — Read Current State

- [ ] Read `project/BOOTSTRAP_STATUS.yaml`
- [ ] Read `project/generated/CURRENT_STATE.md` (or regenerate: `python tools/pos/generate.py`)
- [ ] Read `project/generated/MANAGER_INBOX.md`
- [ ] Read `roles/manager/CONTEXT_PACKET.md`

## Step 4 — Read Active Roadmap and Work

- [ ] List active work items: `project/work/`
- [ ] Check open PRs on GitHub if tooling is available
- [ ] Identify any pending Founder decisions
- [ ] Identify any blocked work

## Step 5 — Inspect Repository Structure

- [ ] Run `python tools/pos/validate.py` — note any failures
- [ ] Run `python -m pytest tests/pos -v --tb=short` — note any failures
- [ ] Note pre-existing warnings (do not treat warnings as new failures)

## Step 6 — Identify Current Objective

- [ ] State the current primary objective in one sentence
- [ ] Confirm whether the Architect is instantiated and available
- [ ] Identify the next highest-value action

## Step 7 — Produce First Manager Briefing

Output a concise briefing containing:

**Project State:**  
[One paragraph: where the project is right now]

**Active Work:**  
[List of work items and their status]

**Open PRs Pending Founder Action:**  
[List with PR links]

**Blockers:**  
[Anything preventing forward progress]

**Architect Status:**  
[Instantiated / not instantiated; what's assigned to them]

**Recommended Next Step:**  
[One concrete action]

**Decisions Needed from Founder:**  
[Specific bounded questions, if any]
