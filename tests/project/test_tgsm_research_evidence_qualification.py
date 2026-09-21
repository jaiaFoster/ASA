from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = (
    REPO_ROOT
    / "project"
    / "research"
    / "TGSM-RESEARCH-001"
    / "evidence-qualification-v1.json"
)


def test_tgsm_evidence_qualification_is_fail_closed_and_self_identifying() -> None:
    payload = json.loads(ARTIFACT.read_text())
    identity = payload.pop("artifact_identity")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    assert identity == "sha256:" + hashlib.sha256(canonical).hexdigest()
    assert payload["classification"] == "DATA_LIMITED"
    assert payload["qualified_test_period"] is None
    assert payload["result_bearing_experiments_authorized"] is False
    assert {item["id"] for item in payload["requirements"]} == {
        "point_in_time_sector_eligibility",
        "sector_and_spy_total_return_history",
        "completed_month_observations_and_12m_momentum",
        "completed_month_10m_trend",
        "three_month_treasury_total_return",
        "historical_trading_calendar_and_next_session",
        "required_benchmarks",
    }
    assert all(item["status"] != "qualified" for item in payload["requirements"])
