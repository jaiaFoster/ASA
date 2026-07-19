# ASA Project — Agent Entry Point

**Active operating system: Lean POS** (migration complete — all six cutover phases done)

## Canonical state

- **Project state:** [`project/lean/state/project-state.yaml`](project/lean/state/project-state.yaml)
- **Migration final report:** [`project/lean/migration/FINAL_REPORT.md`](project/lean/migration/FINAL_REPORT.md)
- **Current state view:** [`CURRENT_STATE.md`](CURRENT_STATE.md)

## Operational truth

GitHub issues, PRs, reviews, CI checks, and merges are the operational record.
Lean POS stores only non-derivable durable governance state (objective, constraints, refs).

## Lean tools

- Validate: `python tools/pos/lean/validate.py --file <file> --schema <schema>`
- Generate current state: `python tools/pos/lean/generate.py current-state --project-state project/lean/state/project-state.yaml --generated-at <ISO8601> --output CURRENT_STATE.md`
- Integrity check: `python tools/pos/lean/check_integrity.py`
- Entrypoint check: `python tools/pos/lean/check_entrypoints.py`
- Pre-push check: `python tools/pos/lean/pre_push_check.py`

## Role packages

See [`roles/`](roles/) for Founder, Architect, Manager, and Worker role definitions.

## Governance

Frozen governance documents live in [`governance/frozen/`](governance/frozen/).
Changes require the authorized process defined in [`roles/shared/RISK_SCALED_PROCESS.md`](roles/shared/RISK_SCALED_PROCESS.md).
