"""ANALYTICS-002 success criterion: "Forward Factor consumes analytics
outputs without additional calculations."

This proves it end-to-end against the real, unmodified Forward Factor
manifest -- analytics/ computes front_iv/back_iv/front_dte/back_dte, and
those values are passed directly into the manifest's execution context with
no further math performed anywhere in this test.

Lives under tests/ (not analytics/) because it imports strategies/ purely
to validate against the real manifest -- analytics/ itself must not import
strategies/ (tests/architecture/test_analytics_boundaries.py), and this
file is exactly why: it's the integration seam between the two, not part
of the reusable package.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from analytics.expiration_selection import ExpirationCandidate, select_expiration_pair
from analytics.forward_factor import compute_days_to_expiration, compute_option_implied_volatility
from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    ExpirationCollection,
    ExpirationCycle,
    Instrument,
    InstrumentKind,
    OptionChain,
    OptionContract,
    OptionType,
    Security,
    SecurityAssetType,
)
from strategies import (
    CORE_COMPONENTS,
    FORWARD_FACTOR_CALENDAR_MANIFEST,
    STONK_STRATEGY_PLUGINS,
    compile_strategy_graph,
    execute_strategy_graph,
)
from strategies.plugins import build_plugin_registry
from strategies.stonk_components import D, EXPIRATION_COLLECTION, OPTION_CHAIN
from strategies.type_system import ComponentValues, StrategyTypeReference, TypedValue

AS_OF = date(2026, 7, 22)
OBSERVED_AT = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
FRONT_EXPIRATION = date(2026, 9, 21)  # 61 days out
BACK_EXPIRATION = date(2026, 10, 21)  # 91 days out
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "integration-test"),)


def _security() -> Security:
    return Security(
        Instrument(CanonicalInstrumentIdentity("figi", "figi-AAPL"), InstrumentKind.EQUITY, "AAPL", "USD"),
        "AAPL",
        SecurityAssetType.EQUITY,
        "XNAS",
    )


def _contract(expiration: date, strike: str, option_type: OptionType, iv: str) -> OptionContract:
    mark = Decimal("2.00")
    return OptionContract(
        CanonicalInstrumentIdentity("asa-option-v1", f"{expiration}-{strike}-{option_type.value}"),
        _security(),
        expiration,
        Decimal(strike),
        option_type,
        mark - Decimal("0.10"),
        mark + Decimal("0.10"),
        mark,
        100,
        500,
        Decimal("0.35"),
        Decimal("0.01"),
        Decimal("-0.02"),
        Decimal("0.03"),
        Decimal("0.01"),
        Decimal(iv),
        OBSERVED_AT,
        EVIDENCE,
    )


def test_analytics_outputs_feed_the_real_manifest_with_zero_additional_math() -> None:
    chain = OptionChain(
        "integration-chain",
        _security(),
        OBSERVED_AT,
        (
            _contract(FRONT_EXPIRATION, "105", OptionType.CALL, "0.48"),
            _contract(BACK_EXPIRATION, "105", OptionType.CALL, "0.4548992562461861547567860943472296"),
            _contract(FRONT_EXPIRATION, "95", OptionType.PUT, "0.50"),
            _contract(BACK_EXPIRATION, "95", OptionType.PUT, "0.47"),
        ),
        EVIDENCE,
    )

    # Step 1: analytics selects the front/back expiration pair -- the same
    # DTE policy the manifest's own (separate, frozen) dte_pair_selector uses.
    candidates = (
        ExpirationCandidate(FRONT_EXPIRATION, 61),
        ExpirationCandidate(BACK_EXPIRATION, 91),
    )
    selected = select_expiration_pair(
        candidates,
        front_min_dte=35,
        front_max_dte=90,
        back_min_dte=49,
        back_max_dte=139,
        minimum_gap_days=14,
        maximum_gap_days=49,
        target_front_dte=60,
        target_gap_days=30,
    )
    assert selected is not None
    front, back = selected

    # Step 2: analytics computes DTE and extracts IV -- both read/derived
    # directly, no further calculation performed here or afterward.
    front_dte = compute_days_to_expiration({"expiration": front.expiration_date, "as_of": AS_OF})
    back_dte = compute_days_to_expiration({"expiration": back.expiration_date, "as_of": AS_OF})
    front_iv = compute_option_implied_volatility(
        {"chain": chain, "expiration": front.expiration_date, "strike": Decimal("105"), "option_type": OptionType.CALL}
    )
    back_iv = compute_option_implied_volatility(
        {"chain": chain, "expiration": back.expiration_date, "strike": Decimal("105"), "option_type": OptionType.CALL}
    )

    # Step 3: those four analytics outputs are passed directly into the
    # real, unmodified manifest's execution context -- verbatim, no math.
    expirations = ExpirationCollection(
        AS_OF,
        (
            ExpirationCycle(front.expiration_date, front.days_to_expiration, True, False, AS_OF, EVIDENCE),
            ExpirationCycle(back.expiration_date, back.days_to_expiration, True, False, AS_OF, EVIDENCE),
        ),
    )
    context = ComponentValues(
        (
            ("expiration_select.expirations", TypedValue(EXPIRATION_COLLECTION, expirations)),
            ("double_calendar.chain", TypedValue(OPTION_CHAIN, chain)),
            ("forward_iv.front_iv", TypedValue(D, front_iv)),
            ("forward_iv.back_iv", TypedValue(D, back_iv)),
            ("forward_iv.front_dte", TypedValue(StrategyTypeReference("Integer", "1.0.0"), int(front_dte))),
            ("forward_iv.back_dte", TypedValue(StrategyTypeReference("Integer", "1.0.0"), int(back_dte))),
            ("factor.front_ex_earnings_iv", TypedValue(D, front_iv)),
        )
    )
    registry = build_plugin_registry(CORE_COMPONENTS, STONK_STRATEGY_PLUGINS)
    graph = compile_strategy_graph(FORWARD_FACTOR_CALENDAR_MANIFEST, registry)
    result = execute_strategy_graph(graph, context)

    assert result.outputs.get("verdict").value in {"PASS", "WATCH", "FAIL"}
    assert result.outputs.get("forward_factor").value is not None
