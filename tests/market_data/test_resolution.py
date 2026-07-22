from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from domain import (
    FreshnessStatus,
    MarketObservation,
    ProviderProvenance,
    Quote,
    market_observation_identity,
)
from domain.values import DomainInvariantError
from market_data import (
    ConfidenceClassification,
    ObservationResolver,
    RequestBudgetAuthorization,
    ResolutionMethod,
    ResolutionPolicy,
)
from tests.market_data.test_fulfillment import provider, request

NOW = datetime(2026, 7, 21, 16, 0, tzinfo=timezone.utc)


def observation(provider_id: str) -> MarketObservation:
    return (
        provider(provider_id)
        .fetch(request(), RequestBudgetAuthorization("test", provider_id, 1, 1))
        .observations[0]
    )


def changed_price(source: MarketObservation, provider_id: str, price: str) -> MarketObservation:
    assert isinstance(source.value, Quote)
    value = dataclasses.replace(source.value, last=Decimal(price))
    provenance = ProviderProvenance(
        provider_id, f"{provider_id}-request", source.provenance.evidence
    )
    return dataclasses.replace(
        source,
        value=value,
        provenance=provenance,
        observation_id=market_observation_identity(
            provider_id,
            source.capability,
            source.subject,
            source.effective_time,
            value,
            source.schema_version,
        ),
    )


def policy(*providers: str) -> ResolutionPolicy:
    return ResolutionPolicy("v1", providers, 60, ("last",))


def test_single_observation_is_selected() -> None:
    item = observation("tradier")
    result = ObservationResolver().resolve((item,), policy("tradier"), as_of=NOW)
    assert result.method is ResolutionMethod.SINGLE_AVAILABLE
    assert result.selected_observation == item
    assert result.confidence.classification is ConfidenceClassification.SINGLE_SOURCE


def test_exact_agreement_selects_configured_priority_independent_of_input_order() -> None:
    tradier = observation("tradier")
    finnhub = changed_price(tradier, "finnhub", str(tradier.value.last))  # type: ignore[union-attr]
    resolver = ObservationResolver()
    first = resolver.resolve((finnhub, tradier), policy("tradier", "finnhub"), as_of=NOW)
    second = resolver.resolve((tradier, finnhub), policy("tradier", "finnhub"), as_of=NOW)
    assert first == second
    assert first.method is ResolutionMethod.EXACT_AGREEMENT
    assert first.selected_observation == tradier
    assert first.disagreements == ()


def test_disagreement_is_field_level_and_priority_selects_reported_value() -> None:
    tradier = observation("tradier")
    finnhub = changed_price(tradier, "finnhub", "999.25")
    result = ObservationResolver().resolve(
        (finnhub, tradier), policy("tradier", "finnhub"), as_of=NOW
    )
    assert result.method is ResolutionMethod.PROVIDER_PRIORITY
    assert result.selected_observation == tradier
    assert any(".last" in item.field_path for item in result.disagreements)
    assert result.confidence.classification is ConfidenceClassification.DISAGREEMENT
    assert result.contributors == ("finnhub", "tradier")


def test_stale_highest_priority_remains_unresolved_without_hidden_fallback() -> None:
    tradier = observation("tradier")
    stale_freshness = dataclasses.replace(
        tradier.freshness,
        as_of=NOW + timedelta(seconds=120),
        age_seconds=120,
        status=FreshnessStatus.STALE,
    )
    stale = dataclasses.replace(tradier, freshness=stale_freshness)
    finnhub = changed_price(tradier, "finnhub", "999.25")
    result = ObservationResolver().resolve(
        (stale, finnhub), policy("tradier", "finnhub"), as_of=NOW + timedelta(seconds=120)
    )
    assert result.method is ResolutionMethod.UNRESOLVED
    assert result.selected_observation is None
    assert result.confidence.classification is ConfidenceClassification.INSUFFICIENT_QUALITY


def test_resolution_rejects_mixed_subjects_and_duplicate_provider_values() -> None:
    item = observation("tradier")
    with pytest.raises(DomainInvariantError, match="one value per provider"):
        ObservationResolver().resolve((item, item), policy("tradier"), as_of=NOW)
