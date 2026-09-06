from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from domain import (
    AdjustedCloseBasis,
    CanonicalFact,
    CanonicalInstrumentIdentity,
    Confidence,
    Instrument,
    InstrumentKind,
    OHLCVBar,
    Provenance,
    UnknownReason,
)
from facts.canonical_projection import canonical_fact_id
from strategies.stock_benchmark_knowledge import (
    B001Payload,
    B002Payload,
    build_b001_knowledge_mapping,
    build_b002_knowledge_mapping,
)

NOW = datetime(2026, 9, 5, 15, 0, tzinfo=UTC)
_INSTRUMENT = Instrument(
    CanonicalInstrumentIdentity("figi", "figi-SPY"), InstrumentKind.EQUITY, "SPY", "USD"
)


def _fact(fact_id: str, fact_type: str, value: object) -> CanonicalFact:
    return CanonicalFact(
        fact_id,
        1,
        fact_type,
        value,
        Confidence(1.0),
        Provenance(("observation",), ("provider",), "provider", (), NOW),
        NOW,
        NOW,
    )


def _month_end_bar(months_back: int, *, adjusted_close: Decimal | None) -> OHLCVBar:
    total_months = NOW.year * 12 + (NOW.month - 1) - months_back
    year, month = divmod(total_months, 12)
    end_at = datetime(year, month + 1, 15, 12, 0, tzinfo=UTC)
    start_at = end_at - timedelta(days=1)
    close = Decimal("400") + Decimal(months_back)
    basis = AdjustedCloseBasis.SPLIT_ADJUSTED if adjusted_close is not None else None
    return OHLCVBar(
        _INSTRUMENT,
        86400,
        start_at,
        end_at,
        close,
        close + Decimal("2"),
        close - Decimal("2"),
        close,
        Decimal("1000000"),
        adjusted_close,
        basis,
    )


def _ten_completed_months() -> tuple[OHLCVBar, ...]:
    return tuple(
        _month_end_bar(months_back, adjusted_close=Decimal("400") + months_back)
        for months_back in range(1, 11)
    )


class TestB001KnowledgeMapping:
    def test_payload_carries_the_projected_price(self) -> None:
        digest = "snapshot-digest"
        mapping = build_b001_knowledge_mapping(
            subject="SPY", quote_observation_id="quote-1", price=Decimal("560.25")
        )
        (request,) = mapping.canonical_fact_requests
        fact = _fact(
            canonical_fact_id(request.fact_type, request.subject, digest),
            request.fact_type,
            request.value,
        )

        derived_requests = mapping.compute_derived_fact_requests((fact,))
        assert derived_requests == ()

        from analytics.features import DerivedFactSet

        payload = mapping.build_payload((fact,), DerivedFactSet(()))
        assert payload == B001Payload(Decimal("560.25"))


class TestB002KnowledgeMapping:
    def _facts(self, digest: str, bars: tuple[OHLCVBar, ...], price: Decimal = Decimal("560.25")):
        mapping = build_b002_knowledge_mapping(
            subject="SPY",
            snapshot_digest=digest,
            quote_observation_id="quote-1",
            price=price,
            bars_observation_id="bars-1",
            bars=bars,
            as_of=NOW,
        )
        facts = tuple(
            _fact(
                canonical_fact_id(request.fact_type, request.subject, digest),
                request.fact_type,
                request.value,
            )
            for request in mapping.canonical_fact_requests
        )
        return mapping, facts

    def test_sufficient_history_materializes_sma_and_builds_payload(self) -> None:
        digest = "snapshot-digest"
        mapping, facts = self._facts(digest, _ten_completed_months())

        derived_requests = mapping.compute_derived_fact_requests(facts)
        assert not isinstance(derived_requests, UnknownReason)
        assert len(derived_requests) == 1

        from analytics.derived_fact_materialization import materialize_derived_fact
        from analytics.derived_facts import DERIVED_FACT_REGISTRY
        from analytics.features import DerivedFactSet

        (request,) = derived_requests
        derived = DerivedFactSet(
            (
                materialize_derived_fact(
                    DERIVED_FACT_REGISTRY,
                    request.feature_id,
                    request.subject,
                    digest,
                    value=request.value,
                    unit=request.unit,
                    effective_time=NOW,
                    input_evidence=request.input_evidence,
                    quality_status=request.quality_status,
                    parameters=request.parameters,
                ),
            )
        )
        payload = mapping.build_payload(facts, derived)
        assert isinstance(payload, B002Payload)
        assert payload.price == Decimal("560.25")
        # Mean of 401..410 == 405.5
        assert payload.sma_10m == Decimal("405.5")

    def test_insufficient_history_is_a_typed_unknown_not_a_raw_close_fallback(self) -> None:
        digest = "snapshot-digest"
        nine_months = tuple(
            _month_end_bar(months_back, adjusted_close=Decimal("400") + months_back)
            for months_back in range(1, 10)
        )
        mapping, facts = self._facts(digest, nine_months)

        result = mapping.compute_derived_fact_requests(facts)

        assert result == UnknownReason("insufficient_adjusted_history")

    def test_missing_adjusted_close_is_a_typed_unknown(self) -> None:
        digest = "snapshot-digest"
        bars = tuple(
            _month_end_bar(months_back, adjusted_close=None) for months_back in range(1, 11)
        )
        mapping, facts = self._facts(digest, bars)

        result = mapping.compute_derived_fact_requests(facts)

        assert result == UnknownReason("insufficient_adjusted_history")
