from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from analytics.features import DerivedFactSet
from domain import (
    CanonicalInstrumentIdentity,
    OHLCVBar,
    OHLCVSeries,
    OptionType,
    SecurityMasterRecord,
    SecurityType,
    UnknownReason,
)
from strategies.manifest_version_pins import version_pin_violations
from strategies.zhan_manifest import STRATEGY_ID, ZHAN_MANIFEST
from strategies.zhan_planning import rate_demand, security_master_demand
from strategies.zhan_portfolio import ZhanSubjectCandidate
from strategy_runtime.adapters.zhan import ZHAN_CONTRACT
from strategy_runtime.adapters.zhan_portfolio import (
    ZhanSubjectMaterialization,
    materialize_zhan_family,
)
from strategy_runtime.adapters.zhan_subject_first import (
    _formation_close,
    _last_session_of_month,
    _security_master_is_effective,
    build_zhan_subject_first_adapter,
)
from strategy_runtime.context import RuntimeContext
from strategy_runtime.cross_sectional_portfolio import PortfolioBookSide
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.manifest_contract import validate_manifest_contract
from tests.market_data.test_index_dividends_security_master_x07 import AAPL
from tests.strategies.test_cboe_put_strategy import _put

AS_OF = datetime(2026, 9, 30, 20, tzinfo=UTC)
EXPIRY = date(2026, 11, 20)


def _candidate(index: int, *, expiration: date = EXPIRY) -> ZhanSubjectCandidate:
    spot = Decimal(10 + index * 10)
    put = replace(
        _put(spot),
        option_contract_id=CanonicalInstrumentIdentity("occ", f"S{index}-{expiration}-P"),
        expiration=expiration,
        strike=spot,
        bid=Decimal("1"),
        ask=Decimal("1.2"),
        delta=Decimal("-0.5"),
        root=None,
        settlement_style=None,
    )
    call = replace(
        put,
        option_contract_id=CanonicalInstrumentIdentity("occ", f"S{index}-{expiration}-C"),
        option_type=OptionType.CALL,
        delta=Decimal("0.5"),
    )
    return ZhanSubjectCandidate(
        f"S{index}",
        AS_OF,
        f"evidence:{index}",
        spot,
        SecurityType.COMMON_STOCK,
        Decimal(1_000_000 + index),
        Decimal("0.04"),
        -spot.ln(),
        (call, put),
        "PASS",
    )


def test_manifest_contract_and_assumption_pin_are_complete() -> None:
    assert ZHAN_CONTRACT.strategy_id == STRATEGY_ID
    validate_manifest_contract(ZHAN_MANIFEST, ZHAN_CONTRACT)
    assert version_pin_violations((ZHAN_MANIFEST,)) == ()
    assert {item.name for item in ZHAN_MANIFEST.required_market_capabilities} >= {
        "option_chain_v1",
        "security_master_v1",
        "rate_observation_v1",
    }
    assert not rate_demand(AS_OF).required
    assert not security_master_demand(AS_OF).required


def test_zhan_family_builds_exact_shared_stock_vw_long_short_p12() -> None:
    result = materialize_zhan_family({f"S{i}": _candidate(i) for i in range(10)})
    passing = [item for item in result.values() if item.state == "PASS"]
    assert len(passing) == 2
    assert {item.quantile for item in passing} == {1, 10}
    portfolios = {item.portfolio.identity for item in passing if item.portfolio is not None}
    assert len(portfolios) == 1
    portfolio = next(item.portfolio for item in passing if item.portfolio is not None)
    assert portfolio is not None
    assert {item.side for item in portfolio.members} == {
        PortfolioBookSide.LONG,
        PortfolioBookSide.SHORT,
    }
    assert all(item.weight == Decimal(1) for item in portfolio.members)


