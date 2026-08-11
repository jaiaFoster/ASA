"""SPRINT-014 S14-PR-05A, Architect checkpoint: ninth review -- "the
orchestrator that invokes bindings must be generic and registry/callback-
driven, never if strategy_id == 'earnings_calendar'". These tests enforce
that directly against strategy_runtime/knowledge.py, knowledge_registry.py,
and knowledge_composition.py's own source, mirroring
tests/architecture/test_subject_planning_boundaries.py's substring-sweep
pattern for screening/subject_planning.py.
"""

from __future__ import annotations

import ast
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "strategy_runtime"
_MODULES = (
    _PACKAGE_ROOT / "knowledge.py",
    _PACKAGE_ROOT / "knowledge_registry.py",
    _PACKAGE_ROOT / "knowledge_composition.py",
)

# Strategy-specific names that would signal the generic composition seam
# has stopped being generic -- Earnings Calendar's own payload, binding,
# fact_types, or structural selection must never appear here, textually or
# as an import.
_PROHIBITED_SOURCE_SUBSTRINGS = (
    "earnings_calendar",
    "EarningsCalendar",
    "EARNINGS_CALENDAR",
    "front_contract_id",
    "back_contract_id",
    "term_structure",
    "atm_iv_vs_realized",
    "forward_factor",
    "skew_momentum",
)


def _source(module: Path) -> str:
    return module.read_text()


def _imported_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_only_permitted_roots() -> None:
    permitted = {
        "__future__",
        "analytics",
        "collections",
        "dataclasses",
        "datetime",
        "domain",
        "facts",
        "market_data",
        "screening",
        "strategy_runtime",
        "typing",
    }
    for module in _MODULES:
        imported = _imported_roots(ast.parse(_source(module)))
        assert imported <= permitted, (
            f"{module.name} imports outside {permitted}: {imported - permitted}"
        )


def test_never_imports_strategy_specific_packages() -> None:
    forbidden = {"strategies", "asa"}
    for module in _MODULES:
        imported = _imported_roots(ast.parse(_source(module)))
        assert not (imported & forbidden), f"{module.name} imports: {imported & forbidden}"


def test_source_never_names_a_strategy_payload_binding_or_fact() -> None:
    for module in _MODULES:
        source = _source(module)
        found = [needle for needle in _PROHIBITED_SOURCE_SUBSTRINGS if needle in source]
        assert not found, f"{module.name} names strategy-specific identifiers: {found}"


def test_no_conditional_branches_on_a_string_literal_at_all() -> None:
    """The strongest available proxy for "never branches on a strategy
    identity": no comparison anywhere in these modules compares anything
    against a string constant. strategy_id is only ever used as a dict/
    registry key -- looked up, stored, returned -- never compared.
    """
    for module in _MODULES:
        tree = ast.parse(_source(module))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            operands = (node.left, *node.comparators)
            for operand in operands:
                if isinstance(operand, ast.Constant) and isinstance(operand.value, str):
                    raise AssertionError(
                        f"{module.name} compares against a string literal "
                        f"{operand.value!r} at line {node.lineno} -- the generic "
                        "composition seam must never branch on strategy identity"
                    )


def test_composition_accepts_no_caller_controlled_temporal_input() -> None:
    """Architect checkpoint, tenth review, item 1: compose_strategy_
    knowledge must not accept an ``effective_time`` (or any other
    caller-supplied temporal value) it could use instead of the sealed
    snapshot's own ``as_of`` -- a future production caller passing
    wall-clock time could otherwise recreate the same-snapshot/different-
    identity defect this closed. Checked directly against the function's
    own signature, not by convention.
    """
    import inspect

    from strategy_runtime.knowledge_composition import compose_strategy_knowledge

    signature = inspect.signature(compose_strategy_knowledge)
    assert "effective_time" not in signature.parameters
    for name, parameter in signature.parameters.items():
        annotation = str(parameter.annotation)
        assert "datetime" not in annotation, (
            f"compose_strategy_knowledge's parameter {name!r} carries a datetime-typed "
            "annotation -- every fact's own effective_time must come from the sealed "
            "snapshot's own as_of, never a caller-supplied value"
        )


def test_orchestrator_never_compares_against_strategy_id() -> None:
    """compose_strategy_knowledge receives ``strategy_id`` as a parameter
    but must only ever use it as a registry lookup key (``mapping_for``) --
    never compared, branched on, or interpolated into a conditional. The
    module-wide string-literal-comparison sweep above already proves no
    comparison anywhere touches a string constant; this asserts the
    stronger, targeted fact that the ``strategy_id`` name itself never
    appears inside an ``ast.Compare`` node at all (covers comparisons
    against another variable, not just a literal).
    """
    module = _PACKAGE_ROOT / "knowledge_composition.py"
    tree = ast.parse(_source(module))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for operand in (node.left, *node.comparators):
            if isinstance(operand, ast.Name) and operand.id == "strategy_id":
                raise AssertionError(
                    f"{module.name} compares strategy_id at line {node.lineno} -- "
                    "the generic orchestrator must never branch on strategy identity"
                )
