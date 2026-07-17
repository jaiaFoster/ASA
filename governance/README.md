# Governance Directory

This directory contains all ASA 2 governance artifacts organized by type.

## Structure

### `frozen/`

Frozen historical and normative governance documents. These files are **not edited in place**. Content is preserved byte-for-byte from the versions that were in effect at bootstrap.

Placement in `frozen/` does not imply these documents have identical governance weight — they span constitutional principles, role specifications, and engineering specifications.

To correct, extend, or supersede a frozen document, add an entry to `amendments/`.

### `amendments/`

Amendment register entries. Amendments apply over frozen documents and do not modify their bodies. See `GOV-AMD-001.md` for the initial register.

### `audits/`

Independent critique, governance review, and adversarial audit artifacts. These document findings against governance documents but do not modify them.

### `history/superseded/`

Documents preserved for reference that have been superseded by later versions or made obsolete. Not authoritative.

### `manifest.yaml`

The single source of truth for governance file identity. Lists every artifact with class, status, version, SHA-256 hash, and original path. The validator uses this file to confirm integrity.

## Key Rules

- Frozen files are never substantively edited.
- Amendments are stored separately and applied by interpretation, not by in-place edit.
- Audit artifacts document findings; they do not constitute approvals.
- Generated operational views (in `project/generated/`) are not canonical governance documents.
- No software component may approve, reject, merge, or deploy based on governance status alone.
