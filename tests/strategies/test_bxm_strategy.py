from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from analytics.buywrite import cboe_buywrite_daily_return
from analytics.derived_fact_materialization import materialize_derived_fact
from analytics.derived_facts import (
    CBOE_BUYWRITE_DAILY_RETURN,
    DERIVED_FACT_REGISTRY,
    WINDOWED_OPTION_TRADE_VWAP,
)
from analytics.features import DerivedFactSet
from domain import (
    CanonicalFact,
    CanonicalInstrumentIdentity,
    Confidence,
    EvidenceKind,
    EvidenceReference,
    EvidenceUsability,
    HistoricalOptionPanel,
    HistoricalOptionSnapshot,
    IndexDividendPoints,
    IndexSettlementValue,
    Instrument,
    InstrumentKind,
    MarketCapability,
    OHLCVBar,
    OHLCVSeries,
    OptionChain,
    OptionContract,
    OptionTrade,
    OptionTradeTape,
    OptionType,
    Provenance,
    Quote,
    ResolvedCapabilityEvidence,
    Security,
    SecurityAssetType,
    SettlementStyle,
    UnknownReason,
)
from facts.canonical_projection import canonical_fact_id
from strategies.bxm_evaluation import NO_ACTION, evaluate_bxm
from strategies.bxm_knowledge import BxmPayload, build_bxm_knowledge_mapping
from strategies.bxm_manifest import BXM_MANIFEST, STRATEGY_ID
from strategies.bxm_planning import (
    bootstrap_demands,
    expand_post_selection_demands,
    resolved_field_requirements,
)
from strategies.cboe_put_planning import chain_demand, quote_demand
from strategies.knowledge_contracts import KnowledgeMapping
from strategies.manifest import ParameterSpec
from strategies.tristate_components import PASS, UNKNOWN
from strategy_runtime.adapters.bxm import BXM_CONTRACT
from strategy_runtime.adapters.bxm_subject_first import (
    build_bxm_overlay,
    build_bxm_subject_first_adapter,
)
from strategy_runtime.context import RuntimeContext
from strategy_runtime.contract import StructureKind
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.result import EvaluationState

ROLL = datetime(2026, 10, 16, 14, 55, tzinfo=UTC)
EXPIRY = date(2026, 11, 20)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "spx-chain", 1),)
SPX = Security(
    Instrument(
        CanonicalInstrumentIdentity("index_root", "SPX"), InstrumentKind.INDEX, "SPX", "USD"
    ),
    "SPX",
    SecurityAssetType.INDEX,
    "CBOE",
)


def _call(
    strike: str, *, root: str = "SPX", settlement: SettlementStyle = SettlementStyle.AM
) -> OptionContract:
    return OptionContract(
        CanonicalInstrumentIdentity("occ", f"SPX-{EXPIRY}-{strike}-C"),
        SPX,
        EXPIRY,
        Decimal(strike),
        OptionType.CALL,
        Decimal("50"),
        Decimal("51"),
        None,
        10,
        10,
        Decimal("0.5"),
        None,
        None,
        None,
        None,
        None,
        ROLL,
        EVIDENCE,
        root,
        settlement,
    )


def _chain(*contracts: OptionContract) -> OptionChain:
    return OptionChain("spx-chain", SPX, ROLL, contracts, EVIDENCE)


def test_bxm_manifest_contract_and_capabilities_are_production_exact() -> None:
    assert BXM_CONTRACT.strategy_id == STRATEGY_ID
    assert BXM_CONTRACT.structure is StructureKind.CUSTOM
    assert {item.name for item in BXM_MANIFEST.required_market_capabilities} >= {
        "option_trade_tape_v1",
        "index_dividend_points_v1",
        "index_settlement_value_v1",
    }


def test_bxm_selects_closest_standard_next_month_call_at_or_above_reference() -> None:
    chain = _chain(
        _call("4995"),
        _call("5000"),
        _call("5005"),
        _call("5001", root="SPXW", settlement=SettlementStyle.PM),
    )
    decision = evaluate_bxm(
        decision_date=ROLL.date(),
        roll_date=ROLL.date(),
        quote_effective_time=ROLL,
        quote_value=Decimal("5002"),
        chain=chain,
    )
    assert decision.verdict == PASS
    assert decision.selected_call is not None
    assert decision.selected_call.strike == Decimal("5005")
    payload = BxmPayload(
        chain,
        Decimal("5002"),
        ROLL,
        UnknownReason("OPTION_TRADE_TAPE_UNAVAILABLE"),
        None,
        UnknownReason("INDEX_DIVIDEND_POINTS_UNAVAILABLE"),
        UnknownReason("INDEX_SETTLEMENT_VALUE_UNAVAILABLE"),
    )
    overlay = build_bxm_overlay(payload, decision)
    assert overlay.broker_executable is False
    assert overlay.underlying.instrument.display_symbol == "SPX"
    assert overlay.option_legs[0].contract.identity == decision.selected_call.identity


