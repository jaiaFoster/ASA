from datetime import UTC, datetime
from decimal import Decimal

from analytics.cross_sectional_materialization import (
    CrossSectionalFactInputs,
    materialize_cross_sectional_facts,
)
from analytics.derived_facts import CROSS_SECTIONAL_MOMENTUM, SECTOR_RELATIVE_MOMENTUM
from domain import (
    CanonicalInstrumentIdentity,
    CanonicalReturnObservation,
    EvidenceKind,
    EvidenceReference,
    SectorClassification,
    SecurityAssetType,
)
from strategy_runtime.comparison_universe import (
    select_comparison_universe_returns,
    select_sector_reference_returns,
)

START = datetime(2026, 7, 1, tzinfo=UTC)
END = datetime(2026, 8, 1, tzinfo=UTC)


def _instrument(symbol: str) -> CanonicalInstrumentIdentity:
    return CanonicalInstrumentIdentity("symbol", symbol)


def _return(symbol: str, value: str) -> CanonicalReturnObservation:
    return CanonicalReturnObservation(
        _instrument(symbol),
        Decimal(value),
        START,
        END,
        END,
        (EvidenceReference(EvidenceKind.CANONICAL_FACT, f"daily_closes:{symbol}", 1),),
    )


def _inputs() -> tuple[
    tuple[CanonicalReturnObservation, ...],
    dict[CanonicalInstrumentIdentity, SecurityAssetType],
    dict[CanonicalInstrumentIdentity, SectorClassification],
]:
    values = (
        _return("AAPL", "0.06"),
        _return("MSFT", "0.05"),
        _return("NVDA", "0.04"),
        _return("AMD", "0.03"),
        _return("AVGO", "0.02"),
        _return("MU", "0.01"),
        _return("XLK", "0.025"),
    )
    asset_types = {item.instrument: SecurityAssetType.EQUITY for item in values}
    asset_types[_instrument("XLK")] = SecurityAssetType.ETF
    sectors = {
        item.instrument: SectorClassification("GICS", "2023", "45")
        for item in values
        if item.instrument.value != "XLK"
    }
    return values, asset_types, sectors


def _selected(
    values: tuple[CanonicalReturnObservation, ...],
    asset_types: dict[CanonicalInstrumentIdentity, SecurityAssetType],
    sectors: dict[CanonicalInstrumentIdentity, SectorClassification],
) -> tuple[CrossSectionalFactInputs, ...]:
    return tuple(
        CrossSectionalFactInputs(
            item,
            select_comparison_universe_returns(
                item.instrument,
                (item.period_start, item.period_end),
                values,
                asset_types,
            ),
            select_sector_reference_returns(
                item.instrument,
                (item.period_start, item.period_end),
                sectors,
                values,
            ),
            "insufficient_comparison_cohort",
            "missing_sector_membership"
            if item.instrument not in sectors
            else "missing_sector_benchmark_return",
        )
        for item in values
    )


def test_materialization_is_deterministic_and_order_independent() -> None:
    values, asset_types, sectors = _inputs()
    first = materialize_cross_sectional_facts(
        _selected(values, asset_types, sectors), effective_time=END
    )
    second = materialize_cross_sectional_facts(
        _selected(tuple(reversed(values)), asset_types, sectors), effective_time=END
    )
    assert first == second
    aapl = next(item for item in first if item.subject == _instrument("AAPL"))
    assert aapl.comparison_peer_count == 5
    assert {fact.derived_fact_id.split(":", 1)[0] for fact in aapl.derived_facts.facts} == {
        CROSS_SECTIONAL_MOMENTUM,
        SECTOR_RELATIVE_MOMENTUM,
    }
    assert all(len(fact.input_evidence) >= 2 for fact in aapl.derived_facts.facts)


def test_changed_member_value_changes_fact_identity() -> None:
    values, asset_types, sectors = _inputs()
    before = materialize_cross_sectional_facts(
        _selected(values, asset_types, sectors), effective_time=END
    )
    changed = tuple(
        _return("MSFT", "0.50") if item.instrument == _instrument("MSFT") else item
        for item in values
    )
    after = materialize_cross_sectional_facts(
        _selected(changed, asset_types, sectors), effective_time=END
    )
    before_fact = next(
        item for item in before if item.subject == _instrument("AAPL")
    ).derived_facts.facts[0]
    after_fact = next(
        item for item in after if item.subject == _instrument("AAPL")
    ).derived_facts.facts[0]
    assert before_fact.derived_fact_id != after_fact.derived_fact_id


def test_incomplete_cohort_and_missing_sector_are_typed() -> None:
    values, asset_types, _sectors = _inputs()
    result = materialize_cross_sectional_facts(
        _selected(values[:2], asset_types, {}), effective_time=END
    )
    assert all(
        item.comparison_unknown_reason == "insufficient_comparison_cohort" for item in result
    )
    assert all(item.sector_unknown_reason == "missing_sector_membership" for item in result)
    assert all(not item.derived_facts.facts for item in result)


def test_second_consumer_reuses_same_materialized_fact_instance() -> None:
    values, asset_types, sectors = _inputs()
    result = materialize_cross_sectional_facts(
        _selected(values, asset_types, sectors), effective_time=END
    )
    shared = next(item for item in result if item.subject == _instrument("AAPL")).derived_facts
    consumers = {"skew_momentum": shared, "synthetic_consumer": shared}
    assert consumers["skew_momentum"] is consumers["synthetic_consumer"]
