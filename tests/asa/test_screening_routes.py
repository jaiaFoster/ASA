"""API-003: GET /api/v1/capabilities, GET /api/v1/screening[/{signal}[/{symbol}]]
(SPRINT-009R/EPIC-R5: exercised through the strategy_runtime-backed
LatestResultRepository, proving the public response shape is unchanged)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from pydantic import SecretStr

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from strategy_runtime.persistence import UniversalSignalRow
from strategy_runtime.result import EvaluationState, RowType
from strategy_runtime.values import TypedValue
from tests.asa.fakes import InMemoryLatestResultRepository

NOW = datetime(2026, 7, 23, 16, 0, tzinfo=UTC)


def _record(
    signal_id: str,
    symbol: str,
    outcome: str = "pass",
    *,
    observed_at: datetime = NOW,
    opportunity_id: str | None = None,
    lifecycle_stage: str | None = None,
    recommendation_state: str | None = None,
    score: Decimal = Decimal("75"),
    verdict: str | None = "PASS",
) -> UniversalSignalRow:
    return UniversalSignalRow(
        signal_id=signal_id,
        signal_version="1.0.0",
        symbol=symbol,
        observation_id=f"{signal_id}-{symbol}-obs",
        opportunity_id=opportunity_id,
        row_type=RowType.RESULT.value,
        verdict=verdict,
        evaluation_state=EvaluationState(outcome).value,
        lifecycle_stage=lifecycle_stage,
        recommendation_state=recommendation_state,
        data_quality="complete",
        metrics={"strategy_native_score": TypedValue.of_decimal(score)},
        economics={"estimated_return": TypedValue.of_decimal(Decimal("0.12"))},
        blockers=("capital unavailable",),
        warnings=("monitor liquidity",),
        provenance=("fixture:screening",),
        observed_at=observed_at,
    )


def _client(
    repository: InMemoryLatestResultRepository | None = None,
    token: str | None = "correct-token",
) -> TestClient:
    return TestClient(
        build_application(
            Settings(agent_api_token=SecretStr(token) if token else None, _env_file=None),
            DependencyOverrides(
                latest_result_repository=repository or InMemoryLatestResultRepository(),
                screening_operational_health=lambda: {
                    "last_attempted_batch_at": NOW,
                    "last_successful_batch_at": NOW,
                    "oldest_subject_age": 600,
                    "overdue_subject_count": 473,
                    "last_batch_subject_count": 30,
                    "last_batch_pair_count": 90,
                    "last_batch_failure_count": 0,
                    "last_batch_incomplete_diagnostic_count": 0,
                },
            ),
        )
    )


def _auth(token: str = "correct-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_strategy_health_exposes_all_registered_production_funnels() -> None:
    repository = InMemoryLatestResultRepository()
    for signal in ("forward_factor", "earnings_calendar", "skew_momentum"):
        repository.upsert(_record(signal, "AAPL"))

    response = _client(repository).get("/api/v1/screening-health", headers=_auth())

    assert response.status_code == 200
    funnels = {item["strategy_id"]: item for item in response.json()["strategies"]}
    assert set(funnels) == {"forward_factor", "earnings_calendar", "skew_momentum"}
    assert all(item["active_subjects"] == 1 for item in funnels.values())
    assert all(item["evaluated"] == 1 for item in funnels.values())
    assert all(item["missing_data"] == 0 for item in funnels.values())
    assert all(item["no_signal"] == 0 for item in funnels.values())
    assert all(item["typed_rejection_counts"] for item in funnels.values())


def test_strategy_health_distinguishes_missing_data_from_no_signal() -> None:
    repository = InMemoryLatestResultRepository()
    repository.upsert(
        _record("forward_factor", "AAPL", outcome="missing_data", verdict=None)
    )
    repository.upsert(_record("forward_factor", "MSFT", outcome="no_signal"))

    response = _client(repository).get("/api/v1/screening-health", headers=_auth())

    funnel = next(
        item
        for item in response.json()["strategies"]
        if item["strategy_id"] == "forward_factor"
    )
    assert funnel["active_subjects"] == 2
    assert funnel["evaluated"] == 1
    assert funnel["missing_data"] == 1
    assert funnel["no_signal"] == 1


class TestAuthentication:
    def test_capabilities_without_authorization_header_is_404(self) -> None:
        response = _client().get("/api/v1/capabilities")
        assert response.status_code == 404

    def test_screening_list_without_authorization_header_is_404(self) -> None:
        response = _client().get("/api/v1/screening")
        assert response.status_code == 404

    def test_screening_by_signal_without_authorization_header_is_404(self) -> None:
        response = _client().get("/api/v1/screening/forward_factor")
        assert response.status_code == 404

    def test_screening_result_without_authorization_header_is_404(self) -> None:
        response = _client().get("/api/v1/screening/forward_factor/AAPL")
        assert response.status_code == 404

    def test_wrong_token_is_404_not_401(self) -> None:
        response = _client().get("/api/v1/capabilities", headers=_auth("wrong-token"))
        assert response.status_code == 404

    def test_correct_token_is_accepted(self) -> None:
        response = _client().get("/api/v1/capabilities", headers=_auth())
        assert response.status_code == 200


class TestCapabilities:
    def test_lists_every_registered_signal(self) -> None:
        response = _client().get("/api/v1/capabilities", headers=_auth())
        assert response.status_code == 200
        signal_ids = {item["signal_id"] for item in response.json()["signals"]}
        assert signal_ids == {"earnings_calendar", "forward_factor", "skew_momentum"}

    def test_each_signal_declares_required_capabilities(self) -> None:
        response = _client().get("/api/v1/capabilities", headers=_auth())
        for item in response.json()["signals"]:
            assert item["required_capabilities"]


class TestScreeningOperations:
    def test_exposes_distinct_authenticated_screening_liveness(self) -> None:
        response = _client().get("/api/v1/screening/operations", headers=_auth())

        assert response.status_code == 200
        assert response.json() == {
            "last_attempted_batch_at": NOW.isoformat().replace("+00:00", "Z"),
            "last_successful_batch_at": NOW.isoformat().replace("+00:00", "Z"),
            "oldest_subject_age": 600,
            "overdue_subject_count": 473,
            "last_batch_subject_count": 30,
            "last_batch_pair_count": 90,
            "last_batch_failure_count": 0,
            "last_batch_incomplete_diagnostic_count": 0,
        }

    def test_screening_liveness_requires_authorization(self) -> None:
        assert _client().get("/api/v1/screening/operations").status_code == 404


class TestListScreening:
    def test_empty_repository_returns_empty_envelope(self) -> None:
        response = _client().get("/api/v1/screening", headers=_auth())
        assert response.status_code == 200
        body = response.json()
        assert body == {
            "results": [],
            "total": 0,
            "limit": 100,
            "offset": 0,
            "snapshot_identity": (
                "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
            ),
        }

    def test_returns_every_result_deterministically_ordered(self) -> None:
        repository = InMemoryLatestResultRepository()
        repository.upsert(_record("skew_momentum", "MSFT"))
        repository.upsert(_record("forward_factor", "AAPL"))
        response = _client(repository).get("/api/v1/screening", headers=_auth())
        body = response.json()
        assert [(item["signal_id"], item["symbol"]) for item in body["results"]] == [
            ("forward_factor", "AAPL"),
            ("skew_momentum", "MSFT"),
        ]
        assert body["total"] == 2

    def test_snapshot_identity_fences_multi_page_latest_state(self) -> None:
        repository = InMemoryLatestResultRepository()
        for index in range(501):
            repository.upsert(_record("earnings_calendar", f"E{index:04d}"))
        repository.upsert(_record("forward_factor", "F0000"))
        client = _client(repository)

        first = client.get("/api/v1/screening?limit=500&offset=0", headers=_auth()).json()
        second = client.get("/api/v1/screening?limit=500&offset=500", headers=_auth()).json()

        identities = {
            (item["signal_id"], item["symbol"])
            for item in first["results"] + second["results"]
        }
        assert first["total"] == second["total"] == 502
        assert first["snapshot_identity"] == second["snapshot_identity"]
        assert len(identities) == 502
        assert ("forward_factor", "F0000") in identities

        repository.upsert(_record("skew_momentum", "S0000"))
        changed = client.get(
            "/api/v1/screening?limit=500&offset=500", headers=_auth()
        ).json()
        assert changed["snapshot_identity"] != first["snapshot_identity"]

    def test_every_result_exposes_updated_at_and_age_seconds(self) -> None:
        repository = InMemoryLatestResultRepository()
        repository.upsert(_record("forward_factor", "AAPL"))
        response = _client(repository).get("/api/v1/screening", headers=_auth())
        (result,) = response.json()["results"]
        assert result["updated_at"] is not None
        assert result["age_seconds"] >= 0

    def test_watch_and_typed_explanation_survive_persistence_projection(self) -> None:
        repository = InMemoryLatestResultRepository()
        row = _record("forward_factor", "AAPL", verdict="WATCH")
        row.metrics.update(
            {
                "derived_fact.forward_factor": TypedValue.of_decimal(Decimal("0.19")),
                "formula_version.forward_factor": TypedValue.of_string("1.0.0"),
                "gate.eligible": TypedValue.of_boolean(True),
                "decision.direction": TypedValue.of_string("NEUTRAL"),
                "decision.structure": TypedValue.of_string("structure-1"),
                "decision.reason_codes": TypedValue.of_structured(["verdict:watch"]),
                "decision.assumptions": TypedValue.of_structured(["threshold=0.20"]),
            }
        )
        repository.upsert(row)

        response = _client(repository).get("/api/v1/screening", headers=_auth())
        (result,) = response.json()["results"]
        assert result["outcome"] == "watch"
        assert result["evaluation_state"] == "pass"
        assert result["verdict"] == "WATCH"
        assert result["canonical_facts"] == {}
        assert result["named_derived_facts"] == {"forward_factor": "0.19"}
        assert result["formula_versions"] == {"forward_factor": "1.0.0"}
        assert result["gate_results"] == {"eligible": "True"}
        assert result["direction"] == "NEUTRAL"
        assert result["structure"] == "structure-1"
        assert result["reason_codes"] == ["verdict:watch"]

    def test_pagination_limit_and_offset(self) -> None:
        repository = InMemoryLatestResultRepository()
        for symbol in ["AAPL", "MSFT", "NVDA"]:
            repository.upsert(_record("forward_factor", symbol))
        response = _client(repository).get(
            "/api/v1/screening", headers=_auth(), params={"limit": 1, "offset": 1}
        )
        body = response.json()
        assert body["total"] == 3
        assert body["limit"] == 1
        assert body["offset"] == 1
        assert [item["symbol"] for item in body["results"]] == ["MSFT"]

    def test_limit_above_maximum_is_rejected(self) -> None:
        response = _client().get("/api/v1/screening", headers=_auth(), params={"limit": 501})
        assert response.status_code == 422

    def test_exposes_complete_generic_result_semantics_and_history_link(self) -> None:
        repository = InMemoryLatestResultRepository()
        repository.upsert(
            _record(
                "earnings_calendar",
                "AAPL",
                opportunity_id="opportunity-1",
                lifecycle_stage="watching",
                recommendation_state="monitor",
            )
        )
        result = _client(repository).get("/api/v1/screening", headers=_auth()).json()["results"][0]
        assert result["observation_id"] == "earnings_calendar-AAPL-obs"
        assert result["opportunity_id"] == "opportunity-1"
        assert result["opportunity_history_url"].endswith("/opportunities/opportunity-1/history")
        assert result["lifecycle_stage"] == "watching"
        assert result["status"] == "monitor"
        assert result["data_quality"] == "complete"
        assert result["freshness"] in {"fresh", "stale"}
        assert result["metrics"]["strategy_native_score"] == "75"
        assert result["metric_types"]["strategy_native_score"] == "decimal"
        assert result["economics"]["estimated_return"] == "0.12"
        assert result["economics_types"]["estimated_return"] == "decimal"
        assert result["blockers"] == ["capital unavailable"]
        assert result["warnings"] == ["monitor liquidity"]
        assert result["provenance"] == ["fixture:screening"]

    def test_generic_filters_compose_before_pagination(self) -> None:
        repository = InMemoryLatestResultRepository()
        repository.upsert(
            _record(
                "earnings_calendar",
                "AAPL",
                opportunity_id="opportunity-1",
                lifecycle_stage="watching",
                recommendation_state="monitor",
            )
        )
        repository.upsert(_record("forward_factor", "MSFT"))
        response = _client(repository).get(
            "/api/v1/screening",
            headers=_auth(),
            params={
                "signal": "earnings_calendar",
                "symbol": "AAPL",
                "outcome": "pass",
                "lifecycle_stage": "watching",
                "status": "monitor",
                "limit": 1,
            },
        )
        body = response.json()
        assert body["total"] == 1
        assert body["results"][0]["opportunity_id"] == "opportunity-1"

    def test_freshness_filter_uses_documented_display_threshold(self) -> None:
        repository = InMemoryLatestResultRepository()
        repository.upsert(
            _record(
                "forward_factor",
                "AAPL",
                observed_at=datetime.now(UTC) - timedelta(minutes=5),
            )
        )
        repository.upsert(
            _record(
                "forward_factor",
                "MSFT",
                observed_at=datetime.now(UTC) - timedelta(days=2),
            )
        )
        fresh = _client(repository).get(
            "/api/v1/screening",
            headers=_auth(),
            params={"freshness": "fresh"},
        )
        stale = _client(repository).get(
            "/api/v1/screening",
            headers=_auth(),
            params={"freshness": "stale"},
        )
        assert [item["symbol"] for item in fresh.json()["results"]] == ["AAPL"]
        assert [item["symbol"] for item in stale.json()["results"]] == ["MSFT"]

    def test_numeric_metric_sort_is_deterministic_and_missing_values_are_last(self) -> None:
        repository = InMemoryLatestResultRepository()
        repository.upsert(_record("forward_factor", "AAPL", score=Decimal("20")))
        repository.upsert(_record("forward_factor", "MSFT", score=Decimal("90")))
        response = _client(repository).get(
            "/api/v1/screening/forward_factor",
            headers=_auth(),
            params={"sort_by": "metrics.strategy_native_score", "sort_order": "desc"},
        )
        assert [item["symbol"] for item in response.json()["results"]] == ["MSFT", "AAPL"]

    def test_invalid_sort_is_actionable(self) -> None:
        response = _client().get(
            "/api/v1/screening",
            headers=_auth(),
            params={"sort_by": "verdict"},
        )
        assert response.status_code == 422
        assert response.json()["detail"]["error_code"] == "INVALID_SORT"


class TestListScreeningForSignal:
    def test_filters_to_the_requested_signal_only(self) -> None:
        repository = InMemoryLatestResultRepository()
        repository.upsert(_record("forward_factor", "AAPL"))
        repository.upsert(_record("skew_momentum", "AAPL"))
        response = _client(repository).get("/api/v1/screening/forward_factor", headers=_auth())
        body = response.json()
        assert [item["signal_id"] for item in body["results"]] == ["forward_factor"]

    def test_unknown_signal_is_404_with_deterministic_error_shape(self) -> None:
        response = _client().get("/api/v1/screening/not_a_real_signal", headers=_auth())
        assert response.status_code == 404
        assert response.json()["detail"]["error_code"] == "UNKNOWN_SIGNAL"

    def test_known_signal_with_no_results_yet_returns_empty_envelope_not_404(self) -> None:
        response = _client().get("/api/v1/screening/forward_factor", headers=_auth())
        assert response.status_code == 200
        assert response.json()["results"] == []


class TestGetScreeningResult:
    def test_returns_the_single_result(self) -> None:
        repository = InMemoryLatestResultRepository()
        repository.upsert(_record("forward_factor", "AAPL"))
        response = _client(repository).get("/api/v1/screening/forward_factor/AAPL", headers=_auth())
        assert response.status_code == 200
        body = response.json()
        assert body["signal_id"] == "forward_factor"
        assert body["symbol"] == "AAPL"
        assert body["updated_at"] is not None
        assert body["age_seconds"] >= 0

    def test_unknown_signal_is_404_with_deterministic_error_shape(self) -> None:
        response = _client().get("/api/v1/screening/not_a_real_signal/AAPL", headers=_auth())
        assert response.status_code == 404
        assert response.json()["detail"]["error_code"] == "UNKNOWN_SIGNAL"

    def test_known_signal_with_no_result_for_symbol_is_404(self) -> None:
        response = _client().get("/api/v1/screening/forward_factor/AAPL", headers=_auth())
        assert response.status_code == 404
        assert response.json()["detail"]["error_code"] == "NO_SCREENING_RESULT"


class _RepositoryThatFailsOnUpsert(InMemoryLatestResultRepository):
    """Reads must never write -- any call to upsert() means a read endpoint
    tried to trigger computation instead of only reading persisted state."""

    def upsert(self, row: UniversalSignalRow) -> None:
        raise AssertionError("read endpoint attempted to persist a new result")


class TestReadsNeverComputeOrPersist:
    def test_list_screening_never_calls_upsert(self) -> None:
        response = _client(_RepositoryThatFailsOnUpsert()).get("/api/v1/screening", headers=_auth())
        assert response.status_code == 200

    def test_capabilities_never_calls_upsert(self) -> None:
        response = _client(_RepositoryThatFailsOnUpsert()).get(
            "/api/v1/capabilities", headers=_auth()
        )
        assert response.status_code == 200
