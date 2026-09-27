"""X04 (STRATEGY-PRODUCTION-001 SP-01B): provider-neutral rate facts from Treasury bill rates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from domain import (
    EvidenceKind,
    EvidenceReference,
    InstrumentKind,
    MarketCapability,
    MarketDataRequestContext,
    MarketDataSubject,
    MarketDataSubjectType,
    ProviderAddressProjection,
    RateBasis,
    RateObservation,
    deserialize_market_data,
    serialize_market_data,
)
from domain.values import DomainInvariantError
from market_data import CapabilityRequest, load_market_data_config
from market_data.factory import ProviderDependencies
from market_data.providers import ProviderErrorCode, RequestBudgetAuthorization
from market_data.rate_series import RATE_SERIES, rate_series_instrument
from market_data.transport import ReadOnlyHttpRequest, ReadOnlyHttpResponse
from market_data.us_treasury import (
    UsTreasuryProvider,
    parse_bill_rate_feed,
    publication_effective_time,
)
from screening.live_context import build_capability_subject

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "us_treasury"
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "reference:rates"),)
SEPTEMBER = (FIXTURES / "daily_treasury_bill_rates_202609.xml").read_text()
AUGUST = (FIXTURES / "daily_treasury_bill_rates_202608.xml").read_text()


@dataclass(frozen=True)
class Clock:
    value: datetime

    def now(self) -> datetime:
        return self.value


class Budget:
    def authorize(
        self, provider_id: str, capability: MarketCapability, request_units: int
    ) -> RequestBudgetAuthorization:
        return RequestBudgetAuthorization("budget", provider_id, request_units, 1)


class Transport:
    def __init__(self, bodies: dict[str, str]) -> None:
        self.bodies = bodies
        self.requests: list[ReadOnlyHttpRequest] = []

    def get(self, request: ReadOnlyHttpRequest) -> ReadOnlyHttpResponse:
        self.requests.append(request)
        month = dict(request.query)["field_tdr_date_value_month"]
        return ReadOnlyHttpResponse(200, {"text": self.bodies[month]}, (), 5, f"treasury-{month}")


def _provider(transport: Transport, now: datetime) -> UsTreasuryProvider:
    config = next(
        item
        for item in load_market_data_config({"ASA_US_TREASURY_ENABLED": "true"}).providers
        if item.provider_id == "us_treasury"
    )
    return UsTreasuryProvider(config, ProviderDependencies(transport, Clock(now), Budget()))


def _request(series_id: str, start: datetime, end: datetime) -> CapabilityRequest:
    subject = MarketDataSubject(
        rate_series_instrument(series_id),
        MarketDataSubjectType.INSTRUMENT,
        MarketCapability.RATE_OBSERVATION_V1,
        MarketDataRequestContext(
            start,
            end,
            ("value",),
            (
                ProviderAddressProjection(
                    "us_treasury",
                    "v1",
                    "symbol",
                    series_id,
                    start - timedelta(days=1),
                    None,
                    EVIDENCE,
                ),
            ),
            EVIDENCE,
        ),
    )
    return CapabilityRequest(
        MarketCapability.RATE_OBSERVATION_V1, (subject,), start, end, ("value",), 86400 * 5
    )


def _authorization() -> RequestBudgetAuthorization:
    return RequestBudgetAuthorization("budget", "us_treasury", 1, 1)


def test_feed_parsing_percent_values_and_blank_fields() -> None:
    rows = parse_bill_rate_feed(SEPTEMBER)
    assert rows[date(2026, 9, 1)]["ROUND_B1_CLOSE_4WK_2"] == Decimal("3.69")
    assert "ROUND_B1_CLOSE_4WK_2" not in rows[date(2026, 9, 3)]  # blank is absent, never zero


def test_feed_parser_rejects_dtd_and_entities() -> None:
    with pytest.raises(ValueError):
        parse_bill_rate_feed('<!DOCTYPE x [<!ENTITY a "b">]><feed/>')


def test_bank_discount_rate_is_point_in_time_decimal_fraction() -> None:
    # 2026-09-02 at 18:00 ET: the 09-02 close (16:00 ET) is published and eligible.
    end = datetime(2026, 9, 2, 22, tzinfo=UTC)
    transport = Transport({"202609": SEPTEMBER})
    result = _provider(transport, end).fetch(
        _request("US_TBILL_4WK_BANK_DISCOUNT", end - timedelta(days=3), end), _authorization()
    )
    assert result.error is None
    value = result.observations[0].value
    assert isinstance(value, RateObservation)
    assert (value.basis, value.tenor_days, value.value, value.effective_date) == (
        RateBasis.BANK_DISCOUNT,
        28,
        Decimal("0.0370"),
        date(2026, 9, 2),
    )
    assert result.observations[0].effective_time == publication_effective_time(date(2026, 9, 2))


def test_no_lookahead_before_publication_close() -> None:
    # 11:00 ET on 09-02: the 09-02 value is not yet published; 09-01 is returned.
    end = datetime(2026, 9, 2, 15, tzinfo=UTC)
    transport = Transport({"202609": SEPTEMBER})
    result = _provider(transport, end).fetch(
        _request("US_TBILL_13WK_BANK_DISCOUNT", end - timedelta(days=3), end), _authorization()
    )
    value = result.observations[0].value
    assert isinstance(value, RateObservation)
    assert value.effective_date == date(2026, 9, 1)
    assert value.value == Decimal("0.0378")


def test_month_boundary_reads_previous_month_and_blank_is_not_a_value() -> None:
    end = datetime(2026, 9, 1, 12, tzinfo=UTC)
    transport = Transport({"202609": SEPTEMBER, "202608": AUGUST})
    result = _provider(transport, end).fetch(
        _request("US_TBILL_4WK_BANK_DISCOUNT", end - timedelta(days=4), end), _authorization()
    )
    value = result.observations[0].value
    assert isinstance(value, RateObservation) and value.effective_date == date(2026, 8, 31)
    assert len(transport.requests) == 2


def test_blank_published_value_is_no_data_not_zero() -> None:
    end = datetime(2026, 9, 3, 22, tzinfo=UTC)
    transport = Transport({"202609": SEPTEMBER})
    result = _provider(transport, end).fetch(
        _request("US_TBILL_4WK_BANK_DISCOUNT", datetime(2026, 9, 3, 12, tzinfo=UTC), end),
        _authorization(),
    )
    assert result.error is not None and result.error.code is ProviderErrorCode.NO_DATA


def test_unsourced_series_is_unsupported_never_substituted() -> None:
    end = datetime(2026, 9, 2, 22, tzinfo=UTC)
    result = _provider(Transport({}), end).fetch(
        _request("SP500_DIVIDEND_YIELD", end - timedelta(days=3), end), _authorization()
    )
    assert result.error is not None
    assert result.error.code is ProviderErrorCode.UNSUPPORTED_SYMBOL


def test_rate_observation_contract() -> None:
    instrument = rate_series_instrument("US_TBILL_4WK_BANK_DISCOUNT")
    assert instrument.kind is InstrumentKind.RATE
    value = RateObservation(
        instrument, RateBasis.BANK_DISCOUNT, 28, Decimal("0.0369"), date(2026, 9, 1)
    )
    assert deserialize_market_data(serialize_market_data(value)) == value
    with pytest.raises(DomainInvariantError):
        RateObservation(instrument, RateBasis.BANK_DISCOUNT, 28, Decimal("3.69"), date(2026, 9, 1))
    assert RATE_SERIES["SP500_DIVIDEND_YIELD"].basis is RateBasis.DIVIDEND_YIELD


def test_treasury_is_credential_free_opt_in_and_rate_subjects_are_rate_kind() -> None:
    enabled = load_market_data_config({"ASA_US_TREASURY_ENABLED": "true"})
    config = next(item for item in enabled.providers if item.provider_id == "us_treasury")
    assert config.enabled and config.credential is None
    default = load_market_data_config({})
    assert not next(item for item in default.providers if item.provider_id == "us_treasury").enabled
    subject = build_capability_subject(
        "US_TBILL_4WK_BANK_DISCOUNT",
        MarketCapability.RATE_OBSERVATION_V1,
        datetime(2026, 9, 2, 22, tzinfo=UTC),
    )
    assert subject.canonical_instrument.kind is InstrumentKind.RATE
    assert subject.request_context.required_fields == ("value",)


def test_other_tenors_null_cells_and_malformed_cells_are_per_cell() -> None:
    rows = parse_bill_rate_feed(SEPTEMBER)
    assert rows[date(2026, 9, 1)]["ROUND_B1_CLOSE_8WK_2"] == Decimal("3.74")
    assert "ROUND_B1_CLOSE_26WK_2" not in rows[date(2026, 9, 2)]  # m:null="true"
    assert "ROUND_B1_CLOSE_26WK_2" not in rows[date(2026, 9, 3)]  # malformed cell only
    assert rows[date(2026, 9, 3)]["ROUND_B1_CLOSE_13WK_2"] == Decimal("3.80")
    end = datetime(2026, 9, 2, 23, tzinfo=UTC)
    result = _provider(Transport({"202609": SEPTEMBER}), end).fetch(
        _request("US_TBILL_26WK_BANK_DISCOUNT", end - timedelta(days=3), end), _authorization()
    )
    value = result.observations[0].value
    assert isinstance(value, RateObservation)
    assert (value.effective_date, value.tenor_days) == (date(2026, 9, 1), 182)


def test_out_of_contract_value_is_a_typed_schema_error_not_an_exception() -> None:
    feed = SEPTEMBER.replace(
        '<d:ROUND_B1_CLOSE_8WK_2 m:type="Edm.Double">3.75</d:ROUND_B1_CLOSE_8WK_2>',
        '<d:ROUND_B1_CLOSE_8WK_2 m:type="Edm.Double">150</d:ROUND_B1_CLOSE_8WK_2>',
    )
    end = datetime(2026, 9, 2, 23, tzinfo=UTC)
    result = _provider(Transport({"202609": feed}), end).fetch(
        _request("US_TBILL_8WK_BANK_DISCOUNT", end - timedelta(days=1), end), _authorization()
    )
    assert result.error is not None
    assert result.error.code is ProviderErrorCode.SCHEMA_MISMATCH


def test_availability_is_the_labelled_conservative_assumption() -> None:
    from market_data.us_treasury import AVAILABILITY_ASSUMPTION_ID

    assert AVAILABILITY_ASSUMPTION_ID == "IA-RATE-01"
    # 18:00 ET on 2026-09-02 (EDT) is 22:00 UTC; one minute earlier sees 09-01.
    end = datetime(2026, 9, 2, 21, 59, tzinfo=UTC)
    result = _provider(Transport({"202609": SEPTEMBER}), end).fetch(
        _request("US_TBILL_4WK_BANK_DISCOUNT", end - timedelta(days=3), end), _authorization()
    )
    value = result.observations[0].value
    assert isinstance(value, RateObservation) and value.effective_date == date(2026, 9, 1)


def test_projections_keep_equity_subject_identity_and_scope_rate_subjects() -> None:
    now = datetime(2026, 9, 2, 22, tzinfo=UTC)
    equity = build_capability_subject("AAPL", MarketCapability.REAL_TIME_QUOTE_V1, now)
    providers = {item.provider_id for item in equity.request_context.provider_address_projections}
    assert "us_treasury" not in providers
    rate = build_capability_subject(
        "US_TBILL_4WK_BANK_DISCOUNT", MarketCapability.RATE_OBSERVATION_V1, now
    )
    assert {item.provider_id for item in rate.request_context.provider_address_projections} == {
        "us_treasury"
    }