def test_modal_maturity_tie_and_missing_rate_remain_typed_unknown() -> None:
    first = _candidate(0)
    second = _candidate(1, expiration=date(2026, 12, 18))
    tied = materialize_zhan_family({"S0": first, "S1": second})
    assert {item.reason for item in tied.values()} == {"G_ZHAN_MODAL_MATURITY_UNKNOWN"}

    missing_rate = materialize_zhan_family({"S0": replace(first, risk_free_rate=None)})
    assert missing_rate["S0"].state == "UNKNOWN"
    assert missing_rate["S0"].reason == "G_ZHAN_NO_ARBITRAGE_UNKNOWN"


def test_frozen_stock_price_and_pair_gate_reason_codes_remain_distinct() -> None:
    candidate = _candidate(0)
    assert materialize_zhan_family(
        {"S0": replace(candidate, security_type=None)}
    )["S0"].reason == "G_ZHAN_COMMON_STOCK_UNKNOWN"
    assert materialize_zhan_family(
        {"S0": replace(candidate, security_type=SecurityType.ETF)}
    )["S0"].reason == "G_ZHAN_COMMON_STOCK_FAIL"
    assert materialize_zhan_family(
        {"S0": replace(candidate, spot=Decimal("4.99"))}
    )["S0"].reason == "G_ZHAN_PRICE_MIN_FAIL"

    call, _put_contract = candidate.contracts
    assert materialize_zhan_family({"S0": replace(candidate, contracts=(call,))})[
        "S0"
    ].reason == "G_ZHAN_CALL_AND_PUT_FAIL"
    no_arb = replace(call, bid=Decimal("20"), ask=Decimal("21"))
    paired_put = replace(_put_contract, bid=Decimal("1"), ask=Decimal("1.2"))
    assert materialize_zhan_family(
        {"S0": replace(candidate, contracts=(no_arb, paired_put))}
    )["S0"].reason == "G_ZHAN_NO_ARBITRAGE_FAIL"


def test_atm_tie_is_ambiguous_not_arbitrarily_selected() -> None:
    candidate = _candidate(0)
    call, put = candidate.contracts
    lower_call = replace(
        call, strike=Decimal(9), option_contract_id=CanonicalInstrumentIdentity("occ", "lower-c")
    )
    lower_put = replace(
        put, strike=Decimal(9), option_contract_id=CanonicalInstrumentIdentity("occ", "lower-p")
    )
    upper_call = replace(
        call, strike=Decimal(11), option_contract_id=CanonicalInstrumentIdentity("occ", "upper-c")
    )
    upper_put = replace(
        put, strike=Decimal(11), option_contract_id=CanonicalInstrumentIdentity("occ", "upper-p")
    )
    result = materialize_zhan_family(
        {"S0": replace(candidate, contracts=(lower_call, lower_put, upper_call, upper_put))}
    )
    assert result["S0"] == replace(result["S0"], state="UNKNOWN", reason="AMBIGUOUS_SELECTION")


def test_disagreeing_moneyness_ratios_remain_typed_unknown() -> None:
    candidate = _candidate(0)
    call, put = candidate.contracts
    strike = Decimal("8.2")
    result = materialize_zhan_family(
        {
            "S0": replace(
                candidate,
                contracts=(replace(call, strike=strike), replace(put, strike=strike)),
            )
        }
    )
    assert result["S0"].state == "UNKNOWN"
    assert result["S0"].reason == "G_ZHAN_MONEYNESS_UNKNOWN"


def test_missing_quote_or_liquidity_evidence_is_unknown_but_valid_failure_is_excluded() -> None:
    candidate = _candidate(0)
    call, put = candidate.contracts
    missing = materialize_zhan_family(
        {"S0": replace(candidate, contracts=(replace(call, volume=None), put))}
    )
    assert missing["S0"].state == "UNKNOWN"
    assert missing["S0"].reason == "G_ZHAN_OPTION_QUOTE_UNKNOWN"

    invalid = materialize_zhan_family(
        {"S0": replace(candidate, contracts=(replace(call, volume=0), replace(put, volume=0)))}
    )
    assert invalid["S0"].state == "EXCLUDED"
    assert invalid["S0"].reason == "G_ZHAN_OPTION_QUOTE_FAIL"


