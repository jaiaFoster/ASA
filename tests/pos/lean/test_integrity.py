"""Tests for tools/pos/lean/check_integrity.py — I001-I005 error codes."""
import hashlib
import shutil
import textwrap
from pathlib import Path

import pytest
import yaml

from tools.pos.lean.check_integrity import check_integrity


@pytest.fixture()
def tmp_repo(tmp_path):
    frozen = tmp_path / "governance" / "frozen"
    frozen.mkdir(parents=True)
    manifest = tmp_path / "governance" / "manifest.yaml"
    return tmp_path, frozen, manifest


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_manifest(manifest_path, documents):
    manifest_path.write_text(yaml.dump({"documents": documents}, sort_keys=False))


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_clean_repo_exits_no_errors(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        content = b"frozen content"
        f = frozen / "DOC-001.md"
        f.write_bytes(content)
        _write_manifest(manifest, [
            {"id": "DOC-001", "filename": "governance/frozen/DOC-001.md",
             "status": "frozen", "sha256": _sha256(content)}
        ])
        assert check_integrity(manifest, tmp_path) == []

    def test_non_frozen_entries_skipped(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        _write_manifest(manifest, [
            {"id": "AMD-001", "filename": "governance/amendments/AMD-001.md",
             "status": "active", "sha256": "irrelevant"}
        ])
        assert check_integrity(manifest, tmp_path) == []

    def test_multiple_frozen_files_all_pass(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        entries = []
        for i in range(3):
            content = f"content {i}".encode()
            f = frozen / f"DOC-{i:03d}.md"
            f.write_bytes(content)
            entries.append({"id": f"DOC-{i:03d}", "filename": f"governance/frozen/DOC-{i:03d}.md",
                             "status": "frozen", "sha256": _sha256(content)})
        _write_manifest(manifest, entries)
        assert check_integrity(manifest, tmp_path) == []


# ---------------------------------------------------------------------------
# I001 INVALID_MANIFEST
# ---------------------------------------------------------------------------

class TestI001InvalidManifest:
    def test_unparseable_yaml(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        manifest.write_text(": : : invalid {{{{")
        errors = check_integrity(manifest, tmp_path)
        assert any("I001" in e for e in errors)

    def test_missing_documents_key(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        manifest.write_text(yaml.dump({"frozen_document_policy": {}}))
        errors = check_integrity(manifest, tmp_path)
        assert any("I001" in e for e in errors)

    def test_documents_not_list(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        manifest.write_text(yaml.dump({"documents": "not a list"}))
        errors = check_integrity(manifest, tmp_path)
        assert any("I001" in e for e in errors)

    def test_frozen_entry_no_filename(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        _write_manifest(manifest, [
            {"id": "DOC-X", "status": "frozen", "sha256": "abc"}
        ])
        errors = check_integrity(manifest, tmp_path)
        assert any("I001" in e and "DOC-X" in e for e in errors)

    def test_frozen_entry_no_hash(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        content = b"data"
        f = frozen / "DOC-Y.md"
        f.write_bytes(content)
        _write_manifest(manifest, [
            {"id": "DOC-Y", "filename": "governance/frozen/DOC-Y.md", "status": "frozen"}
        ])
        errors = check_integrity(manifest, tmp_path)
        assert any("I001" in e and "DOC-Y" in e for e in errors)


# ---------------------------------------------------------------------------
# I002 MISSING_FILE
# ---------------------------------------------------------------------------

class TestI002MissingFile:
    def test_declared_frozen_file_absent(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        _write_manifest(manifest, [
            {"id": "DOC-GONE", "filename": "governance/frozen/DOC-GONE.md",
             "status": "frozen", "sha256": "abc123"}
        ])
        errors = check_integrity(manifest, tmp_path)
        assert any("I002" in e and "DOC-GONE" in e for e in errors)

    def test_missing_file_error_includes_filename(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        _write_manifest(manifest, [
            {"id": "X", "filename": "governance/frozen/missing.md",
             "status": "frozen", "sha256": "abc"}
        ])
        errors = check_integrity(manifest, tmp_path)
        assert any("missing.md" in e for e in errors)


# ---------------------------------------------------------------------------
# I003 HASH_MISMATCH
# ---------------------------------------------------------------------------

class TestI003HashMismatch:
    def test_modified_content_detected(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        original = b"original content"
        f = frozen / "DOC-MOD.md"
        f.write_bytes(b"tampered content")
        _write_manifest(manifest, [
            {"id": "DOC-MOD", "filename": "governance/frozen/DOC-MOD.md",
             "status": "frozen", "sha256": _sha256(original)}
        ])
        errors = check_integrity(manifest, tmp_path)
        assert any("I003" in e and "DOC-MOD" in e for e in errors)

    def test_error_includes_expected_and_actual(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        f = frozen / "DOC-A.md"
        f.write_bytes(b"actual")
        expected = _sha256(b"different")
        _write_manifest(manifest, [
            {"id": "DOC-A", "filename": "governance/frozen/DOC-A.md",
             "status": "frozen", "sha256": expected}
        ])
        errors = check_integrity(manifest, tmp_path)
        combined = "\n".join(errors)
        assert "expected" in combined
        assert "actual" in combined

    def test_correct_hash_no_mismatch(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        content = b"exact content"
        f = frozen / "DOC-B.md"
        f.write_bytes(content)
        _write_manifest(manifest, [
            {"id": "DOC-B", "filename": "governance/frozen/DOC-B.md",
             "status": "frozen", "sha256": _sha256(content)}
        ])
        errors = check_integrity(manifest, tmp_path)
        assert not any("I003" in e for e in errors)


# ---------------------------------------------------------------------------
# I004 UNDECLARED_FROZEN_FILE
# ---------------------------------------------------------------------------

class TestI004UndeclaredFrozenFile:
    def test_extra_file_in_frozen_dir(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        (frozen / "EXTRA.md").write_bytes(b"surprise")
        _write_manifest(manifest, [])
        errors = check_integrity(manifest, tmp_path)
        assert any("I004" in e and "EXTRA.md" in e for e in errors)

    def test_declared_file_not_flagged(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        content = b"declared"
        f = frozen / "KNOWN.md"
        f.write_bytes(content)
        _write_manifest(manifest, [
            {"id": "KNOWN", "filename": "governance/frozen/KNOWN.md",
             "status": "frozen", "sha256": _sha256(content)}
        ])
        errors = check_integrity(manifest, tmp_path)
        assert not any("I004" in e for e in errors)

    def test_non_frozen_status_file_in_frozen_dir_flagged(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        content = b"active but in frozen dir"
        f = frozen / "AMD.md"
        f.write_bytes(content)
        # declared as active — still undeclared as a frozen file
        _write_manifest(manifest, [
            {"id": "AMD", "filename": "governance/frozen/AMD.md",
             "status": "active", "sha256": _sha256(content)}
        ])
        errors = check_integrity(manifest, tmp_path)
        # active entries are not added to declared_files set for frozen dir scan
        assert any("I004" in e and "AMD.md" in e for e in errors)


# ---------------------------------------------------------------------------
# I005 DUPLICATE_ENTRY
# ---------------------------------------------------------------------------

class TestI005DuplicateEntry:
    def test_duplicate_id_detected(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        content = b"dup"
        f = frozen / "DOC-DUP.md"
        f.write_bytes(content)
        h = _sha256(content)
        _write_manifest(manifest, [
            {"id": "DOC-DUP", "filename": "governance/frozen/DOC-DUP.md",
             "status": "frozen", "sha256": h},
            {"id": "DOC-DUP", "filename": "governance/frozen/DOC-DUP.md",
             "status": "frozen", "sha256": h},
        ])
        errors = check_integrity(manifest, tmp_path)
        assert any("I005" in e and "DOC-DUP" in e for e in errors)

    def test_unique_ids_no_duplicate_error(self, tmp_repo):
        tmp_path, frozen, manifest = tmp_repo
        for name in ("A", "B"):
            content = name.encode()
            (frozen / f"{name}.md").write_bytes(content)
        _write_manifest(manifest, [
            {"id": "A", "filename": "governance/frozen/A.md", "status": "frozen",
             "sha256": _sha256(b"A")},
            {"id": "B", "filename": "governance/frozen/B.md", "status": "frozen",
             "sha256": _sha256(b"B")},
        ])
        errors = check_integrity(manifest, tmp_path)
        assert not any("I005" in e for e in errors)


# ---------------------------------------------------------------------------
# Real manifest
# ---------------------------------------------------------------------------

class TestRealManifest:
    def test_real_manifest_passes(self):
        """The actual governance/manifest.yaml must pass integrity check."""
        errors = check_integrity()
        assert errors == [], "\n".join(errors)
