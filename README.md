# ASA 2 — Governance and POS Bootstrap Repository

## Overview

ASA 2 is being rebuilt separately from the legacy ASA system. This repository currently contains governance infrastructure and POS (Project Operating System) bootstrap scaffolding. Application code is not present here.

## What This Repository Contains

### Governance Documents (`governance/`)

Frozen historical and normative governance inputs. These documents are preserved byte-for-byte and **not edited in place**. Later corrections and reinterpretations are stored as amendments.

### POS Records (`project/`)

Operational truth for active project work. POS records (work items, assignments, results, decisions, reviews, evidence) are canonical. Generated views summarize this state but are not canonical themselves.

### Tooling (`tools/pos/`)

Deterministic mechanical tools: a validator and a generator. Neither tool may approve, merge, or deploy.

## Key Rules

1. **ASA 2 is separate from legacy ASA.** No legacy application code has been migrated here.
2. **Governance documents are frozen.** Do not edit `governance/frozen/` files.
3. **Amendments are separate.** See `governance/amendments/GOV-AMD-001.md`.
4. **POS records are canonical.** Generated views (`project/generated/`) summarize state; they are not authoritative.
5. **Automation is advisory and mechanical only.** No software component may approve, reject, merge, or deploy independently.
6. **All authority decisions require the Founder.**

## Quick Start

```bash
# Install dependencies
python -m pip install -r tools/pos/requirements.txt

# Run tests
python -m pytest tests/pos -v

# Validate the repository
python tools/pos/validate.py

# Regenerate operational views
python tools/pos/generate.py
```

## Repository Structure

```
governance/
  frozen/           — Frozen normative governance documents
  amendments/       — Amendment register (applies over frozen docs)
  audits/           — Governance and risk audits
  history/          — Superseded documents
  manifest.yaml     — Integrity manifest with SHA-256 hashes

project/
  BOOTSTRAP_STATUS.yaml   — Current phase and operational state
  schemas/                — JSON Schema (YAML) for all POS record types
  work/, assignments/, results/, decisions/, reviews/, evidence/, risks/
                          — Canonical POS record directories
  roles/registry.yaml     — Role registry
  generated/              — Generated operational views (not canonical)

tools/pos/          — Validator, generator, and shared helpers
tests/pos/          — Automated tests

.github/
  CODEOWNERS                    — Protected path ownership
  pull_request_template.md      — PR checklist
  workflows/validate-pos.yml    — CI validation workflow
```

## Missing Documents at Bootstrap

The following expected governance documents were not found in the repository and were not synthesized:

- `RISK-001` — Risk governance standard
- `GOV-AUDIT-001` — Primary governance audit
- `RISK-001-AUDIT-001` — RISK-001 audit

These are noted in `governance/manifest.yaml`. Do not create synthetic versions.

## Current Phase

`POS_BOOTSTRAP` — See `project/BOOTSTRAP_STATUS.yaml` and `project/generated/CURRENT_STATE.md`.
