"""STONK-002 shared pure Component and static Plugin regression coverage."""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from domain import (
    AnnouncementTime,
    CanonicalInstrumentIdentity,
    EarningsEvent,
    EvidenceKind,
    EvidenceReference,
    ExpirationCollection,
    ExpirationCycle,
    Instrument,
    InstrumentKind,
    OptionChain,
    OptionCollection,
    OptionContract,
    OptionStructure,
    OptionType,
    Security,
    SecurityAssetType,
    SecurityCollection,
)
from strategies import (
    STONK_STRATEGY_PLUGINS,
    CalendarStructure,
    ComponentContractError,
    DeltaNearestLeg,
    DeterministicSecurityCap,
    DoubleCalendarStructure,
    DtePairSelector,
    EarningsEventWindow,
    ExpirationPairProjection,
    ExpirationPairSelector,
    ForwardFactor,
    ImpliedForwardVolatility,
    NearestCommonStrikeCalendar,
    OptionLegLiquidity,
    OptionStructureDebit,
    RequiredEvidenceGate,
    SecurityUniverseFilter,
    VerdictClassifier,
    VerticalStructure,
    WeightedScoreWithCeiling,
)
from strategies.manifest import ComponentReference
from strategies.plugins import build_plugin_registry
from strategies.stonk_components import (
    B,
    D,
    DATE,
    DECIMAL_LIST,
    EARNINGS_EVENT,
    EVIDENCE_LIST,
    EXPIRATION_COLLECTION,
    EXPIRATION_CYCLE,
    INTEGER,
    OPTION_CHAIN,
    OPTION_COLLECTION,
    OPTION_CONTRACT,
    OPTION_STRUCTURE,
    OPTION_TYPE,
    SECURITY_COLLECTION,
)
from strategies.type_system import ComponentValues, StrategyTypeReference, TypedValue

NOW = datetime(2026, 1, 1, 16, tzinfo=timezone.utc)
AS_OF = date(2026, 1, 1)
FRONT = date(2026, 1, 17)
BACK = date(2026, 2, 21)
EVENT_DATE = date(2026, 1, 20)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "option-observation"),)


def values(**items: tuple[StrategyTypeReference, object]) -> ComponentValues:
    return ComponentValues(
        tuple((name, TypedValue(type_ref, value)) for name, (type_ref, value) in items.items())
    )


def security(symbol: str = "AAPL") -> Security:
    return Security(
        Instrument(
            CanonicalInstrumentIdentity("figi", f"figi-{symbol}"),
            InstrumentKind.EQUITY,
            symbol,
            "USD",
        ),
        symbol,
        SecurityAssetType.EQUITY,
        "XNAS",
    )


def contract(
    option_id: str,
    expiration: date,
    strike: str,
    option_type: OptionType,
    delta: str,
    mark: str,
) -> OptionContract:
    mark_value = Decimal(mark)
    return OptionContract(
        CanonicalInstrumentIdentity("asa-option-v1", option_id),
        security(),
        expiration,
        Decimal(strike),
        option_type,
        mark_value - Decimal("0.10"),
        mark_value + Decimal("0.10"),
        mark_value,
        100,
        500,
        Decimal(delta),
        Decimal("0.01"),
        Decimal("-0.02"),
        Decimal("0.03"),
        Decimal("0.01"),
        Decimal("0.30"),
        NOW,
        EVIDENCE,
    )


def chain() -> OptionChain:
    contracts = (
        contract("front-call-100", FRONT, "100", OptionType.CALL, "0.55", "2"),
        contract("front-call-105", FRONT, "105", OptionType.CALL, "0.30", "1"),
        contract("back-call-100", BACK, "100", OptionType.CALL, "0.58", "3"),
        contract("back-call-105", BACK, "105", OptionType.CALL, "0.33", "2"),
        contract("front-put-95", FRONT, "95", OptionType.PUT, "-0.30", "1"),
        contract("back-put-95", BACK, "95", OptionType.PUT, "-0.33", "2"),
    )
    return OptionChain("chain-1", security(), NOW, contracts, EVIDENCE)


