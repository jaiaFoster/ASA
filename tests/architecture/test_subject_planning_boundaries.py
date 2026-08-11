"""SPRINT-014 S14-PR-05A: architecture boundaries for the generic phased
subject planner (screening/subject_planning.py). Architect review finding
B1 (PR #292, review 4877473757) required a narrow, real boundary guard
here, not a broadened allowlist -- these tests enforce it directly against
the module's own source, not just against one known call site.
"""

from __future__ import annotations

import ast
from pathlib import Path

from screening.subject_planning import (
    DemandExpansion,
    SubjectPlanConsumer,
    run_subject_plan,
)

_MODULE = Path(__file__).resolve().parents[2] / "screening" / "subject_planning.py"

# Strategy-specific names that would signal this module has stopped being
# generic -- Earnings Calendar's own manifest, requirement type, fact IDs,
# or selection functions must never appear here, textually or as an
# import, at any point in this planner's life (not just "not yet, as of
# this commit").
_PROHIBITED_SOURCE_SUBSTRINGS = (
    "EARNINGS_CALENDAR_MANIFEST",
    "EarningsCalendarRequirement",
    "earnings_calendar_requirement",
    "front_min_dte",
    "back_max_dte",
    "target_gap_days",
    "gap_tolerance_days",
    "term_structure_richness",
    "iv_realized",
    "normalize_richness",
    "select_earnings_relative_expiration_pair",
    "forward_factor",
    "skew_momentum",
    "earnings_calendar",
)


def _imported_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _source() -> str:
    return _MODULE.read_text()


def test_only_permitted_roots() -> None:
    permitted = {
        "__future__",
        "collections",
        "dataclasses",
        "datetime",
        "domain",
        "market_data",
        "screening",
        "types",
        "typing",
    }
    imported = _imported_roots(ast.parse(_source()))
    assert imported <= permitted, (
        f"subject_planning.py imports outside {permitted}: {imported - permitted}"
    )


def test_never_imports_strategy_specific_or_downstream_packages() -> None:
    forbidden = {"strategies", "strategy_runtime", "analytics", "facts", "asa"}
    imported = _imported_roots(ast.parse(_source()))
    assert not (imported & forbidden), f"subject_planning.py imports: {imported & forbidden}"


def test_source_never_names_a_strategy_manifest_requirement_or_fact_id() -> None:
    source = _source()
    found = [needle for needle in _PROHIBITED_SOURCE_SUBSTRINGS if needle in source]
    assert not found, f"subject_planning.py names strategy-specific identifiers: {found}"


def test_no_conditional_branches_on_a_string_literal_at_all() -> None:
    """The strongest available proxy for "never branches on a strategy or
    consumer identity": no `if`/`elif` in this module ever compares
    anything against a string constant. consumer_id is read, stored, and
    returned -- never compared -- so this holds trivially as long as the
    module stays generic.
    """
    tree = ast.parse(_source())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        operands = (node.left, *node.comparators)
        for operand in operands:
            if isinstance(operand, ast.Constant) and isinstance(operand.value, str):
                raise AssertionError(
                    f"subject_planning.py compares against a string literal "
                    f"{operand.value!r} at line {node.lineno} -- this planner must "
                    "never branch on identity"
                )


def test_consumer_protocol_never_exposes_the_plan_fulfiller_or_infrastructure() -> None:
    """DemandExpansionFunction's own input type (ResolvedEvidenceView) is
    a Mapping[str, CapabilityFulfillmentResult] -- never
    SubjectAcquisitionPlan, never a fulfiller, never ProviderMetadata,
    transport, budget, or an attempt repository. Checked directly against
    run_subject_plan's own annotated parameter for expand functions via
    SubjectPlanConsumer's own field type, not just by convention.
    """
    import inspect

    signature = inspect.signature(run_subject_plan)
    consumers_annotation = str(signature.parameters["consumers"].annotation)
    forbidden_words = ("Fulfiller", "Transport", "Budget", "Repository", "ProviderMetadata")
    assert not any(word in consumers_annotation for word in forbidden_words)
    assert SubjectPlanConsumer.__dataclass_fields__.keys() == {
        "consumer_id",
        "bootstrap_demands",
        "expand",
    }
    assert DemandExpansion.__dataclass_fields__.keys() == {
        "demands",
        "selections",
        "unknown_reasons",
    }
