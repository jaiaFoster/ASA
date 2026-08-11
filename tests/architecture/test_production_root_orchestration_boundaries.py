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


def _local_call_assignments(tree: ast.Module) -> dict[str, ast.Call]:
    """Map every simple ``name = Call(...)`` assignment's own target name
    to that Call node -- lets _wraps_plan_backed_fulfillment resolve a
    registry-builder argument through one level of local-variable
    indirection (e.g. ``tracker = TouchedResultFulfillment(item.
    plan_backed_fulfillment)`` then ``build_migrated_strategy_registry
    (tracker)``), never by trusting a bare Name at face value.
    """
    assignments: dict[str, ast.Call] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
        ):
            assignments[node.targets[0].id] = node.value
    return assignments


def _ends_in_plan_backed_fulfillment(node: ast.expr) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "plan_backed_fulfillment"


def _wraps_plan_backed_fulfillment(argument: ast.expr, assignments: dict[str, ast.Call]) -> bool:
    """True if ``argument`` is either .plan_backed_fulfillment directly,
    or a local name assigned from ``TouchedResultFulfillment(<something
    ending in .plan_backed_fulfillment>)`` -- the one permitted level of
    indirection a per-pair provenance tracker introduces. Never resolves
    through any other function/wrapper, and never trusts a bare Name on
    its own -- an untraceable Name (e.g. UNBOUND_FULFILLMENT, or a
    variable assigned some other way) fails.
    """
    if _ends_in_plan_backed_fulfillment(argument):
        return True
    if not isinstance(argument, ast.Name):
        return False
    assigned = assignments.get(argument.id)
    if assigned is None or not isinstance(assigned.func, ast.Name):
        return False
    if assigned.func.id != "TouchedResultFulfillment" or len(assigned.args) != 1:
        return False
    return _ends_in_plan_backed_fulfillment(assigned.args[0])


class TestNoRawFulfillmentStrategyBindingAtLiveRoots:
    """Both production roots must register their live strategy adapters
    against a subject's own PlanBackedFulfillment (Architect checkpoint:
    sixteenth review, "then build the legacy registry over that
    PlanBackedFulfillment, never the raw fulfillment service") -- never
    the bare ``.fulfillment`` a SubjectMarketDataAccess also exposes.
    Resolved through at most one local TouchedResultFulfillment wrapper
    (Architect checkpoint: seventeenth review, provenance tracking).
    """

    def test_scheduled_screening_binds_only_plan_backed_fulfillment(self) -> None:
        tree = _tree(_SCHEDULED)
        assignments = _local_call_assignments(tree)
        call_sites = _registry_builder_call_sites(tree)
        assert call_sites, "expected at least one build_migrated_strategy_registry call"
        for call in call_sites:
            assert len(call.args) == 1
            assert _wraps_plan_backed_fulfillment(call.args[0], assignments), (
                f"scheduled_screening.py binds a live strategy registry at line "
                f"{call.lineno} to something other than .plan_backed_fulfillment "
                f"(directly, or via one TouchedResultFulfillment wrapper) -- "
                f"never the raw fulfillment service"
            )

    def test_screening_routes_binds_only_plan_backed_fulfillment_or_unbound(self) -> None:
        tree = _tree(_API)
        assignments = _local_call_assignments(tree)
        call_sites = _registry_builder_call_sites(tree)
        assert call_sites, "expected at least one build_migrated_strategy_registry call"
        for call in call_sites:
            assert len(call.args) == 1
            assert _wraps_plan_backed_fulfillment(call.args[0], assignments), (
                f"screening_routes.py binds a live strategy registry at line "
                f"{call.lineno} to something other than .plan_backed_fulfillment "
                f"(directly, or via one TouchedResultFulfillment wrapper) -- "
                f"never the raw fulfillment service"
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
