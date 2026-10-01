from calendar import monthcalendar
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

from analytics.features import DerivedFactSet
from domain import (
    CanonicalInstrumentIdentity,
    HistoricalOptionPanel,
    HistoricalOptionSnapshot,
    MarketCapability,
    MarketDataSubjectType,
    OptionType,
    UnknownReason,
)
from screening.live_context import build_capability_subject
from strategies.heston_knowledge import formation_from_panel
from strategies.heston_manifest import HESTON_MANIFEST, STRATEGY_ID
from strategies.heston_planning import historical_panel_demand
from strategies.heston_portfolio import HestonSubjectCandidate
from strategies.manifest_version_pins import version_pin_violations
from strategy_runtime.adapters.heston import HESTON_CONTRACT
from strategy_runtime.adapters.heston_portfolio import (
    HestonSubjectMaterialization,
    materialize_heston_family,
)
from strategy_runtime.adapters.heston_subject_first import build_heston_subject_first_adapter
from strategy_runtime.context import RuntimeContext
from strategy_runtime.cross_sectional_portfolio import PortfolioBookSide
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.manifest_contract import validate_manifest_contract
from tests.strategies.test_cboe_put_strategy import _put

AS_OF = datetime(2026, 10, 16, 21, tzinfo=UTC)
EXPIRY = date(2026, 11, 20)


def test_historical_panel_is_optional_and_uses_option_underlying_subject() -> None:
    demand = historical_panel_demand(AS_OF)
    assert demand.required is False
    subject = build_capability_subject("AAPL", MarketCapability.HISTORICAL_OPTION_PANEL_V1, AS_OF)
    assert subject.subject_type is MarketDataSubjectType.OPTION_UNDERLYING


def _candidate(index: int) -> HestonSubjectCandidate:
    put = replace(
        _put("100"),
        option_contract_id=CanonicalInstrumentIdentity("occ", f"H{index}-P"),
        expiration=EXPIRY,
        bid=Decimal("1.00"),
        ask=Decimal("1.05"),
        delta=Decimal("-0.5"),
        open_interest=10,
        root=None,
        settlement_style=None,
    )
    call = replace(
        put,
        option_contract_id=CanonicalInstrumentIdentity("occ", f"H{index}-C"),
        option_type=OptionType.CALL,
        delta=Decimal("0.5"),
    )
    return HestonSubjectCandidate(
        f"H{index}",
        AS_OF,
        f"evidence:{index}",
        (call, put),
        EXPIRY,
        Decimal(index),
        "PASS",
    )


def test_manifest_contract_and_assumption_pin_are_complete() -> None:
    assert HESTON_CONTRACT.strategy_id == STRATEGY_ID
    validate_manifest_contract(HESTON_MANIFEST, HESTON_CONTRACT)
    assert version_pin_violations((HESTON_MANIFEST,)) == ()
    assert {item.assumption_id for item in HESTON_MANIFEST.assumptions} == {
        "RA-XS-01",
        "RA-XR-03",
    }


def test_heston_family_reuses_p03_and_p12_with_separate_equal_weight_books() -> None:
    result = materialize_heston_family({f"H{i}": _candidate(i) for i in range(10)})
    passing = [
        item
        for item in result.values()
        if isinstance(item, HestonSubjectMaterialization) and item.state == "PASS"
    ]
    assert len(passing) == 2
    assert {item.quantile for item in passing} == {1, 10}
    portfolio = next(item.portfolio for item in passing if item.portfolio is not None)
    assert portfolio is not None
    assert {item.side for item in portfolio.members} == {
        PortfolioBookSide.LONG,
        PortfolioBookSide.SHORT,
    }
    assert all(item.weight == Decimal(1) for item in portfolio.members)
    assert all(item.position is not None for item in passing)


