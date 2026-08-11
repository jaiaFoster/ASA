from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from market_data import load_market_data_config
from strategy_runtime.lifecycle import OpportunityObservation, RecommendedAction
from strategy_runtime.persistence import UniversalSignalRow
from strategy_runtime.result import EvaluationState, RowType, UniversalScreeningResult
from tests.asa.fakes import (
    InMemoryLatestResultRepository,
    InMemoryObservationHistoryRepository,
)
from tests.asa.market_data_ops.fakes import ScriptedTransport

NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
AUTH = {"Authorization": "Bearer correct-token"}


def _observation(offset: int, stage: str) -> OpportunityObservation:
    return OpportunityObservation(
        "opportunity-1",
        "earnings_calendar",
        "AAPL",
        stage,
        "PASS",
        RecommendedAction.NO_ACTION,
        NOW + timedelta(minutes=offset),
    )


def _client(history_repository) -> TestClient:  # noqa: ANN001
    return TestClient(
        build_application(
            Settings(agent_api_token=SecretStr("correct-token"), _env_file=None),
            DependencyOverrides(
                latest_result_repository=InMemoryLatestResultRepository(),
                observation_history_repository=history_repository,
            ),
        )
    )


def test_history_is_oldest_first_bounded_and_opportunity_scoped() -> None:
    history = InMemoryObservationHistoryRepository()
    history.append(_observation(2, "confirmed"))
    history.append(_observation(1, "watching"))
    response = _client(history).get(
        "/api/v1/screening/opportunities/opportunity-1/history",
        headers=AUTH,
        params={"limit": 1, "offset": 1},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["lifecycle_stage"] for item in body["observations"]] == ["confirmed"]
    assert body["opportunity_id"] == "opportunity-1"


def test_identical_observation_append_is_idempotent() -> None:
    history = InMemoryObservationHistoryRepository()
    observation = _observation(1, "watching")
    history.append(observation)
    history.append(observation)
    response = _client(history).get(
        "/api/v1/screening/opportunities/opportunity-1/history", headers=AUTH
    )
    assert response.json()["total"] == 1


def test_missing_history_and_missing_auth_fail_closed() -> None:
    client = _client(InMemoryObservationHistoryRepository())
    path = "/api/v1/screening/opportunities/missing/history"
    assert client.get(path).status_code == 404
    response = client.get(path, headers=AUTH)
    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "NO_OPPORTUNITY_HISTORY"


def test_history_append_failure_does_not_rollback_latest_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    latest = InMemoryLatestResultRepository()

    class FailingHistory:
        def append(self, observation):  # noqa: ANN001, ARG002
            raise RuntimeError("history unavailable")

        def history_for(self, opportunity_id):  # noqa: ANN001, ARG002
            return None

    result = UniversalScreeningResult(
        strategy_id="earnings_calendar",
        strategy_version="1.0.0",
        symbol="AAPL",
        observation_id="observation-1",
        opportunity_id="opportunity-1",
        row_type=RowType.RESULT,
        verdict="PASS",
        evaluation_state=EvaluationState.PASS,
        lifecycle_stage="confirmed",
        recommendation_state=None,
        data_quality=None,
        metrics={},
        economics={},
        blockers=(),
        warnings=(),
        provenance=(),
        observed_at=NOW,
    )

    def successful_refresh(registry, repository, clock, **kwargs):  # noqa: ANN001, ARG001
        repository.upsert(UniversalSignalRow.from_result(result))
        return result, None

    monkeypatch.setattr("asa.api.screening_routes.refresh_with_shadow", successful_refresh)
    monkeypatch.setattr(
        "asa.api.screening_routes.load_market_data_config_from_environment",
        lambda: load_market_data_config(
            {"ASA_TRADIER_ENABLED": "true", "ASA_TRADIER_ACCESS_TOKEN": "test-token"}
        ),
    )
    app = build_application(
        Settings(agent_api_token=SecretStr("correct-token"), _env_file=None),
        DependencyOverrides(
            latest_result_repository=latest,
            observation_history_repository=FailingHistory(),
            market_data_transport_factory=lambda provider_id: ScriptedTransport([]),  # noqa: ARG005
        ),
    )
    response = TestClient(app).post(
        "/api/v1/screening/earnings_calendar/AAPL/refresh", headers=AUTH
    )
    assert response.status_code == 200
    assert latest.get_one("earnings_calendar", "AAPL") is not None
