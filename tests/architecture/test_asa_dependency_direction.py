"""ARCH-MONOREPO-001 Phase 2C: formalize the one-directional dependency between
asa/ (the deployable application, consolidated to the repository root by
Phase 2B) and every other root-level package.

Phase 1's ADR (architecture/ASA-ARCH-MONOREPO-001-Packaging-Consolidation-
ADR.md) confirmed empirically that asa/ imports root-level packages (e.g.
screening.state) but nothing outside asa/ ever imports from it -- the single
fact that makes consolidating asa/ into a plain sibling of screening/,
market_data/, etc. safe in the first place: there is no cycle to introduce.
This test protects that fact going forward, the same way
tests/architecture/test_dependency_boundaries.py protects ADR-004's own
pipeline-layer ordering.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Every root-level package with its own __init__.py, excluding asa/ itself,
# tests/, and tools/ (not application packages).
ROOT_PACKAGES = sorted(
    path.name
    for path in REPO_ROOT.iterdir()
    if path.is_dir()
    and (path / "__init__.py").exists()
    and path.name not in {"asa", "tests", "tools"}
)


def _imported_roots(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text())
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_root_packages_exist() -> None:
    """Guard the guard: fail loudly if package discovery itself breaks,
    rather than silently parametrizing over zero packages."""
    assert len(ROOT_PACKAGES) >= 15, ROOT_PACKAGES


@pytest.mark.parametrize("package", ROOT_PACKAGES)
def test_root_package_does_not_import_asa(package: str) -> None:
    violations = [
        str(py_file.relative_to(REPO_ROOT))
        for py_file in sorted((REPO_ROOT / package).rglob("*.py"))
        if "asa" in _imported_roots(py_file)
    ]
    assert not violations, (
        f"{package}/ imports asa/ -- this would introduce a dependency cycle "
        f"(asa/ imports root packages; root packages must never import back): "
        + ", ".join(violations)
    )


def test_asa_does_import_at_least_one_root_package() -> None:
    """Guard the guard: confirm asa/'s own side of the relationship still
    holds (it is the whole reason this package layout is safe to
    consolidate) rather than this test suite silently passing because
    asa/ stopped importing anything at all."""
    imported = set()
    for py_file in sorted((REPO_ROOT / "asa").rglob("*.py")):
        imported |= _imported_roots(py_file) & set(ROOT_PACKAGES)
    assert imported, "asa/ no longer imports any root-level package"
