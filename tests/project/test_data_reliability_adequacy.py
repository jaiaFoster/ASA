from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = REPO_ROOT / "project" / "research" / "DATA-RELIABILITY-001" / "data-adequacy-v1.json"


def test_data_adequacy_decision_is_self_identifying_and_records_current_proof() -> None:
    payload = json.loads(ARTIFACT.read_text())
    identity = payload.pop("artifact_identity")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    assert identity == "sha256:" + hashlib.sha256(canonical).hexdigest()
    assert payload["classification"] == "PAID_DATA_CAPABILITY_GAP_CONFIRMED"
    current = payload["current_production_remeasurement"]
    assert current["active_identities"] == 1509
    assert current["freshness_live"] == 1509
    assert current["asa_owned_missingness"] == 0
    assert current["provider_external_entitlement_or_coverage"] == 18
    assert payload["last_immutable_historical_census"]["warning"].startswith("Predates")
    assert {item["issue"] for item in payload["asa_owned_corrections"]} == {436, 437}
    assert len(payload["capability_gap_matrix"]) == 5
    assert "separate Founder procurement decision" in payload["decision_rule"]