def earnings_event(*, confirmed: bool = True) -> EarningsEvent:
    return EarningsEvent(
        "event-1",
        security(),
        EVENT_DATE,
        AnnouncementTime.AFTER_CLOSE,
        Decimal("0.05"),
        confirmed,
        (),
        NOW,
        EVIDENCE,
    )


def test_plugins_register_all_components_statically_and_deterministically() -> None:
    registry = build_plugin_registry((), STONK_STRATEGY_PLUGINS)
    expected = {
        (component.definition.namespace, component.definition.name)
        for plugin in STONK_STRATEGY_PLUGINS
        for component in plugin.components
    }
    assert len(expected) == 18
    for namespace, name in expected:
        assert registry.resolve(ComponentReference(namespace, name, "1.0.0"))
    assert (
        registry.identity
        == build_plugin_registry((), tuple(reversed(STONK_STRATEGY_PLUGINS))).identity
    )
    assert STONK_STRATEGY_PLUGINS[0].plugin_id == (
        "263fa946cd81ec3ed561a3a64ea80353730f831063466c6b4363ea510bc1fd17"
    )
    assert STONK_STRATEGY_PLUGINS[1].metadata.version == "1.2.0"
    assert STONK_STRATEGY_PLUGINS[1].plugin_id == (
        "b0e9154404d087fa078327309ab81071028ee852ad9308be4d85a208f4a5860b"
    )


def test_evidence_universe_cap_score_and_verdict_primitives() -> None:
    assert (
        RequiredEvidenceGate()
        .evaluate(
            values(evidence=(EVIDENCE_LIST, EVIDENCE)),
            values(minimum_count=(INTEGER, 1)),
        )
        .get("complete")
        .value
        is True
    )

    aapl, msft = security(), security("MSFT")
    included = (
        SecurityUniverseFilter()
        .evaluate(
            values(
                candidates=(SECURITY_COLLECTION, SecurityCollection((msft, aapl))),
                excluded=(SECURITY_COLLECTION, SecurityCollection((msft,))),
            ),
            ComponentValues(()),
        )
        .get("included")
        .value
    )
    assert included == SecurityCollection((aapl,))

    candidates = SecurityCollection((msft, aapl))
    capped = (
        DeterministicSecurityCap()
        .evaluate(
            values(candidates=(SECURITY_COLLECTION, candidates)),
            values(maximum_count=(INTEGER, 1)),
        )
        .get("selected")
        .value
    )
    assert capped == SecurityCollection(candidates.securities[:1])

    score = (
        WeightedScoreWithCeiling()
        .evaluate(
            values(
                values=(DECIMAL_LIST, (Decimal("100"), Decimal("80"))),
                weights=(DECIMAL_LIST, (Decimal("3"), Decimal("1"))),
            ),
            values(ceiling=(D, Decimal("90"))),
        )
        .get("score")
        .value
    )
    assert score == Decimal("90")
    verdict = (
        VerdictClassifier()
        .evaluate(
            values(score=(D, score)),
            values(
                pass_threshold=(D, Decimal("85")),
                watch_threshold=(D, Decimal("60")),
            ),
        )
        .get("verdict")
        .value
    )
    assert verdict == "PASS"


def test_event_window_and_expiration_selection_are_explicit_time_only() -> None:
    front = ExpirationCycle(FRONT, 16, True, False, AS_OF, EVIDENCE)
    back = ExpirationCycle(BACK, 51, True, False, AS_OF, EVIDENCE)
    event = earnings_event()
    assert (
        EarningsEventWindow()
        .evaluate(
            values(
                event=(EARNINGS_EVENT, event),
                front=(EXPIRATION_CYCLE, front),
                back=(EXPIRATION_CYCLE, back),
            ),
            values(require_confirmed=(B, True)),
        )
        .get("eligible")
        .value
        is True
    )

    selected = (
        ExpirationPairSelector()
        .evaluate(
            values(
                expirations=(
                    EXPIRATION_COLLECTION,
                    ExpirationCollection(AS_OF, (back, front)),
                ),
                event=(EARNINGS_EVENT, event),
            ),
            values(
                front_min_dte=(INTEGER, 7),
                front_max_dte=(INTEGER, 30),
                back_min_dte=(INTEGER, 31),
                back_max_dte=(INTEGER, 90),
            ),
        )
        .get("selected")
        .value
    )
    assert selected == ExpirationCollection(AS_OF, (front, back))

    unconfirmed = replace(event, confirmed=False)
    assert (
        EarningsEventWindow()
        .evaluate(
            values(
                event=(EARNINGS_EVENT, unconfirmed),
                front=(EXPIRATION_CYCLE, front),
                back=(EXPIRATION_CYCLE, back),
            ),
            values(require_confirmed=(B, True)),
        )
        .get("eligible")
        .value
        is False
    )


