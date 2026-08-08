"""API-004: POST /api/v1/screening/{signal}/{symbol}/refresh."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from market_data.transport import ReadOnlyHttpResponse
from strategy_runtime.orchestration import ShadowParityDiagnostic
from strategy_runtime.persistence import UniversalSignalRow
from strategy_runtime.result import EvaluationState, ResultTemporalMetadata, RowType
from tests.asa.fakes import InMemoryLatestResultRepository
from tests.asa.market_data_ops.fakes import ScriptedTransport, tradier_quote_response


def _client(
    transport_factory: Callable[[str], object] | None = None,
    repository: InMemoryLatestResultRepository | None = None,
) -> TestClient:
    return TestClient(
        build_application(
            Settings(agent_api_token=SecretStr("correct-token"), _env_file=None),
            DependencyOverrides(
                latest_result_repository=repository
                or InMemoryLatestResultRepository(),
                market_data_transport_factory=transport_factory,
            ),
        )
    )


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer correct-token"}


def _tradier_refresh_responses(expiration: str) -> list[ReadOnlyHttpResponse]:
    return [
        tradier_quote_response(),
        ReadOnlyHttpResponse(
            200, {"expirations": {"date": [expiration]}}, (), 12, "tradier-request-2"
        ),
        ReadOnlyHttpResponse(
            200,
            {
                "options": {
                    "option": [
                        {
                            "symbol": "AAPL_TEST_CALL",
                            "underlying": "AAPL",
                            "expiration_date": expiration,
                            "strike": "190",
                            "option_type": "call",
                            "bid": "4.9",
                            "ask": "5.1",
                            "last": "5",
                            "volume": 1000,
                            "open_interest": 5000,
                            "greeks": {
                                "delta": "0.5",
                                "gamma": "0.03",
                                "theta": "-0.1",
                                "vega": "0.2",
                                "rho": "0.01",
                            },
                        }
                    ]
                }
            },
            (),
            12,
            "tradier-request-3",
        ),
    ]


class TestAuthenticationAndValidation:
    def test_without_authorization_header_is_404(self) -> None:
        response = _client().post("/api/v1/screening/skew_momentum/AAPL/refresh")
        assert response.status_code == 404

    def test_unknown_signal_is_404(self) -> None:
        response = _client().post(
            "/api/v1/screening/not_a_real_signal/AAPL/refresh", headers=_auth()
        )
        assert response.status_code == 404
        assert response.json()["detail"]["error_code"] == "UNKNOWN_SIGNAL"

    def test_symbol_outside_approved_live_universe_is_422(self) -> None:
        response = _client().post(
            "/api/v1/screening/skew_momentum/NOTREAL/refresh", headers=_auth()
        )
        assert response.status_code == 422
        assert response.json()["detail"]["error_code"] == "UNSUPPORTED_SYMBOL"

    def test_no_live_provider_configured_is_503(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No ASA_TRADIER_ENABLED/ASA_FINNHUB_ENABLED/ASA_ALPHA_VANTAGE_ENABLED set
        # -- every provider is disabled by default.
        for name in (
            "ASA_TRADIER_ENABLED",
            "ASA_FINNHUB_ENABLED",
            "ASA_ALPHA_VANTAGE_ENABLED",
        ):
            monkeypatch.delenv(name, raising=False)
        response = _client().post("/api/v1/screening/skew_momentum/AAPL/refresh", headers=_auth())
        assert response.status_code == 503
        assert response.json()["detail"]["error_code"] == "NO_LIVE_PROVIDER_CONFIGURED"


class TestSuccessfulRefresh:
    def test_refresh_persists_and_returns_a_result_with_request_accounting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
        monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
        expiration = (date.today() + timedelta(days=7)).isoformat()
        responses = _tradier_refresh_responses(expiration)
        client = _client(transport_factory=lambda _provider_id: ScriptedTransport(responses))

        response = client.post("/api/v1/screening/skew_momentum/AAPL/refresh", headers=_auth())

        assert response.status_code == 200
        body = response.json()
        assert body["signal_id"] == "skew_momentum"
        assert body["symbol"] == "AAPL"
        assert body["request_count"] >= 1
        assert body["provider_contacted"] is True
        assert body["refresh_failed"] is False
        assert body["updated_at"] is not None
        assert body["age_seconds"] >= 0
        assert body["observed_at"] is not None
        assert body["received_at"] is not None
        assert body["evaluated_at"] is not None
        assert body["persisted_at"] is not None
        assert body["market_session_date"] is not None
        assert body["market_session_status"] in {
            "premarket",
            "open",
            "after_hours",
            "weekend",
            "holiday",
        }
        assert body["freshness_status"] in {"live", "prior_session"}
        assert body["usability_status"] in {"usable", "usable_with_warning"}
        assert isinstance(body["warning_codes"], list)
        assert body["input_time_skew_seconds"] >= 0
        # "sandbox-secret-token" must never appear in the response.
        assert "sandbox-secret-token" not in response.text

    def test_refresh_result_is_then_visible_via_get(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
        monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
        expiration = (date.today() + timedelta(days=7)).isoformat()
        responses = _tradier_refresh_responses(expiration)
        client = _client(transport_factory=lambda _provider_id: ScriptedTransport(responses))

        client.post("/api/v1/screening/skew_momentum/AAPL/refresh", headers=_auth())
        follow_up = client.get("/api/v1/screening/skew_momentum/AAPL", headers=_auth())

        assert follow_up.status_code == 200
        assert follow_up.json()["symbol"] == "AAPL"
        assert follow_up.json()["observed_at"] is not None
        assert follow_up.json()["usability_status"] in {
            "usable",
            "usable_with_warning",
        }

    def test_on_demand_refresh_inside_cooldown_does_not_contact_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
        monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
        expiration = (date.today() + timedelta(days=7)).isoformat()
        constructions = 0

        def transport_factory(_provider_id: str) -> object:
            nonlocal constructions
            constructions += 1
            return ScriptedTransport(_tradier_refresh_responses(expiration))

        client = _client(transport_factory=transport_factory)
        first = client.post(
            "/api/v1/screening/skew_momentum/AAPL/refresh", headers=_auth()
        )
        second = client.post(
            "/api/v1/screening/skew_momentum/AAPL/refresh", headers=_auth()
        )

        assert first.status_code == second.status_code == 200
        assert second.json()["provider_contacted"] is False
        assert second.json()["request_count"] == 0
        assert second.json()["result_changed"] is False
        assert constructions == 1


def _seeded_row_with_recent_attempt(signal_id: str, symbol: str) -> UniversalSignalRow:
    """A prior result whose own last_refresh_attempt_at is "now" -- always
    well inside ON_DEMAND_COOLDOWN regardless of when the test runs.
    """
    now = datetime.now(UTC)
    temporal = ResultTemporalMetadata(
        observed_at=now,
        received_at=now,
        evaluated_at=now,
        persisted_at=now,
        market_session_date=now.date(),
        market_session_status="open",
        age_seconds=0,
        last_refresh_attempt_at=now,
        last_successful_refresh_at=now,
        next_refresh_at=now + timedelta(hours=1),
        data_advanced_on_last_refresh=True,
        freshness_status="live",
        usability_status="usable",
        usability_reason="fresh enough",
        warning_codes=(),
        acquisition_started_at=now,
        acquisition_completed_at=now,
        input_time_skew_seconds=0,
    )
    return UniversalSignalRow(
        signal_id=signal_id,
        signal_version="1.0.0",
        symbol=symbol,
        observation_id=f"{signal_id}-{symbol}-seed",
        opportunity_id=None,
        row_type=RowType.RESULT.value,
        verdict="PASS",
        evaluation_state=EvaluationState.PASS.value,
        lifecycle_stage=None,
        recommendation_state=None,
        data_quality=None,
        metrics={},
        economics={},
        blockers=(),
        warnings=(),
        provenance=(),
        observed_at=now,
        temporal=temporal,
    )


class TestShadowWiring:
    """SPRINT-014 S14-PR-05A, Architect checkpoint: sixteenth review,
    "final wiring increment": this route now builds a SubjectAcquisitionPlan
    + PlanBackedFulfillment per request and, only for a signal with a
    registered shadow binding, attempts subject-first shadow preparation
    sharing that same plan.
    """

    def test_cooldown_hit_makes_zero_provider_contact_and_zero_shadow_preparation(
        self,
    ) -> None:
        """"API cooldown stays before all acquisition construction/
        preparation. A cooldown hit must remain zero provider contacts
        and zero shadow work, exactly as today." Uses earnings_calendar
        -- the one registered shadow-eligible signal -- specifically
        because an unshadowed signal's cooldown path would never have
        exercised the shadow-preparation branch at all.
        """
        repository = InMemoryLatestResultRepository()
        repository.upsert(_seeded_row_with_recent_attempt("earnings_calendar", "AAPL"))
        constructions = 0

        def transport_factory(_provider_id: str) -> object:
            nonlocal constructions
            constructions += 1
            raise AssertionError("transport must never be constructed on a cooldown hit")

        client = _client(transport_factory=transport_factory, repository=repository)

        response = client.post(
            "/api/v1/screening/earnings_calendar/AAPL/refresh", headers=_auth()
        )

        assert response.status_code == 200
        assert response.json()["provider_contacted"] is False
        assert response.json()["request_count"] == 0
        assert constructions == 0

    def test_unshadowed_signal_makes_no_earnings_only_acquisition(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """"Do not eagerly acquire shadow-only data for an unshadowed API
        request ... shadow preparation must be limited to shadowed
        strategies actually requested for that subject." skew_momentum
        has no registered shadow binding, so its own refresh must consume
        exactly its own 3 scripted requests (quote/expirations/chain) --
        never one more for an Earnings-only capability. The scripted
        transport is exactly sized (no slack): a shadow-only acquisition
        attempt would either exhaust it (IndexError) or show up as an
        unexpected extra request_count, either of which this test catches.
        """
        monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
        monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
        expiration = (date.today() + timedelta(days=7)).isoformat()
        responses = _tradier_refresh_responses(expiration)
        client = _client(transport_factory=lambda _provider_id: ScriptedTransport(responses))

        response = client.post(
            "/api/v1/screening/skew_momentum/AAPL/refresh", headers=_auth()
        )

        assert response.status_code == 200
        assert response.json()["request_count"] == len(responses) == 3

    def test_shadow_parity_diagnostic_is_logged_and_never_in_the_http_response(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """"Log/record shadow diagnostics internally instead ... do not
        expose ShadowParityDiagnostic in the HTTP response in this
        increment." refresh_with_shadow() itself is replaced here so this
        test exercises exactly this route's own logging call site,
        decoupled from real acquisition or the (separately, exhaustively
        tested in tests/strategy_runtime/test_orchestration.py)
        correctness of the diagnostic's own content.
        """
        import asa.api.screening_routes as screening_routes_module
        from strategy_runtime.result import UniversalScreeningResult

        legacy_result = UniversalScreeningResult(
            strategy_id="earnings_calendar",
            strategy_version="1.0.0",
            symbol="AAPL",
            observation_id="legacy-obs",
            opportunity_id=None,
            row_type=RowType.RESULT,
            verdict="PASS",
            evaluation_state=EvaluationState.PASS,
            lifecycle_stage=None,
            recommendation_state=None,
            data_quality=None,
            metrics={},
            economics={},
            blockers=(),
            warnings=(),
            provenance=(),
            observed_at=datetime.now(UTC),
        )
        diagnostic = ShadowParityDiagnostic(
            strategy_id="earnings_calendar",
            symbol="AAPL",
            status="shadow_unknown",
            shadow_unknown_code="synthetic_gap",
            shadow_unknown_demand_ids=("demand-a",),
            legacy_verdict="PASS",
            shadow_snapshot_id=None,
            shadow_snapshot_digest=None,
        )

        def _fake_refresh_with_shadow(
            *_args: object, **_kwargs: object
        ) -> tuple[UniversalScreeningResult, ShadowParityDiagnostic]:
            return legacy_result, diagnostic

        monkeypatch.setattr(
            screening_routes_module, "refresh_with_shadow", _fake_refresh_with_shadow
        )
        monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
        monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
        # build_application() -> configure_logging() replaces the root
        # logger's own handler list wholesale (root.handlers = [handler]),
        # which silently evicts pytest's own caplog handler -- reattach it
        # after the app (and its logging config) already exists, since
        # set_level() alone only adjusts levels, never re-adds a handler.
        client = _client(transport_factory=lambda _provider_id: ScriptedTransport([]))
        caplog.set_level(logging.INFO, logger="asa.api.screening_routes")
        logging.getLogger().addHandler(caplog.handler)

        response = client.post(
            "/api/v1/screening/earnings_calendar/AAPL/refresh", headers=_auth()
        )

        assert response.status_code == 200
        assert "shadow" not in response.text.lower()
        entries = [
            record for record in caplog.records if record.message == "shadow_parity_diagnostic"
        ]
        assert len(entries) == 1
        entry = entries[0]
        assert entry.signal_id == "earnings_calendar"
        assert entry.symbol == "AAPL"
        assert entry.shadow_status == "shadow_unknown"
        assert entry.shadow_unknown_code == "synthetic_gap"
        assert entry.shadow_unknown_demand_ids == ("demand-a",)