def test_manifest_parameters_are_the_live_selection_and_quantity_authority() -> None:
    nodes = []
    for node in BXM_MANIFEST.nodes:
        if node.node_id == "selection":
            values = {item.name: item for item in node.parameters}
            values["contract_root"] = ParameterSpec("contract_root", "Text", "SPXW")
            values["settlement_style"] = ParameterSpec("settlement_style", "Text", "pm")
            node = replace(node, parameters=tuple(values.values()))
        elif node.node_id == "short_call_quantity":
            node = replace(node, parameters=(ParameterSpec("value", "Decimal", "2"),))
        nodes.append(node)
    changed = replace(BXM_MANIFEST, nodes=tuple(nodes), strategy_version="1.0.1")
    decision = evaluate_bxm(
        decision_date=ROLL.date(),
        roll_date=ROLL.date(),
        quote_effective_time=ROLL,
        quote_value=Decimal("5000"),
        chain=_chain(
            _call("5000"),
            _call("5001", root="SPXW", settlement=SettlementStyle.PM),
        ),
        manifest=changed,
    )
    assert decision.verdict == PASS
    assert decision.selected_call is not None
    assert decision.selected_call.root == "SPXW"
    assert decision.short_call_quantity == Decimal(2)


def test_bxm_truth_table_and_wrong_contract_identity_fail_closed() -> None:
    assert (
        evaluate_bxm(
            decision_date=date(2026, 10, 12),
            roll_date=ROLL.date(),
            quote_effective_time=ROLL,
            quote_value=Decimal("5000"),
            chain=_chain(_call("5000")),
        ).verdict
        == NO_ACTION
    )
    assert (
        evaluate_bxm(
            decision_date=ROLL.date(),
            roll_date=UnknownReason("calendar_unavailable"),
            quote_effective_time=ROLL,
            quote_value=Decimal("5000"),
            chain=_chain(_call("5000")),
        ).verdict
        == UNKNOWN
    )
    result = evaluate_bxm(
        decision_date=ROLL.date(),
        roll_date=ROLL.date(),
        quote_effective_time=ROLL,
        quote_value=Decimal("5000"),
        chain=_chain(_call("5000", root="SPXW", settlement=SettlementStyle.PM)),
    )
    assert result.verdict == UNKNOWN
    assert result.reason == "G_BXM_STRIKE_EXISTS_UNKNOWN"


def test_bxm_plans_every_declared_lifecycle_capability_as_optional_where_appropriate() -> None:
    now = datetime(2026, 10, 16, 15, 0, tzinfo=UTC)
    demands = bootstrap_demands(now)
    by_capability = {item.capability: item for item in demands}
    for capability in (
        MarketCapability.INDEX_DIVIDEND_POINTS_V1,
        MarketCapability.INDEX_SETTLEMENT_VALUE_V1,
        MarketCapability.HISTORICAL_BARS_V1,
        MarketCapability.HISTORICAL_OPTION_PANEL_V1,
    ):
        assert by_capability[capability].required is False
        assert capability in resolved_field_requirements()
    assert MarketCapability.OPTION_TRADE_TAPE_V1 not in by_capability

    call = _call("5005")
    quote = Quote(SPX.instrument, None, None, Decimal("5002"), None, None, None, "USD")
    chain = _chain(call)
    evidence = {
        quote_demand(now).demand_id: ResolvedCapabilityEvidence(
            quote_demand(now).demand_id,
            MarketCapability.REAL_TIME_QUOTE_V1,
            EvidenceUsability.RESOLVED,
            quote,
            ("quote-observation",),
            None,
        ),
        chain_demand(now, EXPIRY).demand_id: ResolvedCapabilityEvidence(
            chain_demand(now, EXPIRY).demand_id,
            MarketCapability.OPTION_CHAIN_V1,
            EvidenceUsability.RESOLVED,
            chain,
            ("chain-observation",),
            None,
        ),
    }
    post = expand_post_selection_demands(
        evidence,
        (("expiration", EXPIRY.isoformat()),),
        now=now,
        roll_date=now.date(),
    )
    assert len(post.demands) == 1
    tape = post.demands[0]
    assert tape.capability is MarketCapability.OPTION_TRADE_TAPE_V1
    assert tape.contract_identity == call.identity
    start_utc = tape.effective_start.astimezone(UTC)
    end_utc = tape.effective_end.astimezone(UTC)
    assert (start_utc.hour, start_utc.minute) == (15, 30)
    assert (end_utc.hour, end_utc.minute) == (17, 30)


