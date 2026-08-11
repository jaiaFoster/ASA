"""SPRINT-014 S14-PR-05A, Architect checkpoint: fifteenth review, deferred
test hardening -- "add the deferred AST architecture guard for
strategy_runtime/orchestration.py proving no strategy-specific imports or
string-identity branching." Mirrors tests/architecture/
test_subject_preparation_boundaries.py's own substring/AST-sweep pattern.
"""

from __future__ import annotations

import ast
from pathlib import Path

_MODULE = Path(__file__).resolve().parents[2] / "strategy_runtime" / "orchestration.py"

# Strategy-specific names that would signal the shared orchestration seam
# has stopped being generic -- any migrated strategy's own payload,
# binding, fact_types, or structural selection must never appear here,
# textually or as an import.
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
        "hashlib",
        "json",
        "market_data",
        "screening",
        "strategy_runtime",
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


def test_never_compares_against_strategy_id_or_subject() -> None:
    """strategy_id and symbol/subject are only ever used as registry-
    lookup keys (shadow_registry.is_registered/binding_for,
    legacy_registry.contract_for), dict keys, or forwarded verbatim into
    a ShadowParityDiagnostic/RuntimeContext -- never compared against
    another value to decide behavior.

    Deliberately scoped to these two names rather than a blanket
    "no comparison against any string literal" sweep (unlike
    test_subject_preparation_boundaries.py's own version of this check):
    this module's own ShadowParityDiagnostic.is_match property legitimately
    compares ``self.status`` against the literal ``"match"`` -- a generic
    diagnostic-state check, not a strategy- or subject-identity branch --
    and a blanket sweep would flag that as a false positive.
    """
    tree = ast.parse(_source())
    guarded_names = {"strategy_id", "subject", "symbol"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for operand in (node.left, *node.comparators):
            if isinstance(operand, ast.Name) and operand.id in guarded_names:
                raise AssertionError(
                    f"compares {operand.id!r} at line {node.lineno} -- the shared "
                    "orchestration seam must never branch on strategy or subject identity"
                )
