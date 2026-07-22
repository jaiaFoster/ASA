from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from analytics.errors import MissingImpliedVolatilityError, NoMatchingContractError
from analytics.forward_factor import (
    FORWARD_FACTOR_ANALYTICS_COMPUTATIONS,
    FORWARD_FACTOR_ANALYTICS_REGISTRY,
    compute_days_to_expiration,
    compute_option_implied_volatility,
)
from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    Instrument,
    InstrumentKind,
    OptionChain,
    OptionContract,
    OptionType,
    Security,
    SecurityAssetType,
)

OBSERVED_AT = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "test-evidence"),)


def _security() -> Security:
    return Security(
        Instrument(CanonicalInstrumentIdentity("figi", "figi-AAPL"), InstrumentKind.EQUITY, "AAPL", "USD"),
        "AAPL",
        SecurityAssetType.EQUITY,
        "XNAS",
    )


def _contract(expiration: date, strike: str, implied_volatility: Decimal | None) -> OptionContract:
    return OptionContract(
        CanonicalInstrumentIdentity("asa-option-v1", f"opt-{strike}"),
        _security(),
        expiration,
        Decimal(strike),
        OptionType.CALL,
        Decimal("1.90"),
        Decimal("2.10"),
        Decimal("2.00"),
        100,
        500,
        Decimal("0.35"),
        Decimal("0.01"),
        Decimal("-0.02"),
        Decimal("0.03"),
        Decimal("0.01"),
        implied_volatility,
        OBSERVED_AT,
        EVIDENCE,
    )


def _chain(*contracts: OptionContract) -> OptionChain:
    return OptionChain("test-chain", _security(), OBSERVED_AT, contracts, EVIDENCE)


class TestComputeDaysToExpiration:
    def test_computes_calendar_days(self) -> None:
        value = compute_days_to_expiration(
            {"expiration": date(2026, 9, 21), "as_of": date(2026, 7, 22)}
        )
        assert value == Decimal(61)

    def test_same_day_is_zero(self) -> None:
        value = compute_days_to_expiration({"expiration": date(2026, 7, 22), "as_of": date(2026, 7, 22)})
        assert value == Decimal(0)

    def test_expiration_before_as_of_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot precede"):
            compute_days_to_expiration({"expiration": date(2026, 7, 1), "as_of": date(2026, 7, 22)})


class TestComputeOptionImpliedVolatility:
    def test_extracts_the_canonical_field_directly(self) -> None:
        chain = _chain(_contract(date(2026, 9, 21), "105", Decimal("0.35")))
        value = compute_option_implied_volatility(
            {"chain": chain, "expiration": date(2026, 9, 21), "strike": Decimal("105"), "option_type": OptionType.CALL}
        )
        assert value == Decimal("0.35")

    def test_no_matching_contract_raises(self) -> None:
        chain = _chain(_contract(date(2026, 9, 21), "105", Decimal("0.35")))
        with pytest.raises(NoMatchingContractError):
            compute_option_implied_volatility(
                {"chain": chain, "expiration": date(2026, 9, 21), "strike": Decimal("110"), "option_type": OptionType.CALL}
            )

    def test_missing_implied_volatility_raises(self) -> None:
        chain = _chain(_contract(date(2026, 9, 21), "105", None))
        with pytest.raises(MissingImpliedVolatilityError):
            compute_option_implied_volatility(
                {"chain": chain, "expiration": date(2026, 9, 21), "strike": Decimal("105"), "option_type": OptionType.CALL}
            )

    def test_no_black_scholes_solving_the_field_is_read_verbatim(self) -> None:
        """Confirms this reads the provider-reported field directly rather
        than deriving it -- the whole point of this ticket's scoping
        decision (see analytics/forward_factor.py's module docstring).
        """
        chain = _chain(_contract(date(2026, 9, 21), "105", Decimal("0.9999")))
        value = compute_option_implied_volatility(
            {"chain": chain, "expiration": date(2026, 9, 21), "strike": Decimal("105"), "option_type": OptionType.CALL}
        )
        assert value == Decimal("0.9999")


class TestRegistration:
    def test_both_features_are_registered(self) -> None:
        assert FORWARD_FACTOR_ANALYTICS_REGISTRY.registered_ids() == (
            "days_to_expiration",
            "option_implied_volatility",
        )

    def test_every_registered_feature_has_a_computation(self) -> None:
        for feature_id in FORWARD_FACTOR_ANALYTICS_REGISTRY.registered_ids():
            assert feature_id in FORWARD_FACTOR_ANALYTICS_COMPUTATIONS