def test_buywrite_daily_return_is_materialized_from_projected_inputs() -> None:
    prior_time = datetime(2026, 10, 15, 19, 59, tzinfo=UTC)
    entry_time = datetime(2026, 10, 16, 17, 0, tzinfo=UTC)
    close_time = datetime(2026, 10, 16, 19, 59, tzinfo=UTC)
    old_call = replace(
        _call("5005"),
        option_contract_id=CanonicalInstrumentIdentity("occ", "SPX-2026-10-16-98-C"),
        expiration=ROLL.date(),
        strike=Decimal("98"),
        bid=Decimal("3"),
        ask=Decimal("5"),
        observed_at=prior_time,
    )
    other_old_call = replace(
        old_call,
        option_contract_id=CanonicalInstrumentIdentity("occ", "SPX-2026-10-16-99-C"),
        strike=Decimal("99"),
    )
    new_call = replace(
        _call("5005"),
        strike=Decimal("105"),
        bid=Decimal("2"),
        ask=Decimal("4"),
    )
    new_close = replace(new_call, observed_at=close_time)
    after_close = replace(
        new_call,
        bid=Decimal("98"),
        ask=Decimal("100"),
        observed_at=datetime(2026, 10, 16, 20, 1, tzinfo=UTC),
    )
    panel = HistoricalOptionPanel(
        SPX.instrument,
        datetime(2026, 10, 16, 20, 2, tzinfo=UTC),
        (
            HistoricalOptionSnapshot(
                SPX.instrument,
                prior_time,
                prior_time,
                "prior-close",
                (old_call, other_old_call),
            ),
            HistoricalOptionSnapshot(
                SPX.instrument, close_time, close_time, "current-close", (new_close,)
            ),
            HistoricalOptionSnapshot(
                SPX.instrument,
                after_close.observed_at,
                after_close.observed_at,
                "after-close",
                (after_close,),
            ),
        ),
    )
    trade = OptionTrade(
        "trade-1", new_call.identity, Decimal("4"), Decimal("2"), entry_time, entry_time, ()
    )
    excluded_time = entry_time + timedelta(minutes=1)
    excluded_trade = OptionTrade(
        "trade-excluded",
        new_call.identity,
        Decimal("10"),
        Decimal("100"),
        excluded_time,
        excluded_time,
        ("A",),
    )
    tape = OptionTradeTape(new_call.identity, close_time, (trade, excluded_trade))
    aligned_bar = OHLCVBar(
        SPX.instrument,
        60,
        entry_time - timedelta(seconds=60),
        entry_time,
        Decimal("102"),
        Decimal("102"),
        Decimal("102"),
        Decimal("102"),
        Decimal("1"),
    )
    excluded_bar = replace(
        aligned_bar,
        start_at=excluded_time - timedelta(seconds=60),
        end_at=excluded_time,
        open=Decimal("999"),
        high=Decimal("999"),
        low=Decimal("999"),
        close=Decimal("999"),
    )
    prior_close_bar = replace(
        aligned_bar,
        start_at=prior_time - timedelta(seconds=60),
        end_at=prior_time,
        open=Decimal("100"),
        high=Decimal("100"),
        low=Decimal("100"),
        close=Decimal("100"),
    )
    current_close_bar = replace(
        aligned_bar,
        start_at=close_time - timedelta(seconds=60),
        end_at=close_time,
    )
    series = OHLCVSeries(
        SPX.instrument,
        60,
        datetime(2026, 10, 16, 20, 2, tzinfo=UTC),
        (prior_close_bar, aligned_bar, excluded_bar, current_close_bar),
    )
    mapping = build_bxm_knowledge_mapping(
        subject="SPX",
        snapshot_digest="digest",
        quote_observation_id="quote-observation",
        chain_observation_id="chain-observation",
        chain=_chain(new_call),
        spot=Decimal("102"),
        quote_effective_time=ROLL,
        tape_observation=("tape-observation", tape),
        dividend_observation=(
            "dividend-observation",
            IndexDividendPoints(SPX.instrument, Decimal("1"), ROLL.date()),
        ),
        settlement_observation=(
            "settlement-observation",
            IndexSettlementValue(
                SPX, ROLL.date(), SettlementStyle.AM, Decimal("101"), ROLL, EVIDENCE
            ),
        ),
        vwap_window_start=datetime(2026, 10, 16, 15, 30, tzinfo=UTC),
        vwap_window_end=datetime(2026, 10, 16, 17, 30, tzinfo=UTC),
        roll_date=ROLL.date(),
        bars_observation=("bars-observation", series),
        option_history_observation=("option-history-observation", panel),
        selected_call_identity=new_call.identity,
        held_call_identity=old_call.identity,
    )
    facts = tuple(
        CanonicalFact(
            canonical_fact_id(request.fact_type, request.subject, "digest"),
            1,
            request.fact_type,
            request.value,
            Confidence(1.0),
            Provenance((request.observation_id,), ("fixture",), "fixture", (), ROLL),
            ROLL,
            ROLL,
        )
        for request in mapping.canonical_fact_requests
    )
    requests = mapping.compute_derived_fact_requests(facts)
    assert not isinstance(requests, UnknownReason)
    daily_request = next(item for item in requests if item.feature_id == CBOE_BUYWRITE_DAILY_RETURN)
    expected = cboe_buywrite_daily_return(
        roll_day=True,
        prior_index_close=Decimal("100"),
        prior_call_close=Decimal("4"),
        index_close=Decimal("102"),
        call_close=Decimal("3"),
        dividend_points=Decimal("1"),
        old_strike=Decimal("98"),
        settlement_value=Decimal("101"),
        index_vwav=Decimal("102"),
        call_vwap=Decimal("4"),
    )
    assert daily_request.value == expected
    materialized = materialize_derived_fact(
        DERIVED_FACT_REGISTRY,
        daily_request.feature_id,
        daily_request.subject,
        "digest",
        value=daily_request.value,
        unit=daily_request.unit,
        effective_time=ROLL,
        input_evidence=daily_request.input_evidence,
        quality_status=daily_request.quality_status,
        parameters=daily_request.parameters,
    )
    payload = mapping.build_payload(facts, DerivedFactSet((materialized,)))
    assert payload.daily_return == daily_request.value

    def _assert_lifecycle_mismatch_stays_unknown(
        *,
        dividend: IndexDividendPoints,
        settlement: IndexSettlementValue,
        digest: str,
    ) -> None:
        mismatched = build_bxm_knowledge_mapping(
            subject="SPX",
            snapshot_digest=digest,
            quote_observation_id="quote-observation",
            chain_observation_id="chain-observation",
            chain=_chain(new_call),
            spot=Decimal("102"),
            quote_effective_time=ROLL,
            tape_observation=("tape-observation", tape),
            dividend_observation=("dividend-observation", dividend),
            settlement_observation=("settlement-observation", settlement),
            vwap_window_start=datetime(2026, 10, 16, 15, 30, tzinfo=UTC),
            vwap_window_end=datetime(2026, 10, 16, 17, 30, tzinfo=UTC),
            roll_date=ROLL.date(),
            bars_observation=("bars-observation", series),
            option_history_observation=("option-history-observation", panel),
            selected_call_identity=new_call.identity,
            held_call_identity=old_call.identity,
        )
        mismatched_facts = tuple(
            CanonicalFact(
                canonical_fact_id(request.fact_type, request.subject, digest),
                1,
                request.fact_type,
                request.value,
                Confidence(1.0),
                Provenance((request.observation_id,), ("fixture",), "fixture", (), ROLL),
                ROLL,
                ROLL,
            )
            for request in mismatched.canonical_fact_requests
        )
        mismatched_requests = mismatched.compute_derived_fact_requests(mismatched_facts)
        assert not isinstance(mismatched_requests, UnknownReason)
        assert all(
            item.feature_id != CBOE_BUYWRITE_DAILY_RETURN for item in mismatched_requests
        )
        mismatched_payload = mismatched.build_payload(mismatched_facts, DerivedFactSet(()))
        assert isinstance(mismatched_payload.daily_return, UnknownReason)

    valid_dividend = IndexDividendPoints(SPX.instrument, Decimal("1"), ROLL.date())
    valid_settlement = IndexSettlementValue(
        SPX, ROLL.date(), SettlementStyle.AM, Decimal("101"), ROLL, EVIDENCE
    )
    _assert_lifecycle_mismatch_stays_unknown(
        dividend=replace(valid_dividend, effective_date=ROLL.date() + timedelta(days=1)),
        settlement=valid_settlement,
        digest="wrong-dividend-date",
    )
    other_index = replace(
        SPX,
        instrument=replace(
            SPX.instrument,
            identity=CanonicalInstrumentIdentity("index_root", "NDX"),
            display_symbol="NDX",
        ),
        symbol="NDX",
    )
    for digest, invalid_settlement in (
        (
            "wrong-settlement-date",
            replace(valid_settlement, settlement_date=ROLL.date() + timedelta(days=1)),
        ),
        (
            "wrong-settlement-style",
            replace(valid_settlement, settlement_style=SettlementStyle.PM),
        ),
        ("wrong-settlement-index", replace(valid_settlement, index=other_index)),
    ):
        _assert_lifecycle_mismatch_stays_unknown(
            dividend=valid_dividend,
            settlement=invalid_settlement,
            digest=digest,
        )

    fallback_time = datetime(2026, 10, 16, 17, 29, tzinfo=UTC)
    fallback_quote = replace(new_call, bid=Decimal("3.5"), observed_at=fallback_time)
    fallback_panel = replace(
        panel,
        snapshots=(
            panel.snapshots[0],
            HistoricalOptionSnapshot(
                SPX.instrument,
                fallback_time,
                fallback_time,
                "no-trade-fallback",
                (fallback_quote,),
            ),
            *panel.snapshots[1:],
        ),
    )
    fallback_mapping = build_bxm_knowledge_mapping(
        subject="SPX",
        snapshot_digest="fallback-digest",
        quote_observation_id="quote-observation",
        chain_observation_id="chain-observation",
        chain=_chain(new_call),
        spot=Decimal("102"),
        quote_effective_time=ROLL,
        tape_observation=(
            "empty-tape-observation",
            OptionTradeTape(new_call.identity, close_time, ()),
        ),
        dividend_observation=(
            "dividend-observation",
            IndexDividendPoints(SPX.instrument, Decimal("1"), ROLL.date()),
        ),
        settlement_observation=None,
        vwap_window_start=datetime(2026, 10, 16, 15, 30, tzinfo=UTC),
        vwap_window_end=datetime(2026, 10, 16, 17, 30, tzinfo=UTC),
        roll_date=ROLL.date(),
        bars_observation=("bars-observation", series),
        option_history_observation=("option-history-observation", fallback_panel),
        selected_call_identity=new_call.identity,
        held_call_identity=old_call.identity,
    )
    fallback_facts = tuple(
        CanonicalFact(
            canonical_fact_id(request.fact_type, request.subject, "fallback-digest"),
            1,
            request.fact_type,
            request.value,
            Confidence(1.0),
            Provenance((request.observation_id,), ("fixture",), "fixture", (), ROLL),
            ROLL,
            ROLL,
        )
        for request in fallback_mapping.canonical_fact_requests
    )
    fallback_requests = fallback_mapping.compute_derived_fact_requests(fallback_facts)
    assert not isinstance(fallback_requests, UnknownReason)
    fallback_vwap = next(
        item for item in fallback_requests if item.feature_id == WINDOWED_OPTION_TRADE_VWAP
    )
    assert fallback_vwap.value == Decimal("3.5")

    misaligned_bar = replace(
        aligned_bar,
        start_at=aligned_bar.start_at + timedelta(minutes=1),
        end_at=aligned_bar.end_at + timedelta(minutes=1),
    )
    misaligned_mapping = build_bxm_knowledge_mapping(
        subject="SPX",
        snapshot_digest="misaligned-digest",
        quote_observation_id="quote-observation",
        chain_observation_id="chain-observation",
        chain=_chain(new_call),
        spot=Decimal("102"),
        quote_effective_time=ROLL,
        tape_observation=("tape-observation", tape),
        dividend_observation=(
            "dividend-observation",
            IndexDividendPoints(SPX.instrument, Decimal("1"), ROLL.date()),
        ),
        settlement_observation=(
            "settlement-observation",
            IndexSettlementValue(
                SPX, ROLL.date(), SettlementStyle.AM, Decimal("101"), ROLL, EVIDENCE
            ),
        ),
        vwap_window_start=datetime(2026, 10, 16, 15, 30, tzinfo=UTC),
        vwap_window_end=datetime(2026, 10, 16, 17, 30, tzinfo=UTC),
        roll_date=ROLL.date(),
        bars_observation=(
            "bars-observation",
            OHLCVSeries(SPX.instrument, 60, close_time, (misaligned_bar,)),
        ),
        option_history_observation=("option-history-observation", panel),
        selected_call_identity=new_call.identity,
        held_call_identity=old_call.identity,
    )
    misaligned_facts = tuple(
        CanonicalFact(
            canonical_fact_id(request.fact_type, request.subject, "misaligned-digest"),
            1,
            request.fact_type,
            request.value,
            Confidence(1.0),
            Provenance((request.observation_id,), ("fixture",), "fixture", (), ROLL),
            ROLL,
            ROLL,
        )
        for request in misaligned_mapping.canonical_fact_requests
    )
    misaligned_requests = misaligned_mapping.compute_derived_fact_requests(misaligned_facts)
    assert not isinstance(misaligned_requests, UnknownReason)
    assert all(item.feature_id != CBOE_BUYWRITE_DAILY_RETURN for item in misaligned_requests)


