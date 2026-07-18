#!/usr/bin/env python3
"""
Lean POS offline validator.

Validates lean records against their schemas without any network access,
GitHub credentials, or mutations.

Exit codes: 0 = all valid, 1 = one or more failures.

Error codes are stable and machine-readable (see tools/pos/lean/schemas.py).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import yaml
import jsonschema

from tools.pos.lean.schemas import (
    REPO_ROOT,
    LEAN_SCHEMAS_DIR,
    LEAN_SCHEMA_FILES,
    VALID_RISK_CLASSES,
    VALID_TRIAL_RULE_STATES,
    VALID_EXCEPTIONAL_WORK_STATES,
    VALID_EXCEPTIONAL_WORK_TRIGGERS,
    ERR_SCHEMA_MISSING,
    ERR_YAML_PARSE,
    ERR_MISSING_REQUIRED_FIELD,
    ERR_UNKNOWN_FIELD,
    ERR_INVALID_STATE,
    ERR_EMPTY_LIST,
    ERR_INVALID_RISK_CLASS,
    ERR_SCOPE_LOCK_OVERLAP,
    ERR_SCHEMA_VALIDATION,
    load_yaml,
    load_lean_schema,
)

_FAILURES: list[tuple[str, str, str]] = []  # (error_code, source, message)


def _fail(code: str, source: str, message: str) -> None:
    _FAILURES.append((code, source, message))
    print(f"[FAIL] {code} {source}: {message}")


def _pass(source: str, message: str) -> None:
    print(f"[PASS] {source}: {message}")


# ---------------------------------------------------------------------------
# Schema presence check
# ---------------------------------------------------------------------------

def check_lean_schemas_exist() -> dict:
    """Load and return all lean schemas; fail for any that are missing."""
    loaded = {}
    for name, filename in sorted(LEAN_SCHEMA_FILES.items()):
        path = LEAN_SCHEMAS_DIR / filename
        if not path.exists():
            _fail(ERR_SCHEMA_MISSING, filename, "lean schema file not found")
            continue
        try:
            schema = load_yaml(path)
            loaded[name] = schema
            _pass(filename, "schema found and parses")
        except yaml.YAMLError as exc:
            _fail(ERR_YAML_PARSE, filename, f"YAML parse error: {exc}")
    return loaded


# ---------------------------------------------------------------------------
# Generic JSON Schema validation
# ---------------------------------------------------------------------------

def _validate_against_schema(doc: dict, schema: dict, source: str) -> bool:
    try:
        jsonschema.validate(instance=doc, schema=schema)
        return True
    except jsonschema.ValidationError as exc:
        _fail(ERR_SCHEMA_VALIDATION, source, exc.message)
        return False
    except jsonschema.SchemaError as exc:
        _fail(ERR_SCHEMA_VALIDATION, source, f"schema itself is invalid: {exc.message}")
        return False


# ---------------------------------------------------------------------------
# Lean-specific semantic checks (layered on top of JSON Schema)
# ---------------------------------------------------------------------------

def _check_worker_handoff_semantics(doc: dict, source: str) -> None:
    """Additional semantic rules not expressible in JSON Schema alone."""
    scope = doc.get("scope") or []
    lock = doc.get("lock") or []

    # Scope and lock must be distinct (syntactic overlap check)
    overlap = sorted(set(scope) & set(lock))
    if overlap:
        _fail(
            ERR_SCOPE_LOCK_OVERLAP,
            source,
            f"scope and lock share paths — edits to these would be impossible: {overlap}",
        )

    # accept must be non-empty (also enforced by JSON Schema minItems:1, but explicit here)
    accept = doc.get("accept")
    if accept is not None and len(accept) == 0:
        _fail(ERR_EMPTY_LIST, source, "accept must be non-empty")

    # deliver must be non-empty
    deliver = doc.get("deliver")
    if deliver is not None and len(deliver) == 0:
        _fail(ERR_EMPTY_LIST, source, "deliver must be non-empty")

    # risk must be a supported class
    risk = doc.get("risk")
    if risk is not None and risk not in VALID_RISK_CLASSES:
        _fail(ERR_INVALID_RISK_CLASS, source, f"risk '{risk}' is not a supported risk class")


def _check_trial_rule_semantics(doc: dict, source: str) -> None:
    state = doc.get("state")
    if state and state not in VALID_TRIAL_RULE_STATES:
        _fail(ERR_INVALID_STATE, source, f"state '{state}' is not a valid trial rule state")

    if state == "superseded" and not doc.get("superseded_by"):
        _fail(ERR_MISSING_REQUIRED_FIELD, source, "state=superseded requires superseded_by")


def _check_exceptional_work_semantics(doc: dict, source: str) -> None:
    trigger = doc.get("trigger")
    if trigger and trigger not in VALID_EXCEPTIONAL_WORK_TRIGGERS:
        _fail(ERR_INVALID_STATE, source, f"trigger '{trigger}' is not a supported trigger")

    state = doc.get("state")
    if state and state not in VALID_EXCEPTIONAL_WORK_STATES:
        _fail(ERR_INVALID_STATE, source, f"state '{state}' is not a valid exceptional work state")

    if state == "resolved" and not doc.get("resolution"):
        _fail(
            ERR_MISSING_REQUIRED_FIELD,
            source,
            "state=resolved requires a non-empty resolution",
        )


# ---------------------------------------------------------------------------
# File-based validation
# ---------------------------------------------------------------------------

def _load_doc(path: Path) -> dict | None:
    try:
        doc = load_yaml(path)
        if doc is None:
            _fail(ERR_YAML_PARSE, path.name, "file is empty")
            return None
        return doc
    except yaml.YAMLError as exc:
        _fail(ERR_YAML_PARSE, path.name, f"YAML parse error: {exc}")
        return None


def validate_file(path: Path, schema_name: str, schemas: dict) -> bool:
    doc = _load_doc(path)
    if doc is None:
        return False

    schema = schemas.get(schema_name)
    if schema is None:
        _fail(ERR_SCHEMA_MISSING, path.name, f"schema '{schema_name}' not loaded, cannot validate")
        return False

    ok = _validate_against_schema(doc, schema, path.name)

    # Semantic checks run regardless of JSON Schema result (they produce independent errors)
    if schema_name == "worker_handoff":
        _check_worker_handoff_semantics(doc, path.name)
    elif schema_name == "trial_rule":
        _check_trial_rule_semantics(doc, path.name)
    elif schema_name == "exceptional_work":
        _check_exceptional_work_semantics(doc, path.name)

    if ok:
        _pass(path.name, "valid")
    return ok


# ---------------------------------------------------------------------------
# Directory scan
# ---------------------------------------------------------------------------

FIXTURE_DIR_TO_SCHEMA = {
    # Map fixture directory base-names to schema names.
    # Used for directory-mode validation.
}


def validate_directory(directory: Path, schema_name: str, schemas: dict) -> int:
    """Validate all YAML files in directory against the named schema."""
    count = 0
    for path in sorted(directory.iterdir()):
        if path.suffix in (".yaml", ".yml"):
            validate_file(path, schema_name, schemas)
            count += 1
    return count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Lean POS offline validator. No network access.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate a single file with explicit schema:
  python tools/pos/lean/validate.py --file project/lean/fixtures/valid/worker-handoff.yaml \\
    --schema worker_handoff

  # Validate all fixtures in the repo:
  python tools/pos/lean/validate.py --all-fixtures

  # Validate only valid fixtures (expect all to pass):
  python tools/pos/lean/validate.py --fixture-dir project/lean/fixtures/valid \\
    --schema worker_handoff
""",
    )
    p.add_argument("--file", type=Path, help="Single YAML file to validate")
    p.add_argument(
        "--schema",
        choices=list(LEAN_SCHEMA_FILES.keys()),
        help="Schema name to validate against",
    )
    p.add_argument("--all-fixtures", action="store_true", help="Validate all lean fixture files")
    p.add_argument("--fixture-dir", type=Path, help="Directory of YAML files to validate")
    return p


