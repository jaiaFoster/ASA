import json
from dataclasses import replace

from fastapi.testclient import TestClient

from asa.api.screening_models import ExecutableStructureAssessmentResponse
from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from asa.contracts.portfolio_lifecycle import ExecutionReadinessArtifact
from strategy_runtime.executable_structures import serialize_execution_assessment
from tests.asa.fakes import InMemoryLatestResultRepository, InMemoryObservationRepository
from tests.asa.test_modeled_pnl import BACK, VALUATION, _assessment
from tests.asa.test_screening_routes import _record
from tests.strategy_runtime.test_option_payoff import _vertical


class ReadinessRepository:
    def __init__(self, artifact: ExecutionReadinessArtifact) -> None:
        self.artifact = artifact

    def execution_readiness(self, strategy_id, symbol):
        if (strategy_id, symbol) == (self.artifact.strategy_id, self.artifact.symbol):
            return self.artifact
        return None


def test_explicit_assumption_endpoint_models_pnl_without_acquisition() -> None:
    assessment = _assessment()
    projection = ExecutableStructureAssessmentResponse.from_assessment(assessment)
    artifact = ExecutionReadinessArtifact(
        "forward_factor-AAPL-obs",
        "forward_factor",
        "AAPL",
        assessment.identity,
        projection.model_dump_json(),
        serialize_execution_assessment(assessment),
        assessment.assessed_at,
    )
    results = InMemoryLatestResultRepository()
    results.upsert(_record("forward_factor", "AAPL"))
    app = build_application(
        Settings(agent_api_token="test-token", _env_file=None),
        DependencyOverrides(
            repository=InMemoryObservationRepository(),
            latest_result_repository=results,
            portfolio_lifecycle_repository=ReadinessRepository(artifact),  # type: ignore[arg-type]
        ),
    )
    back_identity = next(
        item.canonical_contract_identity
        for item in projection.exact_legs
        if item.expiration == BACK
    )

    response = TestClient(app).get(
        "/api/v1/screening/forward_factor/AAPL/execution-readiness/modeled-pnl",
        headers={"Authorization": "Bearer test-token"},
        params={
            "valuation_time": VALUATION.isoformat(),
            "spot_reference": "200",
            "underlying_price_grid": "180,200,220",
            "volatility_by_contract": json.dumps({back_identity: "0.30"}),
            "annual_risk_free_rate": "0.04",
            "annual_dividend_yield": "0.01",
            "contract_multiplier": "100",
        },
    )

    assert response.status_code == 200
    assert response.json()["semantics"] == "modeled_PnL_not_guaranteed_payoff"
    assert [item["modeled_pnl"] for item in response.json()["points"]] == [
        "-118.83",
        "484.73",
        "-52.90",
    ]


def test_terminal_payoff_endpoint_returns_exact_vertical_economics() -> None:
    assessment = _vertical()
    projection = ExecutableStructureAssessmentResponse.from_assessment(assessment)
    artifact = ExecutionReadinessArtifact(
        "forward_factor-AAPL-obs",
        "forward_factor",
        "AAPL",
        assessment.identity,
        projection.model_dump_json(),
        serialize_execution_assessment(assessment),
        assessment.assessed_at,
    )
    results = InMemoryLatestResultRepository()
    results.upsert(_record("forward_factor", "AAPL"))
    app = build_application(
        Settings(agent_api_token="test-token", _env_file=None),
        DependencyOverrides(
            repository=InMemoryObservationRepository(),
            latest_result_repository=results,
            portfolio_lifecycle_repository=ReadinessRepository(artifact),  # type: ignore[arg-type]
        ),
    )

    response = TestClient(app).get(
        "/api/v1/screening/forward_factor/AAPL/execution-readiness/terminal-payoff",
        headers={"Authorization": "Bearer test-token"},
        params={"underlying_price_grid": "90,104,120"},
    )

    assert response.status_code == 200
    assert response.json()["semantics"] == ("deterministic_terminal_payoff_from_modeled_entry")
    assert [item["payoff"] for item in response.json()["points"]] == [
        "-400.00",
        "0.00",
        "600.00",
    ]
    assert response.json()["maximum_loss"]["value"] == "400.00"

    default_grid = TestClient(app).get(
        "/api/v1/screening/forward_factor/AAPL/execution-readiness/terminal-payoff",
        headers={"Authorization": "Bearer test-token"},
    )
    assert default_grid.status_code == 200
    assert len(default_grid.json()["points"]) == 23
    assert default_grid.json()["points"][0]["underlying_price"] == "80.00"


def test_calendar_terminal_payoff_refuses_intrinsic_only_substitution() -> None:
    assessment = _assessment()
    projection = ExecutableStructureAssessmentResponse.from_assessment(assessment)
    artifact = ExecutionReadinessArtifact(
        "forward_factor-AAPL-obs",
        "forward_factor",
        "AAPL",
        assessment.identity,
        projection.model_dump_json(),
        serialize_execution_assessment(assessment),
        assessment.assessed_at,
    )
    results = InMemoryLatestResultRepository()
    results.upsert(_record("forward_factor", "AAPL"))
    app = build_application(
        Settings(agent_api_token="test-token", _env_file=None),
        DependencyOverrides(
            repository=InMemoryObservationRepository(),
            latest_result_repository=results,
            portfolio_lifecycle_repository=ReadinessRepository(artifact),  # type: ignore[arg-type]
        ),
    )

    response = TestClient(app).get(
        "/api/v1/screening/forward_factor/AAPL/execution-readiness/terminal-payoff",
        headers={"Authorization": "Bearer test-token"},
        params={"underlying_price_grid": "180,200,220"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == (
        "MULTIPLE_EXPIRATIONS_REQUIRE_MODEL_DEPENDENT_VALUE"
    )


def test_trade_proposal_endpoint_projects_exact_current_trade() -> None:
    assessment = replace(_assessment(), originating_result_identity="forward_factor-AAPL-obs")
    projection = ExecutableStructureAssessmentResponse.from_assessment(assessment)
    artifact = ExecutionReadinessArtifact(
        "forward_factor-AAPL-obs",
        "forward_factor",
        "AAPL",
        assessment.identity,
        projection.model_dump_json(),
        serialize_execution_assessment(assessment),
        assessment.assessed_at,
    )
    results = InMemoryLatestResultRepository()
    results.upsert(_record("forward_factor", "AAPL"))
    app = build_application(
        Settings(agent_api_token="test-token", _env_file=None),
        DependencyOverrides(
            repository=InMemoryObservationRepository(),
            latest_result_repository=results,
            portfolio_lifecycle_repository=ReadinessRepository(artifact),  # type: ignore[arg-type]
        ),
    )

    response = TestClient(app).get(
        "/api/v1/screening/forward_factor/AAPL/trade-proposal",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "available"
    assert response.json()["originating_result_identity"] == "forward_factor-AAPL-obs"
    assert len(response.json()["legs"]) == 2
    assert response.json()["modeled_net_debit_or_credit"] == "2.00"
    assert response.json()["maximum_loss"] == {
        "state": "supported",
        "value": "200.00",
        "reason": None,
    }
    assert response.json()["maximum_profit"]["state"] == "unknown"
