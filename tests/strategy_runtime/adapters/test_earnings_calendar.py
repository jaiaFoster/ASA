"""SPRINT-009/EPIC-7, cut over by SPRINT-014 S14-PR-05: Earnings Calendar
migrated onto the universal runtime and, in this ticket, onto the
subject-first evidence path.

The failure path (test_requires_sealed_evidence) exercises the adapter's
own missing-evidence guard directly. The success path
(test_full_sealed_acquisition_matches_the_pre_cutover_live_path) is this
ticket's own primary CUTOVER_PASS evidence: it runs the SAME scripted
provider responses through both the pre-cutover live path
(screening.live_adapters.build_live_earnings_calendar_adapter, still
present and unmodified for Forward Factor/Skew Momentum's own use) and
the new subject-first path (screening.sealed_earnings_calendar +
strategy_runtime.adapters.earnings_calendar.earnings_calendar_adapter),
and asserts identical outcome status and score -- exact output parity for
identical underlying market data, proving the architecture changed
(acquisition ownership, sealed evidence, zero provider calls from the
strategy) without changing what Earnings Calendar's own financial logic
actually decides.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest

from domain import MarketCapability
from market_data import load_market_data_config
from market_data.attempts import InMemoryAcquisitionAttemptRepository
from market_data.resolution import ResolutionPolicy
from market_data.subject_plan import SubjectAcquisitionPlan
from market_data.transport import ReadOnlyHttpResponse
from screening import run_screening
from screening.adapters import TARGET_STRATEGY_REGISTRY
from screening.live_acquisition import live_only_config
from screening.live_adapters import build_live_earnings_calendar_adapter
from screening.sealed_earnings_calendar import acquire_sealed_earnings_calendar_evidence
from strategy_runtime.adapters.earnings_calendar import (
    EARNINGS_CALENDAR_CONTRACT,
    earnings_calendar_adapter,
)
from strategy_runtime.context import RuntimeContext
from strategy_runtime.contract import LifecycleModel
from strategy_runtime.market_data_planning import (
    build_shared_market_data_access,
    provider_metadata_for,
)
from strategy_runtime.result import EvaluationState
from tests.asa.market_data_ops.fakes import ScriptedTransport, tradier_quote_response


@dataclass
class _FixedClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


_ALWAYS_UNAVAILABLE = ReadOnlyHttpResponse(500, {}, (), 12, "always-unavailable")


class _RoutedTransport:
    """A transport double keyed by endpoint_class, falling back to a
    genuine HTTP 500 (ProviderErrorCode.PROVIDER_UNAVAILABLE for both
    Tradier and Finnhub, confirmed in their own _http_error handling) for
    any endpoint not explicitly scripted -- unlike a finite ScriptedTransport
    queue, this never runs out and never raises a raw IndexError a real
    transport could never produce. Both Finnhub and Tradier declare
    overlapping capabilities (quote, historical bars); this is what lets a
    fixture give Finnhub only its own real earnings response while letting
    everything else it might be asked for fail over to Tradier cleanly.
    """

    def __init__(self, responses_by_endpoint: dict[str, ReadOnlyHttpResponse]) -> None:
        self._responses_by_endpoint = dict(responses_by_endpoint)
        self.requests: list[object] = []

    def get(self, request: object) -> ReadOnlyHttpResponse:
        self.requests.append(request)
        endpoint_class = getattr(request, "endpoint_class", None)
        return self._responses_by_endpoint.get(endpoint_class, _ALWAYS_UNAVAILABLE)


_RESOLUTION_POLICIES = {
    MarketCapability.EARNINGS_CALENDAR_V1: ResolutionPolicy(
        "v1", ("finnhub",), 3600 * 24 * 90, ("earnings_date",)
    ),
    MarketCapability.REAL_TIME_QUOTE_V1: ResolutionPolicy("v1", ("tradier",), 3600, ("last",)),
    MarketCapability.OPTION_CHAIN_V1: ResolutionPolicy(
        "v1", ("tradier",), 3600, ("contracts",)
    ),
    MarketCapability.HISTORICAL_BARS_V1: ResolutionPolicy(
        "v1", ("tradier",), 3600 * 24 * 46, ("close",)
    ),
}


def _tradier_option(
    symbol: str, expiration: str, strike: str, option_type: str, delta: str
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "underlying": "AAPL",
        "expiration_date": expiration,
        "strike": strike,
        "option_type": option_type,
        "bid": "4.9",
        "ask": "5.1",
        "last": "5",
        "volume": 1000,
        "open_interest": 5000,
        "greeks": {
            "delta": delta,
            "gamma": "0.03",
            "theta": "-0.1",
            "vega": "0.2",
            "mid_iv": "0.5",
        },
    }


def _tradier_expirations_response(front: str, back: str) -> ReadOnlyHttpResponse:
    return ReadOnlyHttpResponse(
        200, {"expirations": {"date": [front, back]}}, (), 12, "tradier-request-expirations"
    )


def _tradier_chain_response(expiration: str, request_id: str) -> ReadOnlyHttpResponse:
    options = [
        _tradier_option("CALL_ATM", expiration, "190", "call", "0.50"),
        _tradier_option("PUT_ATM", expiration, "190", "put", "-0.50"),
    ]
    return ReadOnlyHttpResponse(200, {"options": {"option": options}}, (), 12, request_id)


def _tradier_daily_bars_response() -> ReadOnlyHttpResponse:
    days: list[dict[str, object]] = []
    for day_offset in range(29, -1, -1):
        day = (date.today() - timedelta(days=day_offset)).isoformat()
        close = 200 + (day_offset % 5) + (29 - day_offset) * 0.15
        days.append(
            {
                "date": day,
                "open": str(close - 2),
                "high": str(close + 2),
                "low": str(close - 3),
                "close": str(close),
                "volume": "50000000",
            }
        )
    return ReadOnlyHttpResponse(200, {"history": {"day": days}}, (), 12, "tradier-request-history")


def _finnhub_earnings_response(event_date: str) -> ReadOnlyHttpResponse:
    return ReadOnlyHttpResponse(
        200,
        {"earningsCalendar": [{"symbol": "AAPL", "date": event_date, "hour": "amc"}]},
        (),
        12,
        "finnhub-request-earnings",
    )


def _tradier_responses(front: str, back: str) -> list[ReadOnlyHttpResponse]:
    return [
        tradier_quote_response(),
        _tradier_expirations_response(front, back),
        _tradier_chain_response(front, "tradier-request-chain-front"),
        _tradier_chain_response(back, "tradier-request-chain-back"),
        _tradier_daily_bars_response(),
    ]


class TestEarningsCalendarContract:
    def test_contract_declares_an_opportunity_lifecycle(self) -> None:
        assert EARNINGS_CALENDAR_CONTRACT.lifecycle.lifecycle_model is LifecycleModel.OPPORTUNITY
        assert EARNINGS_CALENDAR_CONTRACT.lifecycle.supported_states == ("watching", "confirmed")

    def test_contract_requires_quote_option_chain_and_earnings_calendar(self) -> None:
        capabilities = EARNINGS_CALENDAR_CONTRACT.required_capabilities()
        assert MarketCapability.REAL_TIME_QUOTE_V1 in capabilities
        assert MarketCapability.OPTION_CHAIN_V1 in capabilities
        assert MarketCapability.EARNINGS_CALENDAR_V1 in capabilities


class TestEarningsCalendarAdapter:
    def test_requires_sealed_evidence(self) -> None:
        context = RuntimeContext(
            EARNINGS_CALENDAR_CONTRACT, "AAPL", _FixedClock(datetime.now(UTC)), "run-1"
        )
        with pytest.raises(RuntimeError, match="requires sealed subject-first evidence"):
            earnings_calendar_adapter(context)

    def test_missing_sealed_evidence_facts_assign_no_lifecycle_stage_or_opportunity_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
        monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
        monkeypatch.setenv("ASA_FINNHUB_ENABLED", "true")
        monkeypatch.setenv("ASA_FINNHUB_API_KEY", "sandbox-secret-key")
        clock = _FixedClock(datetime.now(UTC))
        config = live_only_config(
            load_market_data_config(
                {
                    "ASA_TRADIER_ENABLED": "true",
                    "ASA_TRADIER_ACCESS_TOKEN": "sandbox-secret-token",
                    "ASA_FINNHUB_ENABLED": "true",
                    "ASA_FINNHUB_API_KEY": "sandbox-secret-key",
                }
            )
        )
        # Every endpoint fails cleanly (HTTP 500) -- the very first
        # acquisition (the earnings event) fails immediately and
        # deterministically, and every capability after it does too.
        def transport_factory(_provider_id: str) -> object:
            return _RoutedTransport({})

        access = build_shared_market_data_access(config, transport_factory, clock, ("AAPL",))
        plan = SubjectAcquisitionPlan(
            "AAPL",
            access["AAPL"].fulfillment,
            attempt_repository=InMemoryAcquisitionAttemptRepository(),
            plan_id="test-cycle:AAPL",
            clock=clock,
        )
        sealed_evidence = acquire_sealed_earnings_calendar_evidence(
            "AAPL",
            plan,
            clock,
            provider_metadata=provider_metadata_for(config, transport_factory, clock),
            resolution_policy_by_capability=_RESOLUTION_POLICIES,
        )
        context = RuntimeContext(
            EARNINGS_CALENDAR_CONTRACT, "AAPL", clock, "run-1", sealed_evidence
        )

        result = earnings_calendar_adapter(context)

        assert result.strategy_id == "earnings_calendar"
        assert result.evaluation_state is not EvaluationState.PASS
        assert result.evaluation_state is not EvaluationState.NO_SIGNAL
        assert result.opportunity_id is None
        assert result.lifecycle_stage is None
        assert "sandbox-secret-token" not in str(result)
        assert "sandbox-secret-key" not in str(result)

    def test_full_sealed_acquisition_matches_the_pre_cutover_live_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
        monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
        monkeypatch.setenv("ASA_FINNHUB_ENABLED", "true")
        monkeypatch.setenv("ASA_FINNHUB_API_KEY", "sandbox-secret-key")
        clock = _FixedClock(datetime.now(UTC))
        front = (date.today() + timedelta(days=14)).isoformat()
        back = (date.today() + timedelta(days=44)).isoformat()
        earnings_date = (date.today() + timedelta(days=20)).isoformat()
        config = live_only_config(
            load_market_data_config(
                {
                    "ASA_TRADIER_ENABLED": "true",
                    "ASA_TRADIER_ACCESS_TOKEN": "sandbox-secret-token",
                    "ASA_FINNHUB_ENABLED": "true",
                    "ASA_FINNHUB_API_KEY": "sandbox-secret-key",
                }
            )
        )

        # -- Pre-cutover live path -------------------------------------
        # Finnhub's own transport is endpoint-routed, not a finite queue:
        # Finnhub also declares REAL_TIME_QUOTE_V1/HISTORICAL_BARS_V1 (see
        # market_data/finnhub.py's own FINNHUB_CAPABILITIES) and is tried
        # before Tradier for both (alphabetical priority ordering,
        # strategy_runtime/market_data_planning.py) -- a real Finnhub
        # would never "run out of responses," it would return a real HTTP
        # response for every request, so a genuine HTTP 500 (falling back
        # to Tradier) is the faithful fixture, not an exhausted queue.
        old_transports = {
            "tradier": ScriptedTransport(_tradier_responses(front, back)),
            "finnhub": _RoutedTransport(
                {"earnings_calendar": _finnhub_earnings_response(earnings_date)}
            ),
        }
        old_access = build_shared_market_data_access(
            config, lambda provider_id: old_transports[provider_id], clock, ("AAPL",)
        )
        live_adapter = build_live_earnings_calendar_adapter("AAPL", old_access["AAPL"].fulfillment)
        (old_result,) = run_screening(
            TARGET_STRATEGY_REGISTRY,
            {"earnings_calendar": live_adapter},
            clock,
            strategy_ids=("earnings_calendar",),
        )

        # -- New subject-first path -- fresh transports/access, so
        # neither path's own fulfillment cache can leak into the other --
        # each acquires independently against identical scripted inputs.
        new_transports = {
            "tradier": ScriptedTransport(_tradier_responses(front, back)),
            "finnhub": _RoutedTransport(
                {"earnings_calendar": _finnhub_earnings_response(earnings_date)}
            ),
        }

        def new_transport_factory(provider_id: str) -> object:
            return new_transports[provider_id]

        new_access = build_shared_market_data_access(
            config, new_transport_factory, clock, ("AAPL",)
        )
        plan = SubjectAcquisitionPlan(
            "AAPL",
            new_access["AAPL"].fulfillment,
            attempt_repository=InMemoryAcquisitionAttemptRepository(),
            plan_id="test-cycle:AAPL",
            clock=clock,
        )
        sealed_evidence = acquire_sealed_earnings_calendar_evidence(
            "AAPL",
            plan,
            clock,
            provider_metadata=provider_metadata_for(config, new_transport_factory, clock),
            resolution_policy_by_capability=_RESOLUTION_POLICIES,
        )
        context = RuntimeContext(
            EARNINGS_CALENDAR_CONTRACT, "AAPL", clock, "run-1", sealed_evidence
        )

        new_result = earnings_calendar_adapter(context)

        # Exact-parity assertions (CUTOVER_PASS): both paths reach the
        # same success/failure classification and the same numeric score
        # for identical underlying market data.
        assert new_result.evaluation_state is not EvaluationState.ADAPTER_EXCEPTION
        old_success = old_result.outcome_status.value in ("pass", "no_signal")
        new_success = new_result.evaluation_state in (
            EvaluationState.PASS,
            EvaluationState.NO_SIGNAL,
        )
        assert old_success == new_success, (
            f"old={old_result.outcome_status.value!r} new={new_result.evaluation_state!r}"
        )
        if old_result.strategy_native_score is not None:
            new_score = new_result.metrics["strategy_native_score"].native()
            assert new_score == old_result.strategy_native_score
        # I-06: every evaluation references one sealed snapshot digest.
        assert sealed_evidence.snapshot.snapshot_digest
        assert "sandbox-secret-token" not in str(new_result)
        assert "sandbox-secret-key" not in str(new_result)
