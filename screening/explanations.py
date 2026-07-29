"""Generic graph-output to screening explanation projection (SPRINT-012 WS6)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from analytics.derived_facts import DERIVED_FACT_REGISTRY
from screening.results import ExplanationScalar, ScreeningExplanation
from strategies.manifest import StrategyManifest
from strategies.type_system import ComponentValues

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
        (
            name,
            typed.value
            if isinstance(typed.value, bool) or typed.value is None
            else None,
        )
        for name, typed in outputs.entries
        if output_specs[name].explanation_role == "gate"
    )
    formula_versions = []
    for spec in manifest.outputs:
        if spec.formula_id is not None:
            definition = DERIVED_FACT_REGISTRY.get(spec.formula_id)
            formula_versions.append((spec.name, definition.feature_version))

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
            f"{node.node_id}.{parameter.name}={parameter.value}"
            for node in manifest.nodes
            for parameter in node.parameters
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