def test_production_adapter_resolves_exact_lifecycle_evidence_and_materialized_return() -> None:
    class Clock:
        def now(self) -> datetime:
            return ROLL

    call = _call("5005")
    settlement = IndexSettlementValue(
        SPX,
        call.expiration,
        SettlementStyle.AM,
        Decimal("5010"),
        ROLL,
        EVIDENCE,
    )
    payload = BxmPayload(
        _chain(call),
        Decimal("5002"),
        ROLL,
        Decimal("50.5"),
        call.identity,
        IndexDividendPoints(SPX.instrument, Decimal("1"), ROLL.date()),
        settlement,
        ROLL.date(),
        Decimal("0.01"),
    )
    knowledge = ReadOnlyStrategyInput(
        "snapshot",
        "digest",
        ROLL,
        (),
        DerivedFactSet(()),
        payload,
    )
    result = build_bxm_subject_first_adapter({"SPX": knowledge})(
        RuntimeContext(BXM_CONTRACT, "SPX", Clock(), "run")
    )
    assert result.evaluation_state is EvaluationState.PASS
    assert result.metrics["entry.price_state"].native() == "RESOLVED_WINDOWED_OPTION_TRADE_VWAP"
    assert result.metrics["outcome.index_dividend_points"].native() == Decimal("1")
    assert result.metrics["lifecycle.soq_value"].native() == Decimal("5010")
    assert result.metrics["outcome.daily_return"].native() == Decimal("0.01")
    assert result.metrics["lifecycle.held_position_identity"].native() == call.identity

    mismatched = replace(payload, tape_contract_identity="other")
    mismatch_knowledge = replace(knowledge, payload=mismatched)
    mismatch = build_bxm_subject_first_adapter({"SPX": mismatch_knowledge})(
        RuntimeContext(BXM_CONTRACT, "SPX", Clock(), "run")
    )
    assert mismatch.metrics["entry.price_state"].native() == "OPTION_TRADE_TAPE_CONTRACT_MISMATCH"
    assert "entry.windowed_vwap" not in mismatch.metrics

    irrelevant = replace(
        payload,
        dividend_points=IndexDividendPoints(SPX.instrument, Decimal("1"), date(2027, 1, 1)),
        settlement_value=replace(settlement, settlement_date=date(2026, 12, 18)),
    )
    irrelevant_result = build_bxm_subject_first_adapter(
        {"SPX": replace(knowledge, payload=irrelevant)}
    )(RuntimeContext(BXM_CONTRACT, "SPX", Clock(), "run"))
    assert "outcome.index_dividend_points" not in irrelevant_result.metrics
    assert "lifecycle.soq_value" not in irrelevant_result.metrics


