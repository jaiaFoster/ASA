<!--
THIS FILE IS GENERATED.
DO NOT EDIT MANUALLY.
Regenerate with: python tools/pos/generate.py
-->

# AGENTS.md — Worker Context

## Project

**Name:** ASA2
**Phase:** POS_BOOTSTRAP

## Current Objective

**ID:** POS-BOOTSTRAP-01
**Title:** Create Git-backed POS Lite
**Status:** proposed

## Current Active Assignment

None at this time.

## Canonical State Locations

- POS records: `project/work/`, `project/assignments/`, `project/results/`, `project/decisions/`, `project/reviews/`, `project/evidence/`
- Bootstrap status: `project/BOOTSTRAP_STATUS.yaml`
- Role registry: `project/roles/registry.yaml`

## Governance

- Frozen governance documents: `governance/frozen/`
- Amendments: `governance/amendments/GOV-AMD-001.md`
- Manifest: `governance/manifest.yaml`

## Worker Restrictions

- Workers may NOT approve work.
- Workers may NOT merge pull requests.
- Workers may NOT deploy.
- Workers may NOT create permanent organizational roles.
- Workers may NOT modify frozen governance documents.
- Workers MUST produce result records for all assigned work.

## Acceptance Authority

**founder_only**

## Automation Boundaries

- Mode: `advisory_and_mechanical_only`
- May approve: `False`
- May reject: `False`
- May merge: `False`
- May deploy: `False`

---

> **WARNING:** This is a generated file. Do not edit manually.
> Regenerate with: `python tools/pos/generate.py`
>
> **WARNING:** Mechanical validation passing does NOT constitute approval, merge authorization, or deployment authorization.
