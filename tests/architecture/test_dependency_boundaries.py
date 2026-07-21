"""ASA-CORE-001: enforce ADR-004's one-way dependency rule via import analysis.

Scans every Python file in each layer package with the AST module and asserts
that no module imports a module above it in the pipeline order:

    providers -> observation -> reconciliation -> facts -> indicators
        -> strategies -> guardrails -> ranking -> presentation

Each module may import itself, `domain`, and modules strictly below it.
`presentation` is narrower: only `ranking` and `domain` (ADR-004 revision).
`domain` imports nothing but itself. `reconciliation` occupies the Canonical
Fact Layer's pipeline position alongside `facts` (ADR-004 revision,
ASA-CORE-003): `facts/` owns storage/versioning orchestration and depends on
`reconciliation/`'s pure, repository-free reconciliation logic; nothing in
`reconciliation/` depends on `facts/`.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

PIPELINE_ORDER = [
    "providers",
    "observation",
    "reconciliation",
    "facts",
    "indicators",
    "strategies",
    "guardrails",
    "ranking",
    "presentation",
]

ALL_LAYERS = set(PIPELINE_ORDER) | {"domain"}


def _allowed_imports(layer: str) -> set[str]:
    if layer == "domain":
        return {"domain"}
    if layer == "presentation":
        # Narrowed rule (ADR-004): ranking and domain only.
        return {"presentation", "ranking", "domain"}
    if layer == "indicators":
        # Narrowed rule (ADR-004, ASA-CORE-004): facts, reconciliation, domain
        # only — not observation or providers, despite sitting below in the
        # general pipeline order.
        return {"indicators", "facts", "reconciliation", "domain"}
    idx = PIPELINE_ORDER.index(layer)
    return set(PIPELINE_ORDER[: idx + 1]) | {"domain"}


def _imported_roots(py_file: Path) -> set[str]:
    """Top-level module names imported by a Python file."""
    tree = ast.parse(py_file.read_text())
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


def _layer_files(layer: str) -> list[Path]:
    return sorted((REPO_ROOT / layer).rglob("*.py"))


@pytest.mark.parametrize("layer", sorted(ALL_LAYERS))
def test_layer_respects_dependency_boundary(layer):
    allowed = _allowed_imports(layer)
    violations = []
    for py_file in _layer_files(layer):
        forbidden = (_imported_roots(py_file) & ALL_LAYERS) - allowed
        if forbidden:
            violations.append(f"{py_file.relative_to(REPO_ROOT)} imports {sorted(forbidden)}")
    assert not violations, (
        f"{layer}/ violates ADR-004 dependency rule "
        f"(allowed: {sorted(allowed)}):\n" + "\n".join(violations)
    )


def test_presentation_allowed_set_is_narrowed():
    """Guard the guard: the narrowed rule must not regress to the general rule."""
    assert _allowed_imports("presentation") == {"presentation", "ranking", "domain"}


def test_nothing_imports_presentation():
    """presentation/ is terminal — no other layer may depend on it (ADR-004)."""
    violations = []
    for layer in sorted(ALL_LAYERS - {"presentation"}):
        for py_file in _layer_files(layer):
            if "presentation" in _imported_roots(py_file):
                violations.append(str(py_file.relative_to(REPO_ROOT)))
    assert not violations, f"Modules import terminal layer presentation/: {violations}"


def test_domain_imports_no_layer():
    """domain/ is shared and must not depend on any pipeline layer."""
    violations = []
    for py_file in _layer_files("domain"):
        forbidden = _imported_roots(py_file) & set(PIPELINE_ORDER)
        if forbidden:
            violations.append(f"{py_file.relative_to(REPO_ROOT)} imports {sorted(forbidden)}")
    assert not violations, "domain/ must not import pipeline layers:\n" + "\n".join(violations)
