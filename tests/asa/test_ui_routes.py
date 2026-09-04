from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from asa.api.screening_models import ScreeningResultResponse
from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from tests.asa.fakes import InMemoryLatestResultRepository, InMemoryObservationRepository

FIXTURE = Path(__file__).parents[1] / "fixtures" / "ui-screening-result.json"


def _client() -> TestClient:
    return TestClient(
        build_application(
            Settings(agent_api_token=SecretStr("ui-token"), _env_file=None),
            DependencyOverrides(
                repository=InMemoryObservationRepository(),
                latest_result_repository=InMemoryLatestResultRepository(),
            ),
        )
    )


def test_ui_shell_and_packaged_assets_return_200() -> None:
    client = _client()

    shell = client.get("/ui")
    assert shell.status_code == 200
    assert "ASA Intelligence Console" in shell.text
    assert "Content-Security-Policy" in shell.text
    for asset in (
        "app.js",
        "api-client.js",
        "pagination.js",
        "state.js",
        "render.js",
        "styles.css",
    ):
        response = client.get(f"/ui/static/{asset}")
        assert response.status_code == 200
        assert response.content


def test_static_assets_are_inside_the_installed_asa_package() -> None:
    static = files("asa.ui").joinpath("static")
    assert static.joinpath("index.html").is_file()
    assert static.joinpath("app.js").is_file()


def test_shared_ui_fixture_is_a_valid_public_response() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    response = ScreeningResultResponse.model_validate(payload)

    assert response.signal_id == "skew_momentum"
    assert response.verdict == "WATCH"
    assert response.evaluation_state == "pass"
    assert response.gate_results["momentum_complete"] == "UNKNOWN"


def test_ui_mount_does_not_change_protected_api_authentication() -> None:
    client = _client()

    assert client.get("/api/v1/capabilities").status_code == 404
    assert (
        client.get(
            "/api/v1/capabilities",
            headers={"Authorization": "Bearer wrong-token"},
        ).status_code
        == 404
    )
    assert (
        client.get(
            "/api/v1/capabilities",
            headers={"Authorization": "Bearer ui-token"},
        ).status_code
        == 200
    )


def test_ui_client_is_get_only_and_never_persists_token_in_local_storage() -> None:
    static = files("asa.ui").joinpath("static")
    client_source = static.joinpath("api-client.js").read_text(encoding="utf-8")
    application_source = static.joinpath("app.js").read_text(encoding="utf-8")

    assert 'method: "GET"' in client_source
    assert "POST" not in client_source
    assert "/execution-readiness" in client_source
    assert "refresh" not in client_source.lower()
    assert "localStorage" not in client_source + application_source
    assert "sessionStorage" in client_source


def test_ui_traverses_all_pages_and_rejects_incompatible_snapshots() -> None:
    static = files("asa.ui").joinpath("static")
    client_source = static.joinpath("api-client.js").read_text(encoding="utf-8")
    pagination_source = static.joinpath("pagination.js").read_text(encoding="utf-8")

    assert "collectCompleteScreeningState" in client_source
    assert "active_only=true" in client_source
    assert "while (authoritativeTotal === null || results.length < authoritativeTotal)" in (
        pagination_source
    )
    assert "page.snapshot_identity !== snapshotIdentity" in pagination_source
    assert "Duplicate screening identity across pages" in pagination_source
    assert "page.retained_nonactive_total !== retainedNonactiveTotal" in pagination_source


def test_ui_separates_strategy_analytical_state_from_infrastructure_health() -> None:
    static = files("asa.ui").joinpath("static")
    client_source = static.joinpath("api-client.js").read_text(encoding="utf-8")
    render_source = static.joinpath("render.js").read_text(encoding="utf-8")

    assert "/api/v1/screening-health" in client_source
    assert "ANALYTICAL COMPLETENESS" in render_source
    assert "separate from service health and data freshness" in render_source
    assert "missing_data: funnel.missing_data" in render_source
    assert "no_signal: funnel.no_signal" in render_source
    assert "missing_data_reasons: Object.fromEntries" in render_source
    assert "funnel.typed_unknown_counts || []" in render_source
    assert "Fresh missing-data rows remain analytically incomplete" in render_source


def test_ui_distinguishes_visible_loaded_and_authoritative_total_and_build() -> None:
    static = files("asa.ui").joinpath("static")
    application_source = static.joinpath("app.js").read_text(encoding="utf-8")
    render_source = static.joinpath("render.js").read_text(encoding="utf-8")

    assert "state.resultsTotal = results.data.total" in application_source
    assert "state.resultsSnapshotIdentity = results.data.snapshot_identity" in (
        application_source
    )
    assert '["Visible rows", String(model.visible.length)]' in render_source
    assert '["Loaded rows", String(model.results.length)]' in render_source
    assert '["Active latest-state rows", String(model.resultsTotal)]' in render_source
    assert 'model.buildIdentity?.release_sha || "Unavailable"' in render_source


def test_ui_exposes_exact_structure_and_explicit_modeled_pnl_assumptions() -> None:
    render_source = (
        files("asa.ui").joinpath("static", "render.js").read_text(encoding="utf-8")
    )

    assert "Execution readiness — analytical only" in render_source
    assert "Exact leg" in render_source
    assert "Model with explicit assumptions" in render_source
    assert "Modeled P&L at front expiration" in render_source
