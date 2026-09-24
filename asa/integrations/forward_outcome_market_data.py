"""Forward-outcome evidence through the one shared market-data authority (OI-03).

Per the Architect decision: the collector never reuses the screening subject
plan or strategy demands. Each subject gets its own ``SubjectAcquisitionPlan``
(``outcome-collection:`` namespace) over ``build_shared_market_data_access``,
so provider registry, budgets, rolling windows, and attempt recording remain
the single shared authority. Requests are narrow and direct: the underlying
quote plus one chain request per frozen-leg expiration. Brokers are never
called.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from asa.application.ports.forward_outcomes import OutcomeEvidence
from domain import MarketCapability, OptionChain, Quote
from market_data import MarketDataConfig
from market_data.attempts import AcquisitionAttemptRepository
from market_data.fulfillment import CapabilityFulfillmentResult
from market_data.providers import CapabilityRequest
from screening.live_context import build_capability_subject
from strategy_runtime.forward_outcome import LegQuote
from strategy_runtime.market_data_planning import build_shared_market_data_access
from strategy_runtime.orchestration import build_subject_acquisition_access

_QUOTE_FIELDS = ("last",)
_CHAIN_FIELDS = ("contracts",)
_MAXIMUM_AGE_SECONDS = 3600


@dataclass(frozen=True, slots=True)
class _FixedClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


def _request(
    symbol: str,
    capability: MarketCapability,
    fields: tuple[str, ...],
    now: datetime,
    expiration: date | None = None,
) -> CapabilityRequest:
    subject = build_capability_subject(
        symbol, capability, now, required_fields=fields, expiration=expiration
    )
    return CapabilityRequest(capability, (subject,), now, now, fields, _MAXIMUM_AGE_SECONDS)


def _spot(quote: Quote) -> Decimal | None:
    if quote.last is not None:
        return quote.last
    if quote.bid is not None and quote.ask is not None:
        return (quote.bid + quote.ask) / Decimal(2)
    return None


class MarketDataOutcomeEvidenceSource:
    def __init__(
        self,
        config: MarketDataConfig,
        transport_factory: Callable[[str], object],
        attempt_repository: AcquisitionAttemptRepository,
    ) -> None:
        self._config = config
        self._transport_factory = transport_factory
        self._attempt_repository = attempt_repository

    def collect(self, symbol: str, expirations: tuple[date, ...], now: datetime) -> OutcomeEvidence:
        clock = _FixedClock(now)
        access = build_shared_market_data_access(
            self._config, self._transport_factory, clock, (symbol,)
        )[symbol]
        plan = build_subject_acquisition_access(
            symbol,
            access.fulfillment,
            attempt_repository=self._attempt_repository,
            plan_id=f"outcome-collection:{symbol}:{now.isoformat()}",
            clock=clock,
        ).plan
        unknown: list[str] = []
        provenance: list[str] = []
        price: Decimal | None = None
        quote_at: datetime | None = None
        quote_result = plan.resolve(
            _request(symbol, MarketCapability.REAL_TIME_QUOTE_V1, _QUOTE_FIELDS, now)
        )
        quote_obs = _first(quote_result)
        if quote_obs is not None and isinstance(quote_obs.value, Quote):
            price = _spot(quote_obs.value)
            quote_at = quote_obs.effective_time
            provenance.append(f"observation:{quote_obs.observation_id}")
        if price is None:
            unknown.append("underlying_quote_unavailable")
        leg_quotes: dict[str, LegQuote] = {}
        chain_times: list[datetime] = []
        for expiration in expirations:
            chain_result = plan.resolve(
                _request(
                    symbol,
                    MarketCapability.OPTION_CHAIN_V1,
                    _CHAIN_FIELDS,
                    now,
                    expiration=expiration,
                )
            )
            chain_obs = _first(chain_result)
            if chain_obs is None or not isinstance(chain_obs.value, OptionChain):
                unknown.append(f"option_chain_unavailable:{expiration.isoformat()}")
                continue
            chain_times.append(chain_obs.effective_time)
            provenance.append(f"observation:{chain_obs.observation_id}")
            for contract in chain_obs.value.contracts:
                leg_quotes[contract.identity] = LegQuote(contract.bid, contract.ask)
        # The oldest chain evidence is the conservative eligibility time: if it
        # is inside the window, every chain used is.
        return OutcomeEvidence(
            underlying_price=price,
            underlying_observed_at=quote_at,
            leg_quotes=leg_quotes,
            chain_observed_at=(
                min(chain_times) if chain_times and len(chain_times) == len(expirations) else None
            ),
            provenance=tuple(provenance),
            unknown_reasons=tuple(unknown),
        )


def _first(result: CapabilityFulfillmentResult):  # type: ignore[no-untyped-def]
    return result.observations[0] if result.observations else None
