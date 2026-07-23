from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum


class CacheStatus(StrEnum):
    MISS = "miss"
    PERSISTED = "persisted"


class FreshnessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class QuoteProvenance:
    selected_provider: str
    original_provider: str
    cache_status: CacheStatus
    freshness_status: FreshnessStatus
    fallback_reason: str | None
    provider_request_id: str


@dataclass(frozen=True, slots=True)
class MarketObservation:
    symbol: str
    price: Decimal
    currency: str
    observed_at: datetime
    received_at: datetime
    provenance: QuoteProvenance

    def with_current_freshness(self, now: datetime, fresh_for: timedelta) -> "MarketObservation":
        freshness = (
            FreshnessStatus.FRESH
            if self.observed_at >= now.astimezone(UTC) - fresh_for
            else FreshnessStatus.STALE
        )
        return replace(
            self,
            provenance=replace(self.provenance, freshness_status=freshness),
        )
