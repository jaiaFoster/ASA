import json

from fastapi.testclient import TestClient

from asa.api.screening_models import ExecutableStructureAssessmentResponse
from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from asa.contracts.portfolio_lifecycle import ExecutionReadinessArtifact
from strategy_runtime.executable_structures import serialize_execution_assessment
from tests.asa.fakes import InMemoryLatestResultRepository, InMemoryObservationRepository
from tests.asa.test_modeled_pnl import BACK, VALUATION, _assessment
from tests.asa.test_screening_routes import _record


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
