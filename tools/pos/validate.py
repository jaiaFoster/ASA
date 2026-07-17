#!/usr/bin/env python3
"""
ASA2 POS Repository Validator.

Performs mechanical checks only. Output is limited to:
  PASS    — check succeeded
  FAIL    — check failed (exits non-zero)
  WARNING — anomaly that does not fail validation
  UNDETERMINED — check could not be completed

This validator will NEVER output: APPROVED, REJECTED, SAFE TO MERGE,
GOVERNANCE SATISFIED, or any other authority statement.
"""

import sys
from pathlib import Path

# Allow running directly or as a module
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import yaml
from tools.pos.schemas import (
    REPO_ROOT,
    MANIFEST_PATH,
    BOOTSTRAP_STATUS_PATH,
    ROLE_REGISTRY_PATH,
    SCHEMAS_DIR,
    SCHEMA_FILES,
    REQUIRED_DIRECTORIES,
    sha256_file,
    load_yaml,
)

FAILURES = []
WARNINGS = []


def result(status: str, message: str) -> None:
    print(f"[{status}] {message}")
    if status == "FAIL":
        FAILURES.append(message)
    elif status == "WARNING":
        WARNINGS.append(message)


def check_manifest_exists():
    if not MANIFEST_PATH.exists():
        result("FAIL", f"Manifest not found: {MANIFEST_PATH.relative_to(REPO_ROOT)}")
        return None
    result("PASS", "Manifest found")
    return load_yaml(MANIFEST_PATH)


def check_frozen_files(manifest):
    if manifest is None:
        result("UNDETERMINED", "Skipping frozen file checks: manifest not loaded")
        return

    documents = manifest.get("documents", [])
    for doc in documents:
        filename = doc.get("filename")
        expected_hash = doc.get("sha256")
        doc_id = doc.get("id", "UNKNOWN")
        status = doc.get("status", "")

        if status == "missing":
            result("WARNING", f"{doc_id}: marked missing in manifest, skipping hash check")
            continue

        if not filename:
            result("WARNING", f"{doc_id}: no filename in manifest entry")
            continue

        path = REPO_ROOT / filename
        if not path.exists():
            result("FAIL", f"{doc_id}: file not found at {filename}")
            continue

        actual_hash = sha256_file(path)
        if expected_hash and actual_hash != expected_hash:
            result("FAIL", f"{doc_id}: hash mismatch. expected={expected_hash[:16]}... actual={actual_hash[:16]}...")
        elif not expected_hash:
            result("WARNING", f"{doc_id}: no expected hash in manifest, cannot verify integrity")
        else:
            result("PASS", f"{doc_id}: hash verified ({filename})")


def check_required_directories():
    for d in REQUIRED_DIRECTORIES:
        path = REPO_ROOT / d
        if path.is_dir():
            result("PASS", f"Directory exists: {d}")
        else:
            result("FAIL", f"Required directory missing: {d}")


def check_schemas_parse():
    for schema_file in SCHEMA_FILES:
        path = SCHEMAS_DIR / schema_file
        if not path.exists():
            result("FAIL", f"Schema file missing: project/schemas/{schema_file}")
            continue
        try:
            data = load_yaml(path)
            if data is None:
                result("WARNING", f"Schema file is empty: {schema_file}")
            else:
                result("PASS", f"Schema parses: {schema_file}")
        except yaml.YAMLError as e:
            result("FAIL", f"Schema YAML parse error in {schema_file}: {e}")


def check_bootstrap_status():
    if not BOOTSTRAP_STATUS_PATH.exists():
        result("FAIL", f"BOOTSTRAP_STATUS.yaml not found")
        return
    try:
        data = load_yaml(BOOTSTRAP_STATUS_PATH)
        if data is None:
            result("FAIL", "BOOTSTRAP_STATUS.yaml is empty")
        else:
            result("PASS", "BOOTSTRAP_STATUS.yaml parses")
    except yaml.YAMLError as e:
        result("FAIL", f"BOOTSTRAP_STATUS.yaml parse error: {e}")


def check_role_registry():
    if not ROLE_REGISTRY_PATH.exists():
        result("FAIL", "project/roles/registry.yaml not found")
        return
    try:
        data = load_yaml(ROLE_REGISTRY_PATH)
        if data is None:
            result("FAIL", "registry.yaml is empty")
        else:
            result("PASS", "registry.yaml parses")
    except yaml.YAMLError as e:
        result("FAIL", f"registry.yaml parse error: {e}")


def main():
    print("=" * 60)
    print("ASA2 POS Repository Validator")
    print("Mechanical checks only. No authority statements.")
    print("=" * 60)

    manifest = check_manifest_exists()
    check_frozen_files(manifest)
    check_required_directories()
    check_schemas_parse()
    check_bootstrap_status()
    check_role_registry()

    print("=" * 60)
    print(f"Checks complete. Failures: {len(FAILURES)}  Warnings: {len(WARNINGS)}")

    if FAILURES:
        print("[FAIL] One or more checks failed.")
        sys.exit(1)
    else:
        print("[PASS] All checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
