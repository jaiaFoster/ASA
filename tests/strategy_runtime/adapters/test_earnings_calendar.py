"""SPRINT-009/EPIC-7: Earnings Calendar migrated onto the universal
runtime -- the lifecycle-tracking migration target.

Only the failure path is exercised with a full live-acquisition round
trip here: earnings_calendar's own live adapter acquires an earnings
event (EARNINGS_CALENDAR_V1, Finnhub-shaped) before anything else, and
scripting a realistic Finnhub earnings-calendar response is deliberately
out of this test's scope -- an empty/exhausted ScriptedTransport reliably
produces a non-success, isolated outcome, which is exactly what this
test needs to prove earnings_calendar's own stage-assignment logic
(no stage for a non-success outcome). The successful PASS/NO_SIGNAL ->
stage mapping itself is not re-tested here: it reuses
_screening_bridge.translate_screening_result, already proven by
forward_factor's and skew_momentum's own full successful-path tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from domain import MarketCapability
from market_data import load_market_data_config
from strategy_runtime.adapters.earnings_calendar import (
    EARNINGS_CALENDAR_CONTRACT,
    earnings_calendar_adapter,
)
from strategy_runtime.context import RuntimeContext
from strategy_runtime.contract import LifecycleModel
from strategy_runtime.market_data_planning import build_shared_market_data_access
from strategy_runtime.result import EvaluationState
from tests.asa.market_data_ops.fakes import ScriptedTransport


@dataclass
class _FixedClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


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
    def test_requires_shared_fulfillment(self) -> None:
        context = RuntimeContext(
            EARNINGS_CALENDAR_CONTRACT, "AAPL", _FixedClock(datetime.now(UTC)), "run-1"
        )
        with pytest.raises(RuntimeError, match="requires shared market data access"):
            earnings_calendar_adapter(context)

    def test_a_non_success_outcome_assigns_no_lifecycle_stage_or_opportunity_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
        monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
        monkeypatch.setenv("ASA_FINNHUB_ENABLED", "true")
        monkeypatch.setenv("ASA_FINNHUB_API_KEY", "sandbox-secret-key")
        clock = _FixedClock(datetime.now(UTC))
        config = load_market_data_config(
            {
                "ASA_TRADIER_ENABLED": "true",
                "ASA_TRADIER_ACCESS_TOKEN": "sandbox-secret-token",
                "ASA_FINNHUB_ENABLED": "true",
                "ASA_FINNHUB_API_KEY": "sandbox-secret-key",
            }
        )
        # No scripted responses at all -- the very first acquisition
        # (the earnings event) fails immediately and deterministically.
        access = build_shared_market_data_access(
            config, lambda _provider_id: ScriptedTransport([]), clock, ("AAPL",)
        )
        context = RuntimeContext(
            EARNINGS_CALENDAR_CONTRACT, "AAPL", clock, "run-1", access["AAPL"].fulfillment
        )

        result = earnings_calendar_adapter(context)

        assert result.strategy_id == "earnings_calendar"
        assert result.evaluation_state is not EvaluationState.PASS
        assert result.evaluation_state is not EvaluationState.NO_SIGNAL
        assert result.opportunity_id is None
        assert result.lifecycle_stage is None
        assert "sandbox-secret-token" not in str(result)
        assert "sandbox-secret-key" not in str(result)
