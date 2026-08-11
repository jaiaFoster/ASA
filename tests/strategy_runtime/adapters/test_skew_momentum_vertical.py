"""SPRINT-009/EPIC-7: Skew Momentum Vertical migrated onto the universal
runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest

from market_data import load_market_data_config
from market_data.transport import ReadOnlyHttpResponse
from screening.live_acquisition import live_only_config
from strategy_runtime.adapters.skew_momentum_vertical import (
    SKEW_MOMENTUM_VERTICAL_CONTRACT,
    build_skew_momentum_adapter,
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


# (strike offset from the 190 ATM strike, call delta) -- put delta is the
# standard put_delta = call_delta - 1 relationship (matching
# tests/screening/test_live_adapters.py's own _STRIKE_DELTA_LADDER).
# SkewMomentumResearchDecision needs both an ATM contract and a ~0.25-delta
# wing contract on each side, so a single-strike chain (the original
# fixture here) can never complete the real acquisition -- it only
# appeared to pass before because deterministic_fixture (alphabetically
# first, always enabled) silently answered every request instead of this
# scripted Tradier transport, until live_only_config() below forced it out.
_STRIKE_DELTA_LADDER = (
    (-15, "0.80"),
    (-10, "0.70"),
    (-5, "0.60"),
    (0, "0.50"),
    (5, "0.35"),
    (10, "0.25"),
    (15, "0.15"),
)


def _option_row(strike: int, expiration: str, option_type: str, call_delta: str) -> dict:
    delta = call_delta if option_type == "call" else str(round(float(call_delta) - 1, 2))
    return {
        "symbol": f"AAPL_TEST_{option_type.upper()}_{strike}",
        "underlying": "AAPL",
        "expiration_date": expiration,
        "strike": str(strike),
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
            "rho": "0.01",
            "mid_iv": "0.30",
        },
    }


def _history_response() -> ReadOnlyHttpResponse:
    # Skew Momentum's realized-volatility input needs ~30 trading days
    # (screening/live_adapters.py requests a bounded 180-calendar-day
    # horizon), ending recently enough to satisfy the freshness requirement --
    # ending 15+ days ago (an earlier draft's mistake) reads as STALE_DATA.
    days = []
    cursor = date.today() - timedelta(days=1)
    price = 189.0
    while len(days) < 32:
        if cursor.weekday() < 5:
            days.append(
                {
                    "date": cursor.isoformat(),
                    "open": str(price - 0.5),
                    "high": str(price + 1),
                    "low": str(price - 1),
                    "close": str(price),
                    "volume": "1000000",
                }
            )
            price -= 0.1
        cursor -= timedelta(days=1)
    days.reverse()
    return ReadOnlyHttpResponse(200, {"history": {"day": days}}, (), 12, "tradier-request-4")


def _chain_responses(expiration: str) -> list[ReadOnlyHttpResponse]:
    options = [
        _option_row(190 + offset, expiration, option_type, call_delta)
        for offset, call_delta in _STRIKE_DELTA_LADDER
        for option_type in ("call", "put")
    ]
    return [
        tradier_quote_response(),
        ReadOnlyHttpResponse(
            200, {"expirations": {"date": [expiration]}}, (), 12, "tradier-request-2"
        ),
        ReadOnlyHttpResponse(200, {"options": {"option": options}}, (), 12, "tradier-request-3"),
        _history_response(),
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
    def test_full_live_acquisition_produces_a_translated_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
        monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
        clock = _FixedClock(datetime.now(UTC))
        expiration = (date.today() + timedelta(days=7)).isoformat()
        responses = _chain_responses(expiration)

        # live_only_config() force-disables deterministic_fixture -- it
        # defaults to enabled and, being alphabetically first, would
        # otherwise be tried before tradier by CapabilityRegistry's
        # deterministic priority order and silently answer every request
        # from offline fixture data instead of this test's own scripted
        # Tradier-shaped responses (screening/live_acquisition.py's own
        # documented rationale for this exact failure mode).
        config = live_only_config(
            load_market_data_config(
                {
                    "ASA_TRADIER_ENABLED": "true",
                    "ASA_TRADIER_ACCESS_TOKEN": "sandbox-secret-token",
                }
            )
        )
        access = build_shared_market_data_access(
            config, lambda _provider_id: ScriptedTransport(responses), clock, ("AAPL",)
        )
        # SPRINT-014 S14-PR-05A (Architect checkpoint: twelfth review, item
        # 3): acquisition is bound by closure, not carried on RuntimeContext.
        context = RuntimeContext(SKEW_MOMENTUM_VERTICAL_CONTRACT, "AAPL", clock, "run-1")
        adapter = build_skew_momentum_adapter(access["AAPL"].fulfillment)

        result = adapter(context)

        assert result.strategy_id == "skew_momentum"
        assert result.symbol == "AAPL"
        assert result.evaluation_state is not EvaluationState.ADAPTER_EXCEPTION
        assert result.opportunity_id is None
        assert result.lifecycle_stage is None
        assert "sandbox-secret-token" not in str(result)
