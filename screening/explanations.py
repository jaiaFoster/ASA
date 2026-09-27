"""Generic graph-output to screening explanation projection (SPRINT-012 WS6)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from analytics.derived_facts import DERIVED_FACT_REGISTRY
from analytics.formulas import OPTION_STRATEGY_FORMULAS
from screening.results import ExplanationScalar, ScreeningExplanation
from strategies.manifest import StrategyManifest
from strategies.type_system import ComponentValues

# Three-state gate values (SP-01E). UNKNOWN projects to None, never False.
_GATE_STATES: dict[object, bool | None] = {"PASS": True, "FAIL": False, "UNKNOWN": None}


def _gate_value(value: object) -> bool | None:
    if isinstance(value, bool) or value is None:
        return value
    if value not in _GATE_STATES:
        raise ValueError(f"gate value must be Boolean or PASS/FAIL/UNKNOWN: {value!r}")
    return _GATE_STATES[value]


def _formula_version(formula_id: str) -> str:
    if DERIVED_FACT_REGISTRY.is_registered(formula_id):
        return DERIVED_FACT_REGISTRY.get(formula_id).feature_version
    return OPTION_STRATEGY_FORMULAS.get(formula_id).formula_version


def _scalar(value: object) -> ExplanationScalar:
    if value is None or isinstance(value, (bool, int, Decimal, str)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return str(value.value)
    identity = getattr(value, "identity", None)
    if isinstance(identity, str):
        return identity
    if isinstance(value, tuple):
        identities = tuple(getattr(item, "identity", str(item)) for item in value)
        return ",".join(str(item) for item in identities)
    return str(value)


def build_graph_explanation(
    manifest: StrategyManifest, outputs: ComponentValues
) -> ScreeningExplanation:
    """Project all manifest outputs without knowing a strategy identifier."""

    output_specs = {item.name: item for item in manifest.outputs}
    canonical_facts = tuple(
        sorted(
            (
                (name, _scalar(typed.value))
                for name, typed in outputs.entries
                if output_specs[name].explanation_role == "fact"
            ),
            key=lambda item: item[0],
        )
    )
    derived_facts = tuple(
        sorted(
            (
                (name, _scalar(typed.value))
                for name, typed in outputs.entries
                if output_specs[name].explanation_role == "derived_fact"
            ),
            key=lambda item: item[0],
        )
    )
    gates = tuple(
        (name, _gate_value(typed.value))
        for name, typed in outputs.entries
        if output_specs[name].explanation_role == "gate"
    )
    formula_versions = []
    for spec in manifest.outputs:
        if spec.formula_id is not None:
            formula_versions.append((spec.name, _formula_version(spec.formula_id)))

    direction_value = next(
        (
            outputs.get(spec.name).value
            for spec in manifest.outputs
            if spec.explanation_role == "direction"
        ),
        None,
    )
    structure_value = next(
        (
            outputs.get(spec.name).value
            for spec in manifest.outputs
            if spec.explanation_role == "structure"
        ),
        None,
    )
    verdict = str(
        next(
            outputs.get(spec.name).value
            for spec in manifest.outputs
            if spec.explanation_role == "verdict"
        )
    )
    reason_codes = [f"verdict:{verdict.lower()}"]
    reason_codes.extend(
        f"gate:{name}:{'unknown' if value is None else str(value).lower()}"
        for name, value in gates
        if value is not True
    )
    assumptions = tuple(
        sorted(
            [
                f"{node.node_id}.{parameter.name}={parameter.value}"
                for node in manifest.nodes
                for parameter in node.parameters
            ]
            + [
                # Material research/implementation assumptions are disclosed by
                # id; they are never presented as source-authored rules.
                f"assumption:{item.assumption_id}:{item.kind}"
                + (f"[{','.join(item.parameter_names)}]" if item.parameter_names else "")
                for item in manifest.assumptions
            ]
        )
    )
    warnings = tuple(
        f"{name}:unknown"
        for name, value in (*canonical_facts, *derived_facts)
        if value is None
    )
    return ScreeningExplanation(
        canonical_facts=canonical_facts,
        named_derived_facts=derived_facts,
        formula_versions=tuple(sorted(formula_versions)),
        gate_results=tuple(sorted(gates)),
        direction=None if direction_value is None else str(direction_value),
        structure=(
            None if structure_value is None else str(_scalar(structure_value))
        ),
        reason_codes=tuple(reason_codes),
        assumptions=assumptions,
        warnings=warnings,
    )