def test_monthly_formation_cadence_and_dividend_inclusive_variant_are_explicit() -> None:
    assert _last_session_of_month(AS_OF)
    assert not _last_session_of_month(AS_OF.replace(day=29))
    source = Path(
        "research/sprints/ASA-RES-STRATEGY-QUALIFICATION-002/gate-registry.yaml"
    ).read_text()
    assert "footnote-8 variant that includes dividend payers" in source


def test_formation_price_requires_exact_session_and_security_master_is_point_in_time() -> None:
    instrument = AAPL
    exact_end = AS_OF
    exact_bar = OHLCVBar(
        AAPL,
        86400,
        exact_end - timedelta(days=1),
        exact_end,
        Decimal("10"),
        Decimal("11"),
        Decimal("9"),
        Decimal("10"),
        Decimal("100"),
    )
    exact_series = OHLCVSeries(instrument, 86400, exact_end, (exact_bar,))
    assert _formation_close(exact_end, exact_series) == Decimal("10")
    assert _formation_close(AS_OF - timedelta(minutes=1), exact_series) == UnknownReason(
        "G_ZHAN_PRICE_MIN_UNKNOWN"
    )

    prior_bar = replace(
        exact_bar,
        start_at=exact_bar.start_at - timedelta(days=1),
        end_at=exact_bar.end_at - timedelta(days=1),
    )
    prior_series = OHLCVSeries(instrument, 86400, prior_bar.end_at, (prior_bar,))
    assert _formation_close(exact_end, prior_series) == UnknownReason(
        "G_ZHAN_PRICE_MIN_UNKNOWN"
    )

    security = SecurityMasterRecord(
        AAPL,
        SecurityType.COMMON_STOCK,
        Decimal("1000000"),
        AS_OF.date(),
    )
    assert _security_master_is_effective(exact_end, security)
    assert not _security_master_is_effective(
        exact_end, replace(security, effective_date=AS_OF.date() + timedelta(days=1))
    )

    early_end = datetime(2024, 11, 29, 18, tzinfo=UTC)
    early_start = early_end - timedelta(days=1)
    early_bar = replace(exact_bar, start_at=early_start, end_at=early_end)
    early_series = OHLCVSeries(AAPL, 86400, early_end, (early_bar,))
    assert _formation_close(early_end, early_series) == Decimal("10")
    assert _formation_close(
        datetime(2024, 11, 29, 17, 59, tzinfo=UTC), early_series
    ) == UnknownReason("G_ZHAN_PRICE_MIN_UNKNOWN")


def test_subject_first_adapter_replays_materialized_portfolio_without_acquisition() -> None:
    materialized = materialize_zhan_family({f"S{i}": _candidate(i) for i in range(10)})
    subject, payload = next(
        (candidate_subject, value)
        for candidate_subject, value in materialized.items()
        if isinstance(value, ZhanSubjectMaterialization) and value.state == "PASS"
    )
    assert isinstance(payload, ZhanSubjectMaterialization)
    knowledge = ReadOnlyStrategyInput("snapshot", "digest", AS_OF, (), DerivedFactSet(()), payload)

    class Clock:
        def now(self) -> datetime:
            return AS_OF

    context = RuntimeContext(ZHAN_CONTRACT, subject, Clock(), "run")
    adapter = build_zhan_subject_first_adapter({subject: knowledge})
    first = adapter(context)
    second = adapter(context)
    assert first == second
    assert first.evaluation_state.value == "pass"
    assert first.lifecycle_stage == "entered"
    assert payload.portfolio is not None
    assert first.metrics["portfolio.identity"].native() == payload.portfolio.identity