def test_ra_xr_03_excludes_failed_closest_pair_without_replacement() -> None:
    candidate = _candidate(0)
    call, put = candidate.contracts
    failed_call = replace(call, bid=Decimal("0.5"), ask=Decimal("1.5"))
    failed_put = replace(put, bid=Decimal("0.5"), ask=Decimal("1.5"))
    farther_call = replace(
        call,
        option_contract_id=CanonicalInstrumentIdentity("occ", "far-C"),
        strike=Decimal(105),
        delta=Decimal("0.4"),
    )
    farther_put = replace(
        put,
        option_contract_id=CanonicalInstrumentIdentity("occ", "far-P"),
        strike=Decimal(105),
        delta=Decimal("-0.6"),
    )
    result = materialize_heston_family(
        {"H0": replace(candidate, contracts=(failed_call, failed_put, farther_call, farther_put))}
    )
    assert result["H0"] == HestonSubjectMaterialization("EXCLUDED", "G_HES_LOWCOST_PAIR_FAIL")


def test_insufficient_history_is_typed_unknown() -> None:
    candidate = replace(
        _candidate(0), formation_momentum=UnknownReason("insufficient_straddle_return_history")
    )
    result = materialize_heston_family({"H0": candidate})
    assert result["H0"] == HestonSubjectMaterialization(
        "UNKNOWN", "insufficient_straddle_return_history"
    )


def _third_friday(year: int, month: int) -> date:
    fridays = [week[4] for week in monthcalendar(year, month) if week[4]]
    return date(year, month, fridays[2])


def test_historical_panel_materializes_complete_lags_two_through_twelve() -> None:
    snapshots = []
    prior_entry = None
    for month in range(1, 13):
        observed_date = _third_friday(2025, month)
        observed_at = datetime.combine(observed_date, datetime.min.time(), tzinfo=UTC)
        following_year = 2025 + (month == 12)
        following_month = month % 12 + 1
        expiration = _third_friday(following_year, following_month)
        template = _candidate(month).contracts
        call = replace(
            template[0],
            option_contract_id=CanonicalInstrumentIdentity("occ", f"M{month}-C"),
            expiration=expiration,
            observed_at=observed_at,
            bid=Decimal("1"),
            ask=Decimal("1"),
        )
        put = replace(
            template[1],
            option_contract_id=CanonicalInstrumentIdentity("occ", f"M{month}-P"),
            expiration=expiration,
            observed_at=observed_at,
            bid=Decimal("1"),
            ask=Decimal("1"),
        )
        contracts = [call, put]
        if prior_entry is not None:
            contracts.extend(
                replace(item, observed_at=observed_at, bid=Decimal("1.1"), ask=Decimal("1.1"))
                for item in prior_entry
            )
        snapshots.append(
            HistoricalOptionSnapshot(
                call.underlying.instrument,
                observed_at,
                observed_at,
                f"snapshot-{month}",
                tuple(contracts),
            )
        )
        prior_entry = (call, put)
    panel = HistoricalOptionPanel(
        snapshots[0].subject,
        snapshots[-1].observed_at,
        tuple(snapshots),
    )
    assert formation_from_panel(panel) == Decimal("0.1")


def test_subject_first_adapter_replays_without_acquisition() -> None:
    materialized = materialize_heston_family({f"H{i}": _candidate(i) for i in range(10)})
    subject, payload = next(
        (key, value)
        for key, value in materialized.items()
        if isinstance(value, HestonSubjectMaterialization) and value.state == "PASS"
    )
    knowledge: ReadOnlyStrategyInput[object] = ReadOnlyStrategyInput(
        "snapshot", "digest", AS_OF, (), DerivedFactSet(()), payload
    )

    class Clock:
        def now(self) -> datetime:
            return AS_OF

    context = RuntimeContext(HESTON_CONTRACT, subject, Clock(), "run")
    adapter = build_heston_subject_first_adapter({subject: knowledge})
    assert adapter(context) == adapter(context)
    assert adapter(context).evaluation_state.value == "pass"
