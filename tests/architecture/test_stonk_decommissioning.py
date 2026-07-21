"""STONK-005 legacy execution-path decommissioning invariants."""

from __future__ import annotations

import ast
from pathlib import Path

from strategies import STONK_STRATEGY_MANIFESTS

ROOT = Path(__file__).parents[2]
MIGRATED_MODULES = (
    ROOT / "strategies" / "stonk_components.py",
    ROOT / "strategies" / "stonk_manifests.py",
    ROOT / "strategies" / "stonk_plugins.py",
)
LEGACY_ROOTS = {"app", "legacy", "stonk"}


def _import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    roots.update(
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    return roots


def test_migrated_strategy_modules_have_no_legacy_runtime_imports() -> None:
    for path in MIGRATED_MODULES:
        assert not (_import_roots(path) & LEGACY_ROOTS), path


def test_migrated_strategy_modules_do_not_inject_or_load_legacy_paths() -> None:
    prohibited = ("sys.path", "import_module(", "spec_from_file_location", "SourceFileLoader")
    for path in MIGRATED_MODULES:
        source = path.read_text(encoding="utf-8")
        assert not any(token in source for token in prohibited), path


def test_supported_boundary_is_four_canonical_manifests_not_legacy_services() -> None:
    assert tuple(manifest.strategy_id for manifest in STONK_STRATEGY_MANIFESTS) == (
        "asa.stonk.earnings_calendar",
        "asa.stonk.skew_momentum_vertical",
        "asa.stonk.forward_factor_calendar",
        "asa.stonk.stock_momentum",
    )
    assert not (ROOT / "legacy").exists()
    assert not (ROOT / "stonk").exists()


def test_decommissioning_decision_is_documented() -> None:
    document = (ROOT / "docs" / "migration" / "stonk-decommissioning.md").read_text(
        encoding="utf-8"
    )
    assert "Compatibility runtime" in document
    assert "Not required and not created" in document
    assert "can therefore be removed" in document
    assert "manifest → compiled" in document
    assert "graph → registered Components" in document
