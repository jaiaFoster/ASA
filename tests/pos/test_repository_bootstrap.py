"""
Tests for the ASA2 POS repository bootstrap state.

Rules:
- Never modify a real frozen file.
- Use temporary copies for hash-mismatch tests.
- All tests are read-only with respect to canonical records.
"""

import hashlib
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.pos.schemas import (
    MANIFEST_PATH,
    BOOTSTRAP_STATUS_PATH,
    ROLE_REGISTRY_PATH,
    SCHEMAS_DIR,
    SCHEMA_FILES,
    REQUIRED_DIRECTORIES,
    GENERATED_FILE_WARNING,
    sha256_file,
    load_yaml,
)


# ---------------------------------------------------------------------------
# 1. Required directories exist
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("directory", REQUIRED_DIRECTORIES)
def test_required_directory_exists(directory):
    assert (REPO_ROOT / directory).is_dir(), f"Required directory missing: {directory}"


# ---------------------------------------------------------------------------
# 2. Manifest parses
# ---------------------------------------------------------------------------

def test_manifest_parses():
    assert MANIFEST_PATH.exists(), "governance/manifest.yaml not found"
    data = load_yaml(MANIFEST_PATH)
    assert data is not None
    assert "documents" in data
    assert isinstance(data["documents"], list)


# ---------------------------------------------------------------------------
# 3. Frozen governance hashes match manifest
# ---------------------------------------------------------------------------

def test_frozen_hashes_match_manifest():
    data = load_yaml(MANIFEST_PATH)
    mismatches = []
    for doc in data["documents"]:
        if doc.get("status") == "missing":
            continue
        filename = doc.get("filename")
        expected = doc.get("sha256")
        if not filename or not expected:
            continue
        path = REPO_ROOT / filename
        assert path.exists(), f"File listed in manifest not found: {filename}"
        actual = sha256_file(path)
        if actual != expected:
            mismatches.append(f"{doc['id']}: expected {expected[:16]}... got {actual[:16]}...")
    assert not mismatches, "Hash mismatches:\n" + "\n".join(mismatches)


# ---------------------------------------------------------------------------
# 4. Bootstrap status parses
# ---------------------------------------------------------------------------

def test_bootstrap_status_parses():
    assert BOOTSTRAP_STATUS_PATH.exists()
    data = load_yaml(BOOTSTRAP_STATUS_PATH)
    assert data is not None
    assert "project" in data
    assert "phase" in data


# ---------------------------------------------------------------------------
# 5. Role registry parses
# ---------------------------------------------------------------------------

def test_role_registry_parses():
    assert ROLE_REGISTRY_PATH.exists()
    data = load_yaml(ROLE_REGISTRY_PATH)
    assert data is not None
    assert "roles" in data
    assert isinstance(data["roles"], list)
    assert len(data["roles"]) >= 1


# ---------------------------------------------------------------------------
# 6. All six schemas parse
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("schema_file", SCHEMA_FILES)
def test_schema_parses(schema_file):
    path = SCHEMAS_DIR / schema_file
    assert path.exists(), f"Schema file missing: {schema_file}"
    data = load_yaml(path)
    assert data is not None


# ---------------------------------------------------------------------------
# 7. Validator succeeds on committed state
# ---------------------------------------------------------------------------

def test_validator_passes():
    result = subprocess.run(
        [sys.executable, "tools/pos/validate.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Validator failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "[PASS] All checks passed." in result.stdout


# ---------------------------------------------------------------------------
# 8. Validator fails when a frozen hash is intentionally wrong (fixture test)
# ---------------------------------------------------------------------------

def test_validator_fails_on_bad_hash(tmp_path):
    # Copy the repo structure to a temp location and corrupt one hash in manifest
    repo_copy = tmp_path / "ASA"
    shutil.copytree(REPO_ROOT, repo_copy, ignore=shutil.ignore_patterns(".git"))

    manifest_path = repo_copy / "governance" / "manifest.yaml"
    data = load_yaml(manifest_path)

    # Find the first frozen document with a real hash
    for doc in data["documents"]:
        if doc.get("status") != "missing" and doc.get("sha256"):
            doc["sha256"] = "0" * 64  # intentionally wrong
            break

    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    result = subprocess.run(
        [sys.executable, "tools/pos/validate.py"],
        cwd=repo_copy,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "Validator should have failed on bad hash"
    assert "[FAIL]" in result.stdout


# ---------------------------------------------------------------------------
# 9. Generator output is deterministic
# ---------------------------------------------------------------------------

def test_generator_is_deterministic(tmp_path):
    # Run generator twice and compare outputs
    outputs = []
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "tools/pos/generate.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Generator failed: {result.stderr}"

        generated = {}
        generated_dir = REPO_ROOT / "project" / "generated"
        for f in ["AGENTS.md", "CURRENT_STATE.md", "MANAGER_INBOX.md"]:
            path = generated_dir / f
            if path.exists():
                content = path.read_text(encoding="utf-8")
                # Strip timestamp lines for determinism comparison
                lines = [l for l in content.splitlines() if "Generated:" not in l]
                generated[f] = "\n".join(lines)
        outputs.append(generated)

    for filename in outputs[0]:
        assert outputs[0][filename] == outputs[1][filename], (
            f"Generator is not deterministic for {filename}"
        )


# ---------------------------------------------------------------------------
# 10. Generated files contain the generated-file warning
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", ["AGENTS.md", "CURRENT_STATE.md", "MANAGER_INBOX.md"])
def test_generated_files_contain_warning(filename):
    path = REPO_ROOT / "project" / "generated" / filename
    assert path.exists(), f"Generated file missing: project/generated/{filename}"
    content = path.read_text(encoding="utf-8")
    assert "THIS FILE IS GENERATED" in content
    assert "DO NOT EDIT MANUALLY" in content
