"""SPRINT-009R/EPIC-R2: PostgresLatestResultRepository's own JSON encoding
of TypedValue metrics/economics -- exercised as pure functions, without a
real database (see test_universal_screening_service_postgres_integration.py
for the real-Postgres round trip, gated behind the ``postgres`` marker).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from asa.integrations.universal_screening_postgres import _to_params, _to_row
from strategy_runtime.persistence import UniversalSignalRow
from strategy_runtime.values import TypedValue


def _row(**overrides: object) -> UniversalSignalRow:
    defaults: dict[str, object] = {
        "signal_id": "alpha",
        "signal_version": "1.0.0",
        "symbol": "AAPL",
        "observation_id": "obs-1",
        "opportunity_id": None,
        "row_type": "result",
        "verdict": "pass",
        "evaluation_state": "pass",
        "lifecycle_stage": None,
        "recommendation_state": None,
        "data_quality": None,
        "metrics": {"strategy_native_score": TypedValue.of_decimal(Decimal("0.5"))},
        "economics": {"debit": TypedValue.of_decimal(Decimal("125.50"))},
        "blockers": (),
        "warnings": (),
        "provenance": (),
        "observed_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return UniversalSignalRow(**defaults)  # type: ignore[arg-type]


def test_to_params_json_encodes_typed_values() -> None:
    params = _to_params(_row())

    decoded_metrics = json.loads(params["metrics"])
    assert decoded_metrics == {"strategy_native_score": {"type": "decimal", "value": "0.5"}}
    decoded_economics = json.loads(params["economics"])
    assert decoded_economics == {"debit": {"type": "decimal", "value": "125.50"}}


def test_to_row_reconstructs_typed_values_from_a_json_shaped_mapping() -> None:
    mapping = {
        "signal_id": "alpha",
        "signal_version": "1.0.0",
        "symbol": "AAPL",
        "observation_id": "obs-1",
        "opportunity_id": None,
        "row_type": "result",
        "verdict": "pass",
        "evaluation_state": "pass",
        "lifecycle_stage": None,
        "recommendation_state": None,
        "data_quality": None,
        "metrics": {"strategy_native_score": {"type": "decimal", "value": "0.5"}},
        "economics": {"debit": {"type": "decimal", "value": "125.50"}},
        "blockers": [],
        "warnings": [],
        "provenance": [],
        "observed_at": datetime(2026, 1, 1, tzinfo=UTC),
    }

    row = _to_row(mapping)  # type: ignore[arg-type]

    assert row.metrics["strategy_native_score"] == TypedValue.of_decimal(Decimal("0.5"))
    assert row.economics["debit"].native() == Decimal("125.50")


def test_round_trip_through_params_and_row_preserves_typed_values() -> None:
    original = _row()

    params = _to_params(original)
    mapping = dict(params)
    mapping["metrics"] = json.loads(params["metrics"])
    mapping["economics"] = json.loads(params["economics"])
    mapping["blockers"] = []
    mapping["warnings"] = []
    mapping["provenance"] = []

    restored = _to_row(mapping)  # type: ignore[arg-type]

    assert restored.metrics == original.metrics
    assert restored.economics == original.economics
