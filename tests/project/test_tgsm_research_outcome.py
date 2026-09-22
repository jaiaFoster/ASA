from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = REPO_ROOT / "project" / "research" / "TGSM-RESEARCH-001" / "research-outcome-v1.json"


def test_data_limited_outcome_is_self_identifying_and_never_fabricates_results() -> None:
    payload = json.loads(ARTIFACT.read_text())
    identity = payload.pop("artifact_identity")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    assert identity == "sha256:" + hashlib.sha256(canonical).hexdigest()
    assert payload["evidence_classification"] == "DATA_LIMITED"
    assert payload["result_bearing_experiments_executed"] is False
    assert set(payload["baseline_and_ablation_status"]) == {
        "B0",
        "B1",
        "B2",
        "B3",
        "B4",
        "S1",
    }
    assert set(payload["baseline_and_ablation_status"].values()) == {"NOT_RUN_DATA_LIMITED"}
    assert set(payload["hypothesis_assessments"].values()) == {"INCONCLUSIVE"}
    assert all("No " in claim for claim in payload["prohibited_claims"])
