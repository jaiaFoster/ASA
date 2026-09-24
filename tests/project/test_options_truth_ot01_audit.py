from __future__ import annotations

import json
from pathlib import Path

AUDIT_PATH = (
    Path(__file__).resolve().parents[2] / "project" / "reports" / "OPTIONS-TRUTH-001-OT-01.json"
)


def test_ot01_audit_is_complete_and_pins_accepted_versions() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))

    assert audit["sprint"] == "OPTIONS-TRUTH-001"
    assert audit["ticket"] == "OT-01"
    assert len(audit["source_repository"]["revision"]) == 40
    assert audit["runtime_changes_required"] is False
    assert audit["clear_errors_found"] == []
    assert audit["unresolved_product_semantics"] == []

    expected_versions = {
        "earnings_calendar": "1.2.0",
        "forward_factor": "1.3.0",
        "skew_momentum": "2.0.1-research",
    }
    strategies = {item["strategy_id"]: item for item in audit["strategies"]}
    assert {key: item["accepted_version"] for key, item in strategies.items()} == (
        expected_versions
    )

    required = set(audit["required_dimensions"])
    allowed = set(audit["classification_vocabulary"])
    for strategy in strategies.values():
        assert set(strategy["dimensions"]) == required
        assert strategy["source_evidence"]
        for dimension in strategy["dimensions"].values():
            assert dimension["classification"] in allowed
            assert dimension["action"] == "none"
            assert dimension["source_intent"]
            assert dimension["implementation"]
