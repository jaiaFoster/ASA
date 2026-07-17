# Project Directory

This directory holds POS (Project Operating System) operational records. These records are the authoritative source of project truth during active operations.

## POS Record Directories

All directories below store YAML files conforming to the schemas in `schemas/`. Records in these directories are canonical — not the generated views in `generated/`.

| Directory | Record Type | Schema |
|-----------|------------|--------|
| `work/` | Work items — discrete units of scoped work | `schemas/work-item.schema.yaml` |
| `assignments/` | Assignments issued to workers | `schemas/assignment.schema.yaml` |
| `results/` | Worker result records | `schemas/worker-result.schema.yaml` |
| `decisions/` | Decisions pending or made by the Founder | `schemas/decision.schema.yaml` |
| `reviews/` | Review records (does not constitute approval) | `schemas/review.schema.yaml` |
| `evidence/` | Evidence artifacts | `schemas/evidence.schema.yaml` |
| `risks/` | Risk tracking records (schema TBD in POS-BOOTSTRAP-02) | — |
| `roles/` | Role registry | `roles/registry.yaml` |

## Generated Views

`generated/` contains machine-generated operational summaries. These are **not canonical**. Do not edit them manually — regenerate with:

```bash
python tools/pos/generate.py
```

## Bootstrap Status

The current phase and operational state are tracked in `BOOTSTRAP_STATUS.yaml`.
