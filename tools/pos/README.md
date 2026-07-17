# POS Tooling

## Overview

These tools perform **mechanical and advisory** operations only. No tool in this directory may approve, reject, merge, or deploy.

## Files

| File | Purpose |
|------|---------|
| `schemas.py` | Shared constants: repository paths, allowed status values, risk classes, YAML helpers, hash calculation |
| `validate.py` | Repository validator — checks manifest integrity, frozen file hashes, required directories, schema parseability |
| `generate.py` | Deterministic generator — produces operational view files in `project/generated/` |
| `requirements.txt` | Python dependencies |

## Validator

The validator outputs only: `PASS`, `FAIL`, `WARNING`, `UNDETERMINED`.

It will **never** output: `APPROVED`, `REJECTED`, `SAFE TO MERGE`, or `GOVERNANCE SATISFIED`.

```bash
python -m pip install -r tools/pos/requirements.txt
python tools/pos/validate.py
```

A non-zero exit code indicates validation failure.

## Generator

The generator is fully deterministic — same inputs produce the same outputs. It does not call an LLM.

```bash
python tools/pos/generate.py
```

Generated files are written to `project/generated/`. Root-level `AGENTS.md`, `CURRENT_STATE.md`, and `MANAGER_INBOX.md` contain pointers to the generated versions.

## Boundaries

- The validator confirms mechanical correctness.
- The generator summarizes current project state.
- Neither tool has authority over governance decisions, merges, or deployments.
- Both tools are read-only with respect to canonical POS records.