def test_liquidity_and_delta_selection_use_observed_contract_values() -> None:
    selected = (
        DeltaNearestLeg()
        .evaluate(
            values(
                contracts=(OPTION_COLLECTION, OptionCollection(chain().contracts)),
                expiration=(DATE, FRONT),
            ),
            values(option_type=(OPTION_TYPE, "call"), target_delta=(D, Decimal("0.31"))),
        )
        .get("contract")
        .value
    )
    assert isinstance(selected, OptionContract)
    assert selected.strike == Decimal("105")

    liquid = (
        OptionLegLiquidity()
        .evaluate(
            values(contract=(OPTION_CONTRACT, selected)),
            values(
                maximum_spread_ratio=(D, Decimal("0.25")),
                minimum_open_interest=(INTEGER, 100),
                minimum_volume=(INTEGER, 10),
            ),
        )
        .get("liquid")
        .value
    )
    assert liquid is True
    assert (
        OptionLegLiquidity()
        .evaluate(
            values(contract=(OPTION_CONTRACT, replace(selected, mark=None))),
            values(
                maximum_spread_ratio=(D, Decimal("0.25")),
                minimum_open_interest=(INTEGER, 100),
                minimum_volume=(INTEGER, 10),
            ),
        )
        .get("liquid")
        .value
        is False
    )


def test_dte_pair_projection_and_forward_factor_are_deterministic() -> None:
    front = ExpirationCycle(FRONT, 16, True, False, AS_OF, EVIDENCE)
    back = ExpirationCycle(BACK, 51, True, False, AS_OF, EVIDENCE)
    pair_selected = (
        DtePairSelector()
        .evaluate(
            values(
                expirations=(
                    EXPIRATION_COLLECTION,
                    ExpirationCollection(AS_OF, (back, front)),
                )
            ),
            values(
                front_min_dte=(INTEGER, 10),
                front_max_dte=(INTEGER, 30),
                back_min_dte=(INTEGER, 40),
                back_max_dte=(INTEGER, 90),
                minimum_gap_days=(INTEGER, 20),
                maximum_gap_days=(INTEGER, 60),
                target_front_dte=(INTEGER, 20),
                target_gap_days=(INTEGER, 35),
            ),
        )
        .get("selected")
    )
    projected = ExpirationPairProjection().evaluate(
        ComponentValues((("selected", pair_selected),)), ComponentValues(())
    )
    assert projected.get("front_expiration").value == FRONT
    assert projected.get("back_expiration").value == BACK

    implied = (
        ImpliedForwardVolatility()
        .evaluate(
            values(
                front_iv=(D, Decimal("0.48")),
                back_iv=(D, Decimal("0.4548992562461861547567860943472296")),
                front_dte=(INTEGER, 60),
                back_dte=(INTEGER, 90),
            ),
            ComponentValues(()),
        )
        .get("implied_forward_iv")
    )
    factor = (
        ForwardFactor()
        .evaluate(
            values(
                front_ex_earnings_iv=(D, Decimal("0.48")),
                implied_forward_iv=(D, implied.value),
            ),
            ComponentValues(()),
        )
        .get("factor")
        .value
    )
    assert factor.quantize(Decimal("0.00000001")) == Decimal("0.20000000")


