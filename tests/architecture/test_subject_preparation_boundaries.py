"""SPRINT-014 S14-PR-05A, Architect checkpoint: twelfth review, item 5 --
"generic orchestration may expose sealed provider-neutral evidence and
invoke registered strategy bindings; it must not contain
if strategy_id == 'earnings_calendar' or own Earnings DTE/ATM/analytics
policy". These tests enforce that directly against
strategy_runtime/subject_preparation.py's own source, mirroring
tests/architecture/test_knowledge_composition_boundaries.py's substring-
sweep pattern.
"""

from __future__ import annotations

import ast
from pathlib import Path

_MODULE = Path(__file__).resolve().parents[2] / "strategy_runtime" / "subject_preparation.py"

# Strategy-specific names that would signal the generic preparation seam
# has stopped being generic -- Earnings Calendar's own payload, binding,
# fact_types, or structural selection must never appear here, textually or
# as an import. Also covers Forward Factor/Skew Momentum, so the check
# stays meaningful even after they eventually gain their own bindings.
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


def _source() -> str:
    return _MODULE.read_text()


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
        "collections",
        "dataclasses",
        "datetime",
        "domain",
        "market_data",
        "screening",
        "strategy_runtime",
        "typing",
    }
    imported = _imported_roots(ast.parse(_source()))
    assert imported <= permitted, f"imports outside {permitted}: {imported - permitted}"


def test_never_imports_strategy_specific_packages() -> None:
    forbidden = {"strategies", "asa"}
    imported = _imported_roots(ast.parse(_source()))
    assert not (imported & forbidden), f"imports: {imported & forbidden}"


def test_source_never_names_a_strategy_payload_binding_or_fact() -> None:
    source = _source()
    found = [needle for needle in _PROHIBITED_SOURCE_SUBSTRINGS if needle in source]
    assert not found, f"names strategy-specific identifiers: {found}"


def test_no_conditional_branches_on_a_string_literal_at_all() -> None:
    """The strongest available proxy for "never branches on a strategy
    identity": no comparison anywhere in this module compares anything
    against a string constant. strategy_id is only ever used as a
    registry-lookup key -- looked up, stored, returned -- never compared.
    """
    tree = ast.parse(_source())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        operands = (node.left, *node.comparators)
        for operand in operands:
            if isinstance(operand, ast.Constant) and isinstance(operand.value, str):
                raise AssertionError(
                    f"compares against a string literal {operand.value!r} at line "
                    f"{node.lineno} -- the generic preparation seam must never branch "
                    "on strategy identity"
                )


def test_orchestrator_never_compares_against_strategy_id() -> None:
    """Scoped to ``prepare_strategy_knowledge`` itself, not the whole
    module: unlike knowledge_composition.py's own boundary test (a
    dedicated module with no registry class in it), this module also
    defines SubjectPreparationRegistry.is_registered/binding_for, whose
    own ``strategy_id in self._entries`` membership check is a legitimate
    dict lookup -- the same pattern KnowledgeCompositionRegistry.
    is_registered already uses -- never a branch on strategy identity.
    The orchestrator function itself, which actually drives evaluation,
    is what must never compare against strategy_id.
    """
    tree = ast.parse(_source())
    orchestrator = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "prepare_strategy_knowledge"
    )
    for node in ast.walk(orchestrator):
        if not isinstance(node, ast.Compare):
            continue
        for operand in (node.left, *node.comparators):
            if isinstance(operand, ast.Name) and operand.id == "strategy_id":
                raise AssertionError(
                    f"compares strategy_id at line {node.lineno} -- the generic "
                    "orchestrator must never branch on strategy identity"
                )


def test_prepare_strategy_knowledge_accepts_no_caller_controlled_temporal_override() -> None:
    """Mirrors test_knowledge_composition_boundaries.py's own check on
    compose_strategy_knowledge: the only datetime this module's own
    orchestrator accepts is ``now`` (bootstrap-demand construction time),
    never a second, competing temporal value it could use for fact
    identity instead of the sealed snapshot's own as_of.
    """
    import inspect

    from strategy_runtime.subject_preparation import prepare_strategy_knowledge

    signature = inspect.signature(prepare_strategy_knowledge)
    datetime_params = [
        name
        for name, parameter in signature.parameters.items()
        if "datetime" in str(parameter.annotation)
    ]
    assert datetime_params == ["now"]
