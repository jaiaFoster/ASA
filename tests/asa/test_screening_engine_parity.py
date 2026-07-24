"""SPRINT-009R/EPIC-R5: parity verification -- the legacy screening.service-
backed refresh path and the strategy_runtime-backed refresh path this
cutover now uses in production must translate to the identical public
wire response for identical inputs.

Both paths ultimately run the exact same unmodified screening execution
graph (screening.adapters.TARGET_STRATEGY_REGISTRY, via
strategy_runtime.adapters._screening_bridge.translate_screening_result())
against the same deterministic clock and the same scripted provider
responses, so any wire-response difference this test would catch could
only come from the translation layer -- ScreeningResultResponse.from_record()
(legacy) vs .from_universal_result() (this cutover) -- not from a change
in financial computation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from asa.api.screening_models import RefreshResultResponse
from market_data.config import load_market_data_config
from market_data.transport import ReadOnlyHttpResponse
from screening.adapters import TARGET_STRATEGY_REGISTRY
from screening.live_acquisition import build_fulfillment_service_with_accounting
from screening.service import refresh as legacy_refresh
from screening.state import ScreeningStateRecord
from strategy_runtime.adapters import build_migrated_strategy_registry
from strategy_runtime.market_data_planning import build_shared_market_data_access
from strategy_runtime.service import refresh as universal_refresh
from tests.asa.fakes import InMemoryLatestResultRepository, InMemoryScreeningStateRepository
from tests.asa.market_data_ops.fakes import ScriptedTransport, tradier_quote_response


@dataclass(frozen=True, slots=True)
class _FixedClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


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


def _config() -> object:
    return load_market_data_config(
        {"ASA_TRADIER_ENABLED": "true", "ASA_TRADIER_ACCESS_TOKEN": "sandbox-secret-token"}
    )


def test_legacy_and_strategy_runtime_refresh_produce_the_identical_wire_response() -> None:
    clock = _FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
    expiration = (date.today() + timedelta(days=7)).isoformat()

    # -- legacy path --
    legacy_fulfillment, legacy_budget = build_fulfillment_service_with_accounting(
        _config(),  # type: ignore[arg-type]
        lambda _provider_id: ScriptedTransport(_tradier_refresh_responses(expiration)),
        clock,
    )
    legacy_repository: InMemoryScreeningStateRepository = InMemoryScreeningStateRepository()
    legacy_record: ScreeningStateRecord = legacy_refresh(
        legacy_repository,
        TARGET_STRATEGY_REGISTRY,
        legacy_fulfillment,
        clock,
        signal_id="skew_momentum",
        symbol="AAPL",
    )
    legacy_response = RefreshResultResponse.from_record(
        legacy_record, request_count=len(legacy_budget.accounting)
    )

    # -- strategy_runtime path (this cutover) --
    access = build_shared_market_data_access(
        _config(),  # type: ignore[arg-type]
        lambda _provider_id: ScriptedTransport(_tradier_refresh_responses(expiration)),
        clock,
        ("AAPL",),
    )
    subject_access = access["AAPL"]
    universal_repository = InMemoryLatestResultRepository()
    universal_result = universal_refresh(
        build_migrated_strategy_registry(),
        universal_repository,
        clock,
        strategy_id="skew_momentum",
        symbol="AAPL",
        fulfillment_by_subject={"AAPL": subject_access.fulfillment},
    )
    universal_response = RefreshResultResponse.from_universal_result(
        universal_result, request_count=len(subject_access.budget_manager.accounting)
    )

    assert universal_response.model_dump() == legacy_response.model_dump()