def test_calendar_vertical_double_calendar_and_debit_are_replay_stable() -> None:
    option_chain = chain()
    calendar_inputs = values(
        chain=(OPTION_CHAIN, option_chain),
        front_expiration=(DATE, FRONT),
        back_expiration=(DATE, BACK),
        strike=(D, Decimal("100")),
    )
    calendar = (
        CalendarStructure()
        .evaluate(calendar_inputs, values(option_type=(OPTION_TYPE, "call")))
        .get("structure")
        .value
    )
    replay = (
        CalendarStructure()
        .evaluate(calendar_inputs, values(option_type=(OPTION_TYPE, "call")))
        .get("structure")
        .value
    )
    assert isinstance(calendar, OptionStructure)
    assert calendar == replay
    assert calendar.identity == replay.identity

    debit = OptionStructureDebit().evaluate(
        values(structure=(OPTION_STRUCTURE, calendar)), ComponentValues(())
    )
    assert debit.get("mid_debit").value == Decimal("1")
    assert debit.get("conservative_debit").value == Decimal("1.2")

    nearest = (
        NearestCommonStrikeCalendar()
        .evaluate(
            values(
                chain=(OPTION_CHAIN, option_chain),
                front_expiration=(DATE, FRONT),
                back_expiration=(DATE, BACK),
                target_strike=(D, Decimal("103")),
            ),
            values(option_type=(OPTION_TYPE, "call")),
        )
        .get("structure")
        .value
    )
    assert isinstance(nearest, OptionStructure)
    assert {leg.contract.strike for leg in nearest.legs} == {Decimal("105")}

    vertical = (
        VerticalStructure()
        .evaluate(
            values(chain=(OPTION_CHAIN, option_chain), expiration=(DATE, FRONT)),
            values(
                option_type=(OPTION_TYPE, "call"),
                long_delta_target=(D, Decimal("0.55")),
                short_delta_target=(D, Decimal("0.30")),
            ),
        )
        .get("structure")
        .value
    )
    assert isinstance(vertical, OptionStructure)
    assert {leg.contract.strike for leg in vertical.legs} == {
        Decimal("100"),
        Decimal("105"),
    }

    double = (
        DoubleCalendarStructure()
        .evaluate(
            values(
                chain=(OPTION_CHAIN, option_chain),
                front_expiration=(DATE, FRONT),
                back_expiration=(DATE, BACK),
            ),
            values(
                put_delta_target=(D, Decimal("-0.30")),
                call_delta_target=(D, Decimal("0.55")),
            ),
        )
        .get("structures")
        .value
    )
    assert isinstance(double, tuple)
    assert len(double) == 2
    assert all(isinstance(item, OptionStructure) for item in double)


def test_components_fail_closed_on_missing_matches_and_invalid_parameters() -> None:
    with pytest.raises(ComponentContractError, match="no option contract"):
        DeltaNearestLeg().evaluate(
            values(
                contracts=(OPTION_COLLECTION, OptionCollection(chain().contracts)),
                expiration=(DATE, date(2027, 1, 1)),
            ),
            values(option_type=(OPTION_TYPE, "call"), target_delta=(D, Decimal("0.3"))),
        )
    with pytest.raises(ComponentContractError, match="positive"):
        DeterministicSecurityCap().evaluate(
            values(candidates=(SECURITY_COLLECTION, SecurityCollection((security(),)))),
            values(maximum_count=(INTEGER, 0)),
        )


def test_extracted_components_have_no_forbidden_dependencies_or_state() -> None:
    path = Path(__file__).parents[2] / "strategies" / "stonk_components.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not roots & {
        "providers",
        "observation",
        "portfolio",
        "ranking",
        "execution_planning",
        "infrastructure",
        "requests",
        "sqlalchemy",
    }
    assert "today(" not in path.read_text(encoding="utf-8")
    for plugin in STONK_STRATEGY_PLUGINS:
        for component in plugin.components:
            assert not hasattr(component, "__dict__")


def test_every_extracted_component_is_documented() -> None:
    document = (
        Path(__file__).parents[2] / "docs" / "migration" / "stonk-shared-components.md"
    ).read_text(encoding="utf-8")
    for plugin in STONK_STRATEGY_PLUGINS:
        for component in plugin.components:
            assert f"`{component.definition.name}`" in document
    assert "no Stonk ranker was copied" in document
    assert "Portfolio Engine" in document
