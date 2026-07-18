#!/usr/bin/env python3
"""Lean governance integrity checker — I001-I005 error codes."""
import hashlib
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("E: PyYAML required", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "governance" / "manifest.yaml"
FROZEN_DIR = REPO_ROOT / "governance" / "frozen"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def check_integrity(manifest_path: Path = MANIFEST_PATH, repo_root: Path = REPO_ROOT):
    errors = []

    try:
        raw = yaml.safe_load(manifest_path.read_text())
    except Exception as e:
        errors.append(f"I001 INVALID_MANIFEST: cannot parse {manifest_path}: {e}")
        return errors

    if not isinstance(raw, dict) or "documents" not in raw:
        errors.append("I001 INVALID_MANIFEST: missing 'documents' key")
        return errors

    documents = raw["documents"]
    if not isinstance(documents, list):
        errors.append("I001 INVALID_MANIFEST: 'documents' must be a list")
        return errors

    seen_ids = {}
    declared_files = set()

    for entry in documents:
        doc_id = entry.get("id", "<unknown>")
        status = entry.get("status", "")
        filename = entry.get("filename", "")
        expected_hash = entry.get("sha256", "")

        if doc_id in seen_ids:
            errors.append(f"I005 DUPLICATE_ENTRY: id '{doc_id}' appears more than once")
        else:
            seen_ids[doc_id] = filename

        if status != "frozen":
            continue

        if not filename:
            errors.append(f"I001 INVALID_MANIFEST: entry '{doc_id}' has no filename")
            continue

        file_path = repo_root / filename
        declared_files.add(file_path.resolve())

        if not file_path.exists():
            errors.append(f"I002 MISSING_FILE: {filename} (id={doc_id})")
            continue

        if not expected_hash:
            errors.append(f"I001 INVALID_MANIFEST: entry '{doc_id}' has no sha256")
            continue

        actual = _sha256(file_path)
        if actual != expected_hash:
            errors.append(
                f"I003 HASH_MISMATCH: {filename} (id={doc_id})\n"
                f"  expected: {expected_hash}\n"
                f"  actual:   {actual}"
            )

    frozen_dir = repo_root / "governance" / "frozen"
    if frozen_dir.exists():
        for p in sorted(frozen_dir.rglob("*")):
            if p.is_file() and p.resolve() not in declared_files:
                rel = p.relative_to(repo_root)
                errors.append(f"I004 UNDECLARED_FROZEN_FILE: {rel}")

    return errors


def main():
    errors = check_integrity()
    if not errors:
        print("OK: all frozen governance files pass integrity check")
        sys.exit(0)

    # Distinguish invalid manifest (I001/I005 only possible without reaching file checks)
    manifest_only = all(e.startswith("I001") or e.startswith("I005") for e in errors)
    for e in errors:
        print(e)
    sys.exit(2 if manifest_only else 1)


if __name__ == "__main__":
    main()
