"""SPRINT-009/EPIC-7: Forward Factor migrated onto the universal runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest

from domain import MarketCapability
from market_data import load_market_data_config
from market_data.transport import ReadOnlyHttpResponse
from strategy_runtime.adapters.forward_factor import FORWARD_FACTOR_CONTRACT, forward_factor_adapter
from strategy_runtime.context import RuntimeContext
from strategy_runtime.contract import LifecycleModel
from strategy_runtime.market_data_planning import build_shared_market_data_access
from strategy_runtime.result import EvaluationState
from tests.asa.market_data_ops.fakes import ScriptedTransport, tradier_quote_response


@dataclass
class _FixedClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


def _option(expiration: str, strike: str) -> dict[str, object]:
    return {
        "symbol": f"AAPL_TEST_{expiration}_{strike}",
        "underlying": "AAPL",
        "expiration_date": expiration,
        "strike": strike,
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


def _forward_factor_responses(front: str, back: str) -> list[ReadOnlyHttpResponse]:
    return [
        tradier_quote_response(),
        ReadOnlyHttpResponse(
            200, {"expirations": {"date": [front, back]}}, (), 12, "tradier-request-2"
        ),
        ReadOnlyHttpResponse(
            200, {"options": {"option": [_option(front, "190")]}}, (), 12, "tradier-request-3"
        ),
        ReadOnlyHttpResponse(
            200, {"options": {"option": [_option(back, "190")]}}, (), 12, "tradier-request-4"
        ),
    ]


class TestForwardFactorContract:
    def test_contract_declares_no_lifecycle(self) -> None:
        assert FORWARD_FACTOR_CONTRACT.lifecycle.lifecycle_model is LifecycleModel.NONE

    def test_contract_requires_quote_and_option_chain(self) -> None:
        capabilities = FORWARD_FACTOR_CONTRACT.required_capabilities()
        assert MarketCapability.REAL_TIME_QUOTE_V1 in capabilities
        assert MarketCapability.OPTION_CHAIN_V1 in capabilities


class TestForwardFactorAdapter:
    def test_requires_shared_fulfillment(self) -> None:
        context = RuntimeContext(
            FORWARD_FACTOR_CONTRACT, "AAPL", _FixedClock(datetime.now(UTC)), "run-1"
        )
        with pytest.raises(RuntimeError, match="requires shared market data access"):
            forward_factor_adapter(context)

    def test_full_live_acquisition_produces_a_translated_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
        monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
        clock = _FixedClock(datetime.now(UTC))
        # Front ~60 DTE, back ~90 DTE -- both within FORWARD_FACTOR_DTE_POLICY's
        # own windows (screening/context_builders.py), gap 30 days matching
        # its own target_gap_days exactly.
        front = (date.today() + timedelta(days=60)).isoformat()
        back = (date.today() + timedelta(days=90)).isoformat()
        responses = _forward_factor_responses(front, back)

        config = load_market_data_config(
            {"ASA_TRADIER_ENABLED": "true", "ASA_TRADIER_ACCESS_TOKEN": "sandbox-secret-token"}
        )
        access = build_shared_market_data_access(
            config, lambda _provider_id: ScriptedTransport(responses), clock, ("AAPL",)
        )
        context = RuntimeContext(
            FORWARD_FACTOR_CONTRACT, "AAPL", clock, "run-1", access["AAPL"].fulfillment
        )

        result = forward_factor_adapter(context)

        assert result.strategy_id == "forward_factor"
        assert result.symbol == "AAPL"
        assert result.evaluation_state is not EvaluationState.ADAPTER_EXCEPTION
        assert result.opportunity_id is None
        assert result.lifecycle_stage is None
        assert "sandbox-secret-token" not in str(result)
