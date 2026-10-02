from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from analytics.calendar_facts import TradingCalendarView, monthly_expiration_day
from analytics.derived_fact_materialization import materialize_derived_fact
from analytics.derived_facts import DERIVED_FACT_REGISTRY
from analytics.features import DerivedFactSet
from domain import (
    CanonicalFact,
    CanonicalInstrumentIdentity,
    Confidence,
    EvidenceUsability,
    ExpirationCollection,
    ExpirationCycle,
    FreshnessStatus,
    HistoricalOptionPanel,
    HistoricalOptionSnapshot,
    MarketCapability,
    MarketDataSubjectType,
    OptionChain,
    OptionType,
    Provenance,
    ResolvedCapabilityEvidence,
    UnknownReason,
)
from market_data.session_calendar import UsEquitySessionCalendar
from screening.live_context import build_capability_subject
from strategies.heston_knowledge import build_heston_knowledge_mapping, formation_from_panel
from strategies.heston_manifest import HESTON_MANIFEST, STRATEGY_ID
from strategies.heston_planning import expand_demands, expirations_demand, historical_panel_demand
from strategies.heston_portfolio import HestonSubjectCandidate
from strategies.heston_selection import HestonPairSelection, select_heston_pair
from strategies.manifest_version_pins import version_pin_violations
from strategy_runtime.adapters.heston import HESTON_CONTRACT
from strategy_runtime.adapters.heston_portfolio import (
    HestonSubjectMaterialization,
    materialize_heston_family,
)
from strategy_runtime.adapters.heston_subject_first import (
    _formation_state,
    build_heston_subject_first_adapter,
)
from strategy_runtime.context import RuntimeContext
from strategy_runtime.cross_sectional_portfolio import PortfolioBookSide
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.manifest_contract import validate_manifest_contract
from tests.strategies.test_cboe_put_strategy import EVIDENCE, _put

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


def _calendar() -> TradingCalendarView:
    sessions = UsEquitySessionCalendar()
    return TradingCalendarView(
        lambda day: sessions.session(day) is not None, date(2024, 1, 1), date(2027, 12, 31)
    )


def _monthly(year: int, month: int) -> date:
    value = monthly_expiration_day(_calendar(), year, month)
    assert isinstance(value, date)
    return value


def _after_close(day: date) -> datetime:
    # 21:00 UTC is after the 16:00 New York close in both EDT and EST.
    return datetime.combine(day, time(21), tzinfo=UTC)


def _month(start: tuple[int, int], offset: int) -> tuple[int, int]:
    index = start[0] * 12 + start[1] - 1 + offset
    return index // 12, index % 12 + 1


def _panel(
    *,
    start: tuple[int, int] = (2024, 12),
    months: int = 13,
    skip: frozenset[int] = frozenset(),
    weekly_decoys: bool = False,
) -> HistoricalOptionPanel:
    """Monthly-expiration A08 panel; the return held from entry i is i/100."""
    snapshots = []
    prior_entry = None
    template = _candidate(0).contracts
    for offset in range(months):
        if offset in skip:
            prior_entry = None
            continue
        observed_date = _monthly(*_month(start, offset))
        observed_at = _after_close(observed_date)
        expiration = _monthly(*_month(start, offset + 1))
        legs = []
        for option_type, delta in ((OptionType.CALL, "0.49"), (OptionType.PUT, "-0.51")):
            source = template[0] if option_type is OptionType.CALL else template[1]
            legs.append(
                replace(
                    source,
                    option_contract_id=CanonicalInstrumentIdentity(
                        "occ", f"M{offset}-{option_type.value}"
                    ),
                    expiration=expiration,
                    observed_at=observed_at,
                    bid=Decimal("1"),
                    ask=Decimal("1"),
                    delta=Decimal(delta),
                )
            )
        contracts = list(legs)
        if weekly_decoys:
            # A weekly expiring one week later with a call delta of exactly 0.5.
            weekly = observed_date + timedelta(days=7)
            contracts.extend(
                replace(
                    leg,
                    option_contract_id=CanonicalInstrumentIdentity(
                        "occ", f"W{offset}-{leg.option_type.value}"
                    ),
                    expiration=weekly,
                    delta=Decimal("0.5") if leg.option_type is OptionType.CALL else Decimal("-0.5"),
                    bid=Decimal("9"),
                    ask=Decimal("9"),
                )
                for leg in legs
            )
        if prior_entry is not None:
            exit_mid = Decimal(1) + Decimal(offset - 1) / 100
            contracts.extend(
                replace(item, observed_at=observed_at, bid=exit_mid, ask=exit_mid)
                for item in prior_entry
            )
        snapshots.append(
            HistoricalOptionSnapshot(
                legs[0].underlying.instrument,
                observed_at,
                observed_at,
                f"snapshot-{offset}",
                tuple(contracts),
            )
        )
        prior_entry = tuple(legs)
    return HistoricalOptionPanel(
        snapshots[0].subject,
        snapshots[-1].observed_at,
        tuple(snapshots),
    )


