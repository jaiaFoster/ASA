"""Deterministic synthetic market-price provider (ASA-CORE-002).

Produces repeatable, normalized market_price Observations for tests —
no networking, credentials, retries, randomness, or external state, and
no repository writes.

Layering (ADR-004): ``providers/`` may depend only on ``providers`` and
``domain``, so this provider does not import the Observation Layer's
identity algorithm. The identity function is injected at construction
(dependency inversion); the composition point — typically a test — passes
``observation.observation_identity``. Given the same identity function and
the same input, the provider's output is fully repeatable.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Callable, Protocol

from domain.observation import Observation
from domain.provider import Provider

SYNTHETIC_PROVIDER = Provider(
    provider_id="synthetic-deterministic",
    name="Synthetic Deterministic Provider",
)

OBSERVATION_TYPE_MARKET_PRICE = "market_price"

# (provider_id, observation_type, effective_time, normalized value) -> identity
IdentityFunction = Callable[[str, str, datetime, object], str]


class DeterministicMarketPriceProvider:
    """Emits normalized market_price Observations with deterministic identity.

    The produced value is an immutable mapping in canonical (sorted-key)
    order: ``(("currency", ...), ("price", Decimal(...)), ("symbol", ...))``.
    The provider never writes to any repository — it only returns records.
    """

    def __init__(self, identity: IdentityFunction) -> None:
        self._identity = identity
        self.provider = SYNTHETIC_PROVIDER

    @property
    def provider_id(self) -> str:
        return self.provider.provider_id

    def market_price(
        self,
        *,
        symbol: str,
        price: Decimal | str,
        currency: str,
        effective_time: datetime,
        recorded_time: datetime,
    ) -> Observation:
        value = (
            ("currency", currency),
            ("price", Decimal(price)),
            ("symbol", symbol),
        )
        observation_id = self._identity(
            self.provider_id, OBSERVATION_TYPE_MARKET_PRICE, effective_time, value
        )
        return Observation(
            observation_id=observation_id,
            observation_type=OBSERVATION_TYPE_MARKET_PRICE,
            provider_id=self.provider_id,
            value=value,
            effective_time=effective_time,
            recorded_time=recorded_time,
        )
