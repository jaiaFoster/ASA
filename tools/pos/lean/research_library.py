"""Deterministic consistency check for the canonical research library (ROLE-RESEARCH).

Validates `research/` as durable research state (GOV-AMD-001 Amendment 017):

- `catalog.yaml` parses, its `status_semantics` references Amendment 017 A.4
  instead of restating it, and every record has a unique `research_id` and a
  lifecycle status from the accepted set;
- each dossier exists and carries the same status as its catalog record;
- every dossier under `research/strategies/` is catalogued, so there is no
  orphan research truth;
- every referenced source record exists and its `source_id` matches its
  filename, with an accepted `source_class`;
- referenced prior ASA research paths exist.

It judges structure only, never evidence quality. Exit 0 means consistent;
exit 1 means errors.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]

LIFECYCLE = (
    "DISCOVERED",
    "TRIAGE",
    "DEEP_RESEARCH",
    "QUALIFIED",
    "INSUFFICIENT_EVIDENCE",
    "REJECTED",
)
SOURCE_CLASSES = (
    "EXTERNAL_PRIMARY",
    "EXTERNAL_REPLICATION",
    "EXTERNAL_SECONDARY",
    "ASA_PRIOR_INTERNAL",
)
CANONICAL_SEMANTICS = "governance/amendments/GOV-AMD-017.md#a4-qualification-semantics-canonical"
_STATUS_LINE = re.compile(r"^\s*-\s*\*\*Research status:\*\*\s*([A-Z_]+)\s*$", re.MULTILINE)


def validate_library(repo_root: Path = REPO_ROOT) -> list[str]:
    root = repo_root / "research"
    catalog_path = root / "catalog.yaml"
    if not catalog_path.is_file():
        return ["R001 MISSING_CATALOG: research/catalog.yaml not found"]
    try:
        catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        return [f"R001 INVALID_CATALOG: {error}"]
    errors: list[str] = []
    if not isinstance(catalog, dict) or catalog.get("status_semantics") != CANONICAL_SEMANTICS:
        # Qualification semantics have one canonical home (Amendment 017 A.4);
        # the delegable catalog may only reference it, never restate it.
        errors.append(f"R010 STATUS_SEMANTICS_NOT_CANONICAL: must be {CANONICAL_SEMANTICS!r}")
    records = catalog.get("records") if isinstance(catalog, dict) else None
    if not isinstance(records, list):
        return ["R001 INVALID_CATALOG: 'records' must be a list"]
    seen: set[str] = set()
    catalogued_dossiers: set[str] = set()
    for record in records:
        research_id = str(record.get("research_id", ""))
        if not research_id:
            errors.append("R002 MISSING_ID: a catalog record has no research_id")
            continue
        if research_id in seen:
            errors.append(f"R002 DUPLICATE_ID: {research_id}")
        seen.add(research_id)
        status = record.get("research_status")
        if status not in LIFECYCLE:
            errors.append(f"R003 INVALID_STATUS: {research_id} has {status!r}")
        dossier = record.get("dossier")
        dossier_path = repo_root / str(dossier)
        if not dossier or not dossier_path.is_file():
            errors.append(f"R004 MISSING_DOSSIER: {research_id} -> {dossier}")
        else:
            catalogued_dossiers.add(str(dossier))
            match = _STATUS_LINE.search(dossier_path.read_text(encoding="utf-8"))
            if match is None:
                errors.append(f"R005 DOSSIER_STATUS_MISSING: {dossier}")
            elif match.group(1) != status:
                errors.append(
                    f"R005 STATUS_MISMATCH: {research_id} catalog={status} dossier={match.group(1)}"
                )
        for source_id in record.get("source_ids") or []:
            source_path = root / "sources" / f"{source_id}.yaml"
            if not source_path.is_file():
                errors.append(f"R006 MISSING_SOURCE: {research_id} -> {source_id}")
                continue
            source = yaml.safe_load(source_path.read_text(encoding="utf-8")) or {}
            if source.get("source_id") != source_id:
                errors.append(f"R006 SOURCE_ID_MISMATCH: {source_path.name}")
            if source.get("source_class") not in SOURCE_CLASSES:
                errors.append(
                    f"R007 INVALID_SOURCE_CLASS: {source_id} has {source.get('source_class')!r}"
                )
        for prior in record.get("prior_ASA_research") or []:
            if not (repo_root / str(prior)).exists():
                errors.append(f"R008 MISSING_PRIOR_RESEARCH: {research_id} -> {prior}")
    for dossier_path in sorted((root / "strategies").glob("*.md")):
        relative = dossier_path.relative_to(repo_root).as_posix()
        if relative not in catalogued_dossiers:
            errors.append(f"R009 ORPHAN_DOSSIER: {relative} is not in catalog.yaml")
    return errors


def main() -> int:
    errors = validate_library()
    for error in errors:
        print(error)
    if errors:
        print(f"FAIL: {len(errors)} research library error(s)")
        return 1
    print("OK: research library is consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
