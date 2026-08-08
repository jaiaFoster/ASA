"""SPRINT-014 S14-PR-05A, Architect checkpoint: sixteenth review ("PASS --
authorize production-root wiring of both scheduled and API refresh"),
required evidence: "architecture tests forbid direct raw-fulfillment
strategy binding at the live roots and prevent strategy-ID branches in
generic orchestration." The strategy-ID-branch half is covered by
tests/architecture/test_orchestration_boundaries.py; this file covers the
raw-fulfillment-binding half, at the two production composition roots
themselves (asa/scheduled_screening.py, asa/api/screening_routes.py).

An AST sweep, not a text/regex scan, so a cosmetic rename or reformat
can't silently defeat it the way a substring check could.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SCHEDULED = _ROOT / "asa" / "scheduled_screening.py"
_API = _ROOT / "asa" / "api" / "screening_routes.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text())


def _imported_names(tree: ast.Module, module: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def _registry_builder_call_sites(tree: ast.Module) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "build_migrated_strategy_registry"
    ]


def _argument_attribute_name(call: ast.Call) -> str | None:
    """The final ``.attr`` of the call's one positional argument, e.g.
    "plan_backed_fulfillment" for ``item.plan_backed_fulfillment`` -- None
    for a bare Name argument (e.g. UNBOUND_FULFILLMENT, permitted only at
    a metadata-only composition root, never at a live evaluation path).
    """
    assert len(call.args) == 1, "build_migrated_strategy_registry takes exactly one argument"
    argument = call.args[0]
    if isinstance(argument, ast.Attribute):
        return argument.attr
    return None


class TestNoRawFulfillmentStrategyBindingAtLiveRoots:
    """Both production roots must register their live strategy adapters
    against a subject's own PlanBackedFulfillment (Architect checkpoint:
    sixteenth review, "then build the legacy registry over that
    PlanBackedFulfillment, never the raw fulfillment service") -- never
    the bare ``.fulfillment`` a SubjectMarketDataAccess also exposes.
    """

    def test_scheduled_screening_binds_only_plan_backed_fulfillment(self) -> None:
        call_sites = _registry_builder_call_sites(_tree(_SCHEDULED))
        assert call_sites, "expected at least one build_migrated_strategy_registry call"
        for call in call_sites:
            attribute = _argument_attribute_name(call)
            assert attribute == "plan_backed_fulfillment", (
                f"scheduled_screening.py binds a live strategy registry to "
                f".{attribute} at line {call.lineno} -- expected "
                f".plan_backed_fulfillment, never the raw fulfillment service"
            )

    def test_screening_routes_binds_only_plan_backed_fulfillment_or_unbound(self) -> None:
        call_sites = _registry_builder_call_sites(_tree(_API))
        assert call_sites, "expected at least one build_migrated_strategy_registry call"
        for call in call_sites:
            attribute = _argument_attribute_name(call)
            assert attribute == "plan_backed_fulfillment", (
                f"screening_routes.py binds a live strategy registry to "
                f".{attribute} at line {call.lineno} -- expected "
                f".plan_backed_fulfillment, never the raw fulfillment service"
            )


class TestBothRootsCallTheSharedShadowSeamNotRawRefresh:
    """Both roots must call strategy_runtime.orchestration.refresh_with_shadow()
    -- the one shared seam -- never strategy_runtime.service.refresh()
    directly (Architect checkpoint: sixteenth review, "neither calls
    strategy_runtime.service.refresh() directly anymore").
    """

    def test_scheduled_screening_imports_refresh_with_shadow_not_refresh(self) -> None:
        tree = _tree(_SCHEDULED)
        assert "refresh_with_shadow" in _imported_names(tree, "strategy_runtime.orchestration")
        assert "refresh" not in _imported_names(tree, "strategy_runtime.service")

    def test_screening_routes_imports_refresh_with_shadow_not_refresh(self) -> None:
        tree = _tree(_API)
        assert "refresh_with_shadow" in _imported_names(tree, "strategy_runtime.orchestration")
        assert "refresh" not in _imported_names(tree, "strategy_runtime.service")


class TestBothRootsBuildExactlyOnePlanPerSubject:
    """build_subject_acquisition_access() (one SubjectAcquisitionPlan +
    PlanBackedFulfillment) must be called exactly once per subject, never
    once per (strategy, subject) pair -- a lexical proxy for that: it must
    never appear textually inside this module's own per-pair loop body,
    only in a per-subject construction context. Both roots already prove
    the real one-plan-per-subject/invocation property behaviorally (see
    tests/asa/test_scheduled_screening.py and
    tests/asa/test_screening_refresh_route.py); this is the structural
    companion check.
    """

    def test_scheduled_screening_calls_build_subject_acquisition_access_once_lexically(
        self,
    ) -> None:
        tree = _tree(_SCHEDULED)
        call_sites = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "build_subject_acquisition_access"
        ]
        assert len(call_sites) == 1, (
            "expected exactly one lexical build_subject_acquisition_access call "
            "site (a per-subject dict comprehension), not one inside the "
            "per-pair loop"
        )

    def test_screening_routes_calls_build_subject_acquisition_access_once_lexically(self) -> None:
        tree = _tree(_API)
        call_sites = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "build_subject_acquisition_access"
        ]
        assert len(call_sites) == 1