# Entries 0..10 are lags 12..2 (mean of 0.00..0.10 = 0.05); entry 11 is lag 1 (0.11).
LAG_TWO_TO_TWELVE_MEAN = Decimal("0.05")


def test_historical_panel_materializes_complete_lags_two_through_twelve() -> None:
    panel = _panel()
    # Good Friday 2025-04-18 rolls the April monthly expiration to 2025-04-17.
    assert any(snapshot.observed_at.date() == date(2025, 4, 17) for snapshot in panel.snapshots)
    assert formation_from_panel(panel, _calendar()) == LAG_TWO_TO_TWELVE_MEAN

    mapping = build_heston_knowledge_mapping(
        subject="H0",
        snapshot_digest="sealed-a08",
        panel_observation_id="a08-observation",
        panel=panel,
        chain_observation_id="chain-observation",
        chain=OptionChain(
            "heston-chain",
            _candidate(0).contracts[0].underlying,
            AS_OF,
            tuple(replace(item, observed_at=AS_OF) for item in _candidate(0).contracts),
            EVIDENCE,
        ),
        selected_expiration=EXPIRY,
        formation_date_state="PASS",
        calendar=_calendar(),
    )
    facts = tuple(
        CanonicalFact(
            f"{request.fact_type}:H0:sealed-a08",
            1,
            request.fact_type,
            request.value,
            Confidence(1.0),
            Provenance(
                (request.observation_id,),
                ("fixture",),
                "fixture",
                (),
                panel.snapshots[-1].observed_at,
            ),
            panel.snapshots[-1].observed_at,
            panel.snapshots[-1].observed_at,
        )
        for request in mapping.canonical_fact_requests
    )
    derived_requests = mapping.compute_derived_fact_requests(facts)
    assert not isinstance(derived_requests, UnknownReason)
    derived = tuple(
        materialize_derived_fact(
            DERIVED_FACT_REGISTRY,
            request.feature_id,
            request.subject,
            "sealed-a08",
            value=request.value,
            unit=request.unit,
            effective_time=panel.snapshots[-1].observed_at,
            input_evidence=request.input_evidence,
            quality_status=request.quality_status,
            parameters=request.parameters,
        )
        for request in derived_requests
    )
    replayed = mapping.build_payload(facts, DerivedFactSet(derived))
    assert replayed.formation_momentum == LAG_TWO_TO_TWELVE_MEAN


def test_historical_panel_rejects_gap_and_lag_one_only_history() -> None:
    observed = _after_close(date(2025, 1, 17))
    later = _after_close(date(2025, 3, 21))
    call, put = _candidate(1).contracts
    call = replace(call, expiration=later.date(), observed_at=observed)
    put = replace(put, expiration=later.date(), observed_at=observed)
    exit_contracts = tuple(
        replace(item, observed_at=later, bid=Decimal("1.1"), ask=Decimal("1.1"))
        for item in (call, put)
    )
    panel = HistoricalOptionPanel(
        call.underlying.instrument,
        later,
        (
            HistoricalOptionSnapshot(
                call.underlying.instrument, observed, observed, "entry", (call, put)
            ),
            HistoricalOptionSnapshot(
                call.underlying.instrument, later, later, "exit", exit_contracts
            ),
        ),
    )
    assert formation_from_panel(panel, _calendar()) == UnknownReason(
        "invalid_straddle_formation_calendar"
    )


def test_missing_live_open_interest_and_market_are_unknown_not_excluded() -> None:
    candidate = _candidate(0)
    call, put = candidate.contracts
    result = materialize_heston_family(
        {"H0": replace(candidate, contracts=(replace(call, open_interest=None), put))}
    )
    assert result["H0"] == HestonSubjectMaterialization("UNKNOWN", "G_HES_LOWCOST_PAIR_UNKNOWN")
    result = materialize_heston_family(
        {"H0": replace(candidate, contracts=(replace(call, bid=None), put))}
    )
    assert result["H0"] == HestonSubjectMaterialization("UNKNOWN", "G_HES_LOWCOST_PAIR_UNKNOWN")


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


def test_weekly_expirations_are_never_held_in_formation() -> None:
    assert formation_from_panel(_panel(weekly_decoys=True), _calendar()) == (LAG_TWO_TO_TWELVE_MEAN)


