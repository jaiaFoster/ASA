"""SPRINT-014 S14-PR-04: architecture boundaries for snapshot sealing,
canonical projection, and derived-fact materialization.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).parents[2]
_FORBIDDEN_DOWNSTREAM = {"screening", "strategies", "strategy_runtime", "asa"}


def _imported_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _check(relative_path: str, permitted: set[str]) -> None:
    tree = ast.parse((_ROOT / relative_path).read_text())
    roots = _imported_roots(tree)
    downstream = roots & _FORBIDDEN_DOWNSTREAM
    assert not downstream, f"{relative_path} imports downstream layers: {downstream}"
    violations = roots - permitted
    assert not violations, f"{relative_path} imports outside its permitted roots: {violations}"


def test_subject_snapshot_boundaries() -> None:
    _check("market_data/subject_snapshot.py", {"__future__", "datetime", "domain", "market_data"})


def test_canonical_projection_boundaries() -> None:
    _check(
        "facts/canonical_projection.py",
        {"__future__", "datetime", "domain", "market_data"},
    )


def test_derived_fact_materialization_boundaries() -> None:
    _check(
        "analytics/derived_fact_materialization.py",
        # "hashlib"/"json" added (SPRINT-014 S14-PR-05A, Architect
        # checkpoint: seventh review, I-07 parameter identity): the same
        # canonical-json-then-sha256 hashing pattern
        # analytics/features.py's own DerivedFact.identity already uses,
        # now needed here too to fold a selection-dependent feature's own
        # parameters into its derived_fact_id.
        {"__future__", "datetime", "domain", "analytics", "hashlib", "json"},
    )
