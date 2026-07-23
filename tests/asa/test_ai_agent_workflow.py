"""API-005: AI agent workflow validation (SPRINT-008).

Exercises this ticket's own validation_flow end to end -- discover
capabilities, retrieve screening data, inspect timestamps, decide
whether refresh is needed, refresh one opportunity, retrieve the
updated result, generate a structured morning brief -- entirely through
this test's own role as an external HTTP client
(fastapi.testclient.TestClient). This module never imports screening.cli
or calls screening.service/ScreeningStateRepository directly: every step
below is a plain HTTP request, exactly as a production AI agent would
have to make it, proving the API alone -- not the CLI -- is sufficient
(success criterion: no_cli_dependency).

The morning brief is built only from HTTP response JSON already returned
to the caller (_build_morning_brief below), not from any internal
screening/ object, since generating it is this validation harness's own
job (what an agent does with the data), not a new server endpoint --
API-005 adds no production code.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from pydantic import SecretStr

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from market_data.transport import ReadOnlyHttpResponse
from screening.state import ScreeningStateRecord
from tests.asa.fakes import InMemoryScreeningStateRepository
from tests.asa.market_data_ops.fakes import ScriptedTransport, tradier_quote_response

# An agent-side freshness policy, not part of the API contract itself --
# the API only ever reports age_seconds; deciding what counts as "stale"
# is left entirely to the caller, exactly as SPRINT-008 intends.
STALE_THRESHOLD_SECONDS = 4 * 3600
FAKE_PROVIDER_CREDENTIAL = "sandbox-secret-token"


def _seed_repository() -> InMemoryScreeningStateRepository:
    """Represents state already produced by a prior batch run: one fresh
    result an agent should leave alone, one stale result an agent should
    decide to refresh."""
    repository = InMemoryScreeningStateRepository()
    now = datetime.now(UTC)
    repository.upsert(
        ScreeningStateRecord(
            signal_id="forward_factor",
            signal_version="1.0.0",
            symbol="NVDA",
            outcome="pass",
            explanation="calendar richness within bounds",
            metrics={"strategy_native_score": "0.42"},
            updated_at=now - timedelta(minutes=2),
            dependency_timestamps={"as_of": now - timedelta(minutes=2)},
        )
    )
    repository.upsert(
        ScreeningStateRecord(
            signal_id="skew_momentum",
            signal_version="1.0.0",
            symbol="AAPL",
            outcome="no_signal",
            explanation="prior overnight batch result",
            metrics={},
            updated_at=now - timedelta(hours=20),
            dependency_timestamps={"as_of": now - timedelta(hours=20)},
        )
    )
    return repository


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


def _client(repository: InMemoryScreeningStateRepository) -> TestClient:
    expiration = (date.today() + timedelta(days=7)).isoformat()
    responses = _tradier_refresh_responses(expiration)
    return TestClient(
        build_application(
            Settings(agent_api_token=SecretStr("correct-token"), _env_file=None),
            DependencyOverrides(
                screening_state_repository=repository,
                market_data_transport_factory=lambda _provider_id: ScriptedTransport(responses),
            ),
        )
    )


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer correct-token"}


def _build_morning_brief(
    results: list[dict[str, object]], refreshed_pairs: list[tuple[str, str]]
) -> dict[str, object]:
    """The kind of structured summary an agent would hand back to a
    human -- built only from fields already present in the API's own
    JSON responses."""
    ordered = sorted(results, key=lambda item: (item["signal_id"], item["symbol"]))
    lines = [
        f"{item['signal_id']}/{item['symbol']}: {item['outcome']} "
        f"(updated {item['age_seconds']}s ago)"
        for item in ordered
    ]
    return {
        "opportunity_count": len(ordered),
        "refreshed": [{"signal_id": s, "symbol": sym} for s, sym in refreshed_pairs],
        "summary": "\n".join(lines),
    }


def test_ai_agent_workflow_discovers_reads_refreshes_and_briefs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", FAKE_PROVIDER_CREDENTIAL)
    repository = _seed_repository()
    client = _client(repository)
    transcript: list[Response] = []

    # Step 1: discover_capabilities
    capabilities_response = client.get("/api/v1/capabilities", headers=_auth())
    transcript.append(capabilities_response)
    assert capabilities_response.status_code == 200
    signals = capabilities_response.json()["signals"]
    assert {item["signal_id"] for item in signals} == {
        "earnings_calendar",
        "forward_factor",
        "skew_momentum",
    }

    # Step 2: retrieve_screening_data
    screening_response = client.get("/api/v1/screening", headers=_auth())
    transcript.append(screening_response)
    assert screening_response.status_code == 200
    results = screening_response.json()["results"]
    assert len(results) == 2

    # Step 3: inspect_timestamps
    for result in results:
        assert result["age_seconds"] >= 0
        assert result["updated_at"] is not None

    # Step 4: determine_whether_refresh_is_needed
    stale = [item for item in results if item["age_seconds"] > STALE_THRESHOLD_SECONDS]
    assert len(stale) == 1
    target = stale[0]
    assert (target["signal_id"], target["symbol"]) == ("skew_momentum", "AAPL")

    # Step 5: refresh_one_opportunity -- exactly the one stale pair, nothing else
    refresh_response = client.post(
        f"/api/v1/screening/{target['signal_id']}/{target['symbol']}/refresh",
        headers=_auth(),
    )
    transcript.append(refresh_response)
    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    assert refreshed["request_count"] >= 1

    # Step 6: retrieve_updated_result
    updated_response = client.get(
        f"/api/v1/screening/{target['signal_id']}/{target['symbol']}", headers=_auth()
    )
    transcript.append(updated_response)
    assert updated_response.status_code == 200
    updated = updated_response.json()
    assert updated["age_seconds"] < STALE_THRESHOLD_SECONDS
    assert updated["updated_at"] != target["updated_at"]

    # deterministic_responses: an unchanged GET immediately after returns
    # the same result (age_seconds may tick by at most a second).
    repeat_response = client.get(
        f"/api/v1/screening/{target['signal_id']}/{target['symbol']}", headers=_auth()
    )
    transcript.append(repeat_response)
    repeat = repeat_response.json()
    for field in (
        "signal_id",
        "signal_version",
        "symbol",
        "outcome",
        "explanation",
        "metrics",
        "updated_at",
    ):
        assert repeat[field] == updated[field]
    assert abs(repeat["age_seconds"] - updated["age_seconds"]) <= 1

    # Step 7: generate_structured_morning_brief
    final_screening_response = client.get("/api/v1/screening", headers=_auth())
    transcript.append(final_screening_response)
    all_results = final_screening_response.json()["results"]
    brief = _build_morning_brief(all_results, [("skew_momentum", "AAPL")])
    assert brief["opportunity_count"] == len(all_results) == 2
    assert brief["refreshed"] == [{"signal_id": "skew_momentum", "symbol": "AAPL"}]
    assert "skew_momentum/AAPL" in str(brief["summary"])
    assert "forward_factor/NVDA" in str(brief["summary"])

    # success criterion: no_provider_credentials_exposed
    for response in transcript:
        assert FAKE_PROVIDER_CREDENTIAL not in response.text
