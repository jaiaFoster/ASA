"""SPRINT-009/EPIC-7: Skew Momentum Vertical migrated onto the universal
runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest

from market_data import load_market_data_config
from market_data.transport import ReadOnlyHttpResponse
from strategy_runtime.adapters.skew_momentum_vertical import (
    SKEW_MOMENTUM_VERTICAL_CONTRACT,
    skew_momentum_adapter,
)
from strategy_runtime.context import RuntimeContext
from strategy_runtime.market_data_planning import build_shared_market_data_access
from strategy_runtime.result import EvaluationState
from tests.asa.market_data_ops.fakes import ScriptedTransport, tradier_quote_response


@dataclass
class _FixedClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


def _chain_responses(expiration: str) -> list[ReadOnlyHttpResponse]:
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


class TestSkewMomentumVerticalContract:
    def test_contract_declares_no_lifecycle(self) -> None:
        from strategy_runtime.contract import LifecycleModel

        assert SKEW_MOMENTUM_VERTICAL_CONTRACT.lifecycle.lifecycle_model is LifecycleModel.NONE

    def test_contract_requires_quote_and_option_chain(self) -> None:
        from domain import MarketCapability

        capabilities = SKEW_MOMENTUM_VERTICAL_CONTRACT.required_capabilities()
        assert MarketCapability.REAL_TIME_QUOTE_V1 in capabilities
        assert MarketCapability.OPTION_CHAIN_V1 in capabilities


class TestSkewMomentumAdapter:
    def test_requires_shared_fulfillment(self) -> None:
        context = RuntimeContext(
            SKEW_MOMENTUM_VERTICAL_CONTRACT, "AAPL", _FixedClock(datetime.now(UTC)), "run-1"
        )
        with pytest.raises(RuntimeError, match="requires shared market data access"):
            skew_momentum_adapter(context)

    def test_full_live_acquisition_produces_a_translated_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
        monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
        clock = _FixedClock(datetime.now(UTC))
        expiration = (date.today() + timedelta(days=7)).isoformat()
        responses = _chain_responses(expiration)

        config = load_market_data_config(
            {"ASA_TRADIER_ENABLED": "true", "ASA_TRADIER_ACCESS_TOKEN": "sandbox-secret-token"}
        )
        access = build_shared_market_data_access(
            config, lambda _provider_id: ScriptedTransport(responses), clock, ("AAPL",)
        )
        context = RuntimeContext(
            SKEW_MOMENTUM_VERTICAL_CONTRACT,
            "AAPL",
            clock,
            "run-1",
            access["AAPL"].fulfillment,
        )

        result = skew_momentum_adapter(context)

        assert result.strategy_id == "skew_momentum"
        assert result.symbol == "AAPL"
        assert result.evaluation_state is not EvaluationState.ADAPTER_EXCEPTION
        assert result.opportunity_id is None
        assert result.lifecycle_stage is None
        assert "sandbox-secret-token" not in str(result)
