from datetime import UTC
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import RowMapping

from asa.domain.market import CacheStatus, FreshnessStatus, MarketObservation, QuoteProvenance


class PostgresMarketObservationRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save_quote_observation(self, observation: MarketObservation) -> None:
        statement = text("""
            INSERT INTO market_observations (
                symbol, price, currency, observed_at, received_at,
                selected_provider, original_provider, cache_status,
                freshness_status, fallback_reason, provider_request_id
            ) VALUES (
                :symbol, :price, :currency, :observed_at, :received_at,
                :selected_provider, :original_provider, :cache_status,
                :freshness_status, :fallback_reason, :provider_request_id
            )
        """)
        values: dict[str, Any] = {
            "symbol": observation.symbol,
            "price": observation.price,
            "currency": observation.currency,
            "observed_at": observation.observed_at,
            "received_at": observation.received_at,
            "selected_provider": observation.provenance.selected_provider,
            "original_provider": observation.provenance.original_provider,
            "cache_status": observation.provenance.cache_status.value,
            "freshness_status": observation.provenance.freshness_status.value,
            "fallback_reason": observation.provenance.fallback_reason,
            "provider_request_id": observation.provenance.provider_request_id,
        }
        with self._engine.begin() as connection:
            connection.execute(statement, values)

    def latest_quote(self, symbol: str) -> MarketObservation | None:
        statement = text("""
            SELECT symbol, price, currency, observed_at, received_at,
                   selected_provider, original_provider, cache_status,
                   freshness_status, fallback_reason, provider_request_id
            FROM market_observations
            WHERE symbol = :symbol
            ORDER BY observed_at DESC, id DESC
            LIMIT 1
        """)
        with self._engine.connect() as connection:
            row = connection.execute(statement, {"symbol": symbol}).mappings().first()
        return None if row is None else self._to_observation(row)

    def check_health(self) -> bool:
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    @staticmethod
    def _to_observation(row: RowMapping) -> MarketObservation:
        return MarketObservation(
            symbol=str(row["symbol"]),
            price=Decimal(str(row["price"])),
            currency=str(row["currency"]),
            observed_at=row["observed_at"].astimezone(UTC),
            received_at=row["received_at"].astimezone(UTC),
            provenance=QuoteProvenance(
                selected_provider=str(row["selected_provider"]),
                original_provider=str(row["original_provider"]),
                cache_status=CacheStatus(str(row["cache_status"])),
                freshness_status=FreshnessStatus(str(row["freshness_status"])),
                fallback_reason=row["fallback_reason"],
                provider_request_id=str(row["provider_request_id"]),
            ),
        )


def create_postgres_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)
