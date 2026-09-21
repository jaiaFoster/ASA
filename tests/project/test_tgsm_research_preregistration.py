from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = REPO_ROOT / "project" / "research" / "TGSM-RESEARCH-001" / "preregistration-v1.json"


def test_tgsm_preregistration_is_complete_self_identifying_and_fail_closed() -> None:
    payload = json.loads(ARTIFACT.read_text())
    identity = payload.pop("artifact_identity")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    assert identity == "sha256:" + hashlib.sha256(canonical).hexdigest()
    assert payload["evidence_status"] == "DATA_LIMITED"
    assert payload["result_bearing_execution_authorized"] is False
    assert payload["strategy"] == {
        "id": "S001",
        "version": "1.0.0",
        "implementation_manifest_sha256": (
            "260e4e046cabe96a50a15a690f316eb3ee133351c8fbd71f0b491eed5ef38573"
        ),
    }
    assert set(payload["benchmarks"]) == {"B0", "B1", "B2", "B3", "B4", "S1"}
    assert set(payload["hypotheses"]) == {"H1", "H2", "H3", "H4", "H5"}
    assert payload["robustness_grid"] == {
        "momentum_months": [9, 12, 15],
        "trend_sma_months": [8, 10, 12],
        "top_n": [2, 3, 4],
        "rule": (
            "One-factor-at-a-time variations around S1 only; S1 remains 12/10/3 and is "
            "never replaced or re-tuned from results."
        ),
    }
    assert payload["walk_forward"]["parameter_selection"] == "none"


def test_tgsm_preregistration_preserves_prohibited_substitutions() -> None:
    payload = json.loads(ARTIFACT.read_text())
    evidence = payload["evidence_contract"]

    assert "raw and split-only closes prohibited" in evidence["risky_and_spy_returns"]
    assert "ETF, cash, and raw-yield proxies prohibited" in evidence["defensive_return"]
    assert "no imputation" in evidence["missing_policy"]