def test_missing_interior_month_and_stale_anchor_are_unknown() -> None:
    gap = formation_from_panel(_panel(skip=frozenset({5})), _calendar())
    assert isinstance(gap, UnknownReason)
    stale = _panel(months=12)
    stale = replace(stale, as_of=_after_close(_monthly(2025, 12)))
    assert formation_from_panel(stale, _calendar()) == UnknownReason(
        "invalid_straddle_formation_calendar"
    )


def test_juneteenth_2026_monthly_expiration_rolls_to_thursday() -> None:
    assert _monthly(2026, 6) == date(2026, 6, 18)
    assert formation_from_panel(_panel(start=(2025, 6)), _calendar()) == (LAG_TWO_TO_TWELVE_MEAN)
    assert _formation_state(_after_close(date(2026, 6, 18))) == "PASS"
    assert _formation_state(_after_close(date(2026, 6, 19))) == "FAIL"
    assert _formation_state(datetime(2026, 6, 18, 19, tzinfo=UTC)) == "FAIL"  # before close


def _pair(strike: str, call_delta: str | None, open_interest: int | None = 10) -> tuple:
    call, put = _candidate(0).contracts
    return (
        replace(
            call,
            option_contract_id=CanonicalInstrumentIdentity("occ", f"K{strike}-C"),
            strike=Decimal(strike),
            delta=None if call_delta is None else Decimal(call_delta),
            open_interest=open_interest,
        ),
        replace(
            put,
            option_contract_id=CanonicalInstrumentIdentity("occ", f"K{strike}-P"),
            strike=Decimal(strike),
            delta=None if call_delta is None else Decimal(call_delta) - 1,
            open_interest=open_interest,
        ),
    )


def _select(*pairs: tuple) -> object:
    contracts = tuple(contract for pair in pairs for contract in pair)
    return select_heston_pair(contracts, expiration=EXPIRY, require_open_interest=True)


def test_unknown_open_interest_on_a_closer_pair_is_unknown_not_skipped() -> None:
    assert _select(_pair("100", "0.50", None), _pair("105", "0.45")) == UnknownReason(
        "G_HES_LOWCOST_PAIR_UNKNOWN"
    )
    selected = _select(_pair("90", "0.70", None), _pair("105", "0.45"))
    assert isinstance(selected, HestonPairSelection)
    assert selected.call.strike == Decimal(105)
    # Resolved zero open interest is a failed gate: the next pair is eligible.
    zero = _select(_pair("100", "0.50", 0), _pair("105", "0.45"))
    assert isinstance(zero, HestonPairSelection) and zero.call.strike == Decimal(105)


def test_missing_delta_that_could_be_closest_is_unknown() -> None:
    assert _select(_pair("95", "0.60"), _pair("100", None), _pair("105", "0.45")) == (
        UnknownReason("G_HES_LOWCOST_PAIR_UNKNOWN")
    )
    selected = _select(
        _pair("95", "0.55"), _pair("100", "0.50"), _pair("105", "0.45"), _pair("150", None)
    )
    assert isinstance(selected, HestonPairSelection)
    assert selected.call.strike == Decimal(100)


def test_portfolio_and_formation_share_one_selection_owner() -> None:
    import strategies.heston_knowledge as knowledge
    import strategy_runtime.adapters.heston_portfolio as portfolio

    assert knowledge.select_heston_pair is select_heston_pair
    assert portfolio.select_heston_pair is select_heston_pair
    assert not hasattr(knowledge, "_select_pair")


def test_planning_selects_next_month_monthly_expiration_not_a_weekly() -> None:
    now = _after_close(date(2026, 10, 16))
    cycles = (
        ExpirationCycle(date(2026, 10, 23), 7, False, True, now.date(), EVIDENCE),
        ExpirationCycle(date(2026, 11, 13), 28, False, True, now.date(), EVIDENCE),
        ExpirationCycle(date(2026, 11, 20), 35, True, False, now.date(), EVIDENCE),
        ExpirationCycle(date(2026, 12, 18), 63, True, False, now.date(), EVIDENCE),
    )
    resolved = ResolvedCapabilityEvidence(
        expirations_demand(now).demand_id,
        MarketCapability.OPTION_CHAIN_V1,
        EvidenceUsability.RESOLVED,
        ExpirationCollection(now.date(), cycles),
        ("heston-expirations",),
        FreshnessStatus.FRESH,
    )
    result = expand_demands({resolved.demand_id: resolved}, now=now)
    assert result.selections == (("expiration", "2026-11-20"),)
    weeklies_only = replace(resolved, value=ExpirationCollection(now.date(), cycles[:2]))
    assert expand_demands({resolved.demand_id: weeklies_only}, now=now).unknown_reasons == (
        UnknownReason("G_HES_FORMATION_DATE_UNKNOWN"),
    )
