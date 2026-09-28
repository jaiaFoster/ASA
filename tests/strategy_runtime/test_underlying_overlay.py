from dataclasses import replace
from decimal import Decimal

import pytest

from domain import (
    CanonicalInstrumentIdentity,
    InstrumentKind,
    OptionLeg,
    OptionLegPosition,
    OptionType,
    SecurityAssetType,
    UnknownReason,
)
from strategy_runtime.underlying_overlay import (
    OptionOverlayPosition,
    UnderlyingExposureKind,
    UnderlyingExposureLeg,
    overlay_reference_value,
)
from tests.strategies.test_cboe_put_strategy import SPX, _put


def _short_call():  # type: ignore[no-untyped-def]
    put = _put(Decimal("5000"))
    call = replace(put, option_type=OptionType.CALL)
    return OptionLeg(call, OptionLegPosition.SHORT, Decimal(1), "short_call")


def test_p09_nontradable_index_overlay_is_analytical_not_broker_executable() -> None:
    exposure = UnderlyingExposureLeg(
        SPX.instrument,
        Decimal(1),
        UnderlyingExposureKind.INDEX_TOTAL_RETURN,
        False,
    )
    position = OptionOverlayPosition(exposure, (_short_call(),))
    assert position.broker_executable is False
    assert overlay_reference_value(position, underlying_value=Decimal("5000")) == Decimal("4949.5")


def test_p09_rejects_false_index_executability_and_proxy_identity() -> None:
    with pytest.raises(ValueError, match="cannot be broker executable"):
        UnderlyingExposureLeg(
            SPX.instrument,
            Decimal(1),
            UnderlyingExposureKind.INDEX_TOTAL_RETURN,
            True,
        )
    proxy = replace(
        SPX.instrument,
        identity=CanonicalInstrumentIdentity("test", "proxy"),
        kind=InstrumentKind.EQUITY,
        display_symbol="SPY",
    )
    exposure = UnderlyingExposureLeg(
        proxy, Decimal(1), UnderlyingExposureKind.TRADABLE_UNDERLYING, True
    )
    with pytest.raises(ValueError, match="share the exposure instrument"):
        OptionOverlayPosition(exposure, (_short_call(),))


def test_p09_is_order_deterministic_and_exact_leg_identity_bearing() -> None:
    exposure = UnderlyingExposureLeg(
        SPX.instrument, Decimal(1), UnderlyingExposureKind.INDEX_TOTAL_RETURN, False
    )
    first = _short_call()
    second = replace(first, quantity=Decimal(2), role="short_call_two")
    left = OptionOverlayPosition(exposure, (first, second))
    right = OptionOverlayPosition(exposure, (second, first))
    assert left.option_legs == right.option_legs
    assert left.identity == right.identity


def test_p09_value_missing_inputs_remain_typed_unknown() -> None:
    exposure = UnderlyingExposureLeg(
        SPX.instrument, Decimal(1), UnderlyingExposureKind.INDEX_TOTAL_RETURN, False
    )
    position = OptionOverlayPosition(exposure, (_short_call(),))
    assert overlay_reference_value(position, underlying_value=None) == UnknownReason(
        "missing_underlying_exposure_value"
    )
    no_quote = replace(_short_call(), contract=replace(_short_call().contract, bid=None))
    assert overlay_reference_value(
        OptionOverlayPosition(exposure, (no_quote,)), underlying_value=Decimal("5000")
    ) == UnknownReason("missing_option_overlay_midpoint")


def test_p09_generic_tradable_underlying_fixture_proves_reuse() -> None:
    security = replace(
        SPX,
        instrument=replace(
            SPX.instrument,
            identity=CanonicalInstrumentIdentity("test", "generic"),
            kind=InstrumentKind.EQUITY,
            display_symbol="GEN",
        ),
        symbol="GEN",
        asset_type=SecurityAssetType.EQUITY,
    )
    contract = replace(_short_call().contract, underlying=security)
    exposure = UnderlyingExposureLeg(
        security.instrument,
        Decimal("10"),
        UnderlyingExposureKind.TRADABLE_UNDERLYING,
        True,
    )
    position = OptionOverlayPosition(
        exposure,
        (OptionLeg(contract, OptionLegPosition.SHORT, Decimal(1), "generic_overlay"),),
    )
    assert position.broker_executable is True
    assert "BXM" not in type(position).__name__
