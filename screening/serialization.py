"""Canonical, secret-free JSON serialization for ScreeningResult (SCREEN-005)."""

from __future__ import annotations

from typing import Any

from domain import EvidenceReference
from domain.market_data import CompletenessMetadata
from screening.results import ScreeningResult


def _evidence_to_dict(reference: EvidenceReference) -> dict[str, Any]:
    return {"kind": reference.kind.value, "referenced_id": reference.referenced_id}


def _completeness_to_dict(completeness: CompletenessMetadata | None) -> dict[str, Any] | None:
    if completeness is None:
        return None
    return {
        "required_fields": list(completeness.required_fields),
        "present_fields": list(completeness.present_fields),
        "missing_fields": list(completeness.missing_fields),
    }


def result_to_dict(result: ScreeningResult) -> dict[str, Any]:
    """Convert one ScreeningResult into a canonical, JSON-safe mapping.

    Never includes a raw provider payload or secret -- every field here is
    already one of ScreeningResult's own bounded, redacted, canonical
    fields.
    """
    return {
        "run_id": result.run_id,
        "strategy_id": result.strategy_id,
        "strategy_version": result.strategy_version,
        "subject_identity": result.subject_identity,
        "as_of": result.as_of.isoformat(),
        "outcome_status": result.outcome_status.value,
        "signal_classification": result.signal_classification,
        "strategy_native_score": (
            str(result.strategy_native_score) if result.strategy_native_score is not None else None
        ),
        "evidence": [_evidence_to_dict(item) for item in result.evidence],
        "input_provenance": [_evidence_to_dict(item) for item in result.input_provenance],
        "completeness": _completeness_to_dict(result.completeness),
        "failure_detail": result.failure_detail,
    }


def results_to_json_payload(
    results: tuple[ScreeningResult, ...], *, dry_run: bool
) -> dict[str, Any]:
    return {"dry_run": dry_run, "results": [result_to_dict(result) for result in results]}
