"""ASA-CORE-001: repository scaffold matches ADR-004."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

ADR_004_PACKAGES = [
    "providers",
    "observation",
    "facts",
    "indicators",
    "strategies",
    "strategies/capabilities",
    "guardrails",
    "ranking",
    "presentation",
    "domain",
]


@pytest.mark.parametrize("pkg", ADR_004_PACKAGES)
def test_package_exists(pkg):
    path = REPO_ROOT / pkg
    assert path.is_dir(), f"ADR-004 package missing: {pkg}/"
    assert (path / "__init__.py").is_file(), f"{pkg}/ is not a package (no __init__.py)"


@pytest.mark.parametrize("pkg", ADR_004_PACKAGES)
def test_package_documents_its_boundary(pkg):
    """Each package's __init__ docstring states what it owns (ADR-004)."""
    content = (REPO_ROOT / pkg / "__init__.py").read_text()
    assert '"""' in content, f"{pkg}/__init__.py has no docstring"


def test_presentation_docstring_states_narrowed_rule():
    content = (REPO_ROOT / "presentation" / "__init__.py").read_text()
    assert "ranking" in content and "domain" in content, (
        "presentation/__init__.py must document its narrowed dependency rule (ADR-004)"
    )