def test_production_knowledge_path_uses_held_call_for_non_roll_daily_return() -> None:
    return_time = datetime(2026, 11, 19, 19, 59, tzinfo=UTC)
    prior_time = datetime(2026, 11, 18, 19, 59, tzinfo=UTC)
    roll_date = date(2026, 11, 20)
    held = replace(
        _call("5005"),
        expiration=roll_date,
        bid=Decimal("3"),
        ask=Decimal("5"),
        observed_at=prior_time,
    )
    held_current = replace(
        held,
        bid=Decimal("2"),
        ask=Decimal("4"),
        observed_at=return_time,
    )
    panel = HistoricalOptionPanel(
        SPX.instrument,
        return_time,
        (
            HistoricalOptionSnapshot(
                SPX.instrument, prior_time, prior_time, "prior-close", (held,)
            ),
            HistoricalOptionSnapshot(
                SPX.instrument,
                return_time,
                return_time,
                "current-close",
                (held_current,),
            ),
        ),
    )
    prior_bar = OHLCVBar(
        SPX.instrument,
        60,
        prior_time - timedelta(seconds=60),
        prior_time,
        Decimal("100"),
        Decimal("100"),
        Decimal("100"),
        Decimal("100"),
        Decimal("1"),
    )
    current_bar = replace(
        prior_bar,
        start_at=return_time - timedelta(seconds=60),
        end_at=return_time,
        open=Decimal("101"),
        high=Decimal("101"),
        low=Decimal("101"),
        close=Decimal("101"),
    )
    series = OHLCVSeries(SPX.instrument, 60, return_time, (prior_bar, current_bar))

    def _mapping(held_identity: str | None, digest: str) -> KnowledgeMapping[BxmPayload]:
        return build_bxm_knowledge_mapping(
            subject="SPX",
            snapshot_digest=digest,
            quote_observation_id="quote-observation",
            chain_observation_id="chain-observation",
            chain=_chain(_call("5100")),
            spot=Decimal("101"),
            quote_effective_time=return_time,
            tape_observation=None,
            dividend_observation=(
                "dividend-observation",
                IndexDividendPoints(SPX.instrument, Decimal("1"), return_time.date()),
            ),
            settlement_observation=None,
            vwap_window_start=return_time - timedelta(hours=4),
            vwap_window_end=return_time - timedelta(hours=2),
            roll_date=roll_date,
            bars_observation=("bars-observation", series),
            option_history_observation=("option-history-observation", panel),
            selected_call_identity=None,
            held_call_identity=held_identity,
        )

    def _facts(
        mapping: KnowledgeMapping[BxmPayload], digest: str
    ) -> tuple[CanonicalFact, ...]:
        return tuple(
            CanonicalFact(
                canonical_fact_id(request.fact_type, request.subject, digest),
                1,
                request.fact_type,
                request.value,
                Confidence(1.0),
                Provenance((request.observation_id,), ("fixture",), "fixture", (), return_time),
                return_time,
                return_time,
            )
            for request in mapping.canonical_fact_requests
        )

    mapping = _mapping(held.identity, "non-roll")
    facts = _facts(mapping, "non-roll")
    requests = mapping.compute_derived_fact_requests(facts)
    assert not isinstance(requests, UnknownReason)
    daily_request = next(item for item in requests if item.feature_id == CBOE_BUYWRITE_DAILY_RETURN)
    assert daily_request.value == (Decimal("99") / Decimal("96")) - Decimal(1)
    materialized = materialize_derived_fact(
        DERIVED_FACT_REGISTRY,
        daily_request.feature_id,
        daily_request.subject,
        "non-roll",
        value=daily_request.value,
        unit=daily_request.unit,
        effective_time=return_time,
        input_evidence=daily_request.input_evidence,
        quality_status=daily_request.quality_status,
        parameters=daily_request.parameters,
    )
    assert mapping.build_payload(facts, DerivedFactSet((materialized,))).daily_return == (
        daily_request.value
    )

    missing_mapping = _mapping(None, "non-roll-missing-held")
    missing_facts = _facts(missing_mapping, "non-roll-missing-held")
    missing_requests = missing_mapping.compute_derived_fact_requests(missing_facts)
    assert not isinstance(missing_requests, UnknownReason)
    assert all(item.feature_id != CBOE_BUYWRITE_DAILY_RETURN for item in missing_requests)
    missing_payload = missing_mapping.build_payload(missing_facts, DerivedFactSet(()))
    assert isinstance(missing_payload.daily_return, UnknownReason)
