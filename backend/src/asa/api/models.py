from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from asa.domain.market import MarketObservation


class IngestQuotesRequest(BaseModel):
    symbols: set[str] = Field(min_length=1)


class ProvenanceResponse(BaseModel):
    selected_provider: str
    original_provider: str
    cache_status: str
    freshness_status: str
    fallback_reason: str | None
    provider_request_id: str


class QuoteResponse(BaseModel):
    symbol: str
    price: Decimal
    currency: str
    observed_at: datetime
    received_at: datetime
    provenance: ProvenanceResponse

    @classmethod
    def from_domain(cls, observation: MarketObservation) -> "QuoteResponse":
        provenance = observation.provenance
        return cls(
            symbol=observation.symbol,
            price=observation.price,
            currency=observation.currency,
            observed_at=observation.observed_at,
            received_at=observation.received_at,
            provenance=ProvenanceResponse(
                selected_provider=provenance.selected_provider,
                original_provider=provenance.original_provider,
                cache_status=provenance.cache_status.value,
                freshness_status=provenance.freshness_status.value,
                fallback_reason=provenance.fallback_reason,
                provider_request_id=provenance.provider_request_id,
            ),
        )


class IngestQuotesResponse(BaseModel):
    observations: list[QuoteResponse]


class HealthResponse(BaseModel):
    status: str