def _infer_schema(path: Path) -> str | None:
    """Infer schema from filename convention."""
    name = path.stem
    if "project-state" in name or "project_state" in name:
        return "project_state"
    if "trial-rule" in name or "trial_rule" in name:
        return "trial_rule"
    if "exceptional-work" in name or "exceptional_work" in name:
        return "exceptional_work"
    if "worker-handoff" in name or "worker_handoff" in name:
        return "worker_handoff"
    return None


def run_all_fixtures(schemas: dict) -> None:
    fixtures_dir = REPO_ROOT / "project" / "lean" / "fixtures"
    if not fixtures_dir.is_dir():
        _fail(ERR_SCHEMA_MISSING, "fixtures", f"fixtures directory not found: {fixtures_dir}")
        return

    for path in sorted(fixtures_dir.rglob("*.yaml")):
        schema_name = _infer_schema(path)
        if schema_name is None:
            print(f"[WARNING] {path.name}: cannot infer schema, skipping")
            continue
        validate_file(path, schema_name, schemas)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    print("=" * 60)
    print("Lean POS Offline Validator")
    print("No network access. No mutations. No authority statements.")
    print("=" * 60)

    schemas = check_lean_schemas_exist()

    if args.all_fixtures:
        run_all_fixtures(schemas)
    elif args.file and args.schema:
        if not args.file.exists():
            _fail(ERR_YAML_PARSE, str(args.file), "file not found")
        else:
            validate_file(args.file, args.schema, schemas)
    elif args.fixture_dir and args.schema:
        if not args.fixture_dir.is_dir():
            _fail(ERR_YAML_PARSE, str(args.fixture_dir), "directory not found")
        else:
            validate_directory(args.fixture_dir, args.schema, schemas)
    else:
        parser.print_help()
        return 2

    print("=" * 60)
    print(f"Failures: {len(_FAILURES)}")
    if _FAILURES:
        # Errors are emitted in deterministic order (discovery order, sorted by code+source)
        print("[FAIL] Validation failed.")
        return 1
    print("[PASS] All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
