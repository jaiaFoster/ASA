from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from tests.asa.fakes import InMemoryLatestResultRepository, InMemoryObservationRepository
from tests.asa.test_screening_routes import _record
from tools.stock_product.stock_observation import capture_stock_observation, proposal_gaps

SHA = "d" * 40
NOW = datetime(2026, 9, 24, 17, tzinfo=UTC)


def _fetch():  # type: ignore[no-untyped-def]
    results = InMemoryLatestResultRepository()
    for row in (
        _record("B001", "SPY", blockers=()),
        _record("B002", "SPY", "missing_data", verdict=None),
        _record("forward_factor", "AAPL"),
    ):
        results.upsert(row)
    client = TestClient(
        build_application(
            Settings(agent_api_token="t", release_sha=SHA, _env_file=None),
            DependencyOverrides(
                repository=InMemoryObservationRepository(), latest_result_repository=results
            ),
        )
    )
    paths: list[str] = []

    def fetch(path: str):  # type: ignore[no-untyped-def]
        paths.append(path)
        response = client.get(path, headers={"Authorization": "Bearer t"})
        return response.status_code, response.json()

    return fetch, paths


def test_replay_observes_every_declared_stock_strategy_read_only() -> None:
    fetch, paths = _fetch()

    artifact = capture_stock_observation(fetch, production_sha=SHA, captured_at=NOW)

    assert artifact["stock_signals"] == ["B001", "B002"]
    assert artifact["defect_count"] == 0
    assert artifact["status_counts"] == {"unknown": 1, "no_action": 1}
    assert artifact["verdict"] == "typed_path_only_awaiting_actionable"
    assert not any("forward_factor" in path for path in paths)
    assert not any("refresh" in path for path in paths)


def test_proposal_gaps_flag_untyped_absence() -> None:
    assert proposal_gaps({"status": "actionable", "action": None, "action_reason": None}) == [
        "missing:instrument",
        "missing:strategy_id",
        "missing:strategy_version",
        "missing:evidence_observed_at",
        "missing:freshness",
        "missing:evaluation_state",
        "empty:rationale",
        "empty:invalidation_notes",
        "untyped:action",
        "untyped:allocation",
        "invalid:actionable_without_action",
    ]
