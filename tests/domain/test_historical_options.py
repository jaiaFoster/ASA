from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from analytics.option_return_history import MonthlyOptionReturn, straddle_momentum_formation
from domain import (
    CanonicalInstrumentIdentity,
    CompletenessMetadata,
    EvidenceKind,
    EvidenceReference,
    FreshnessMetadata,
    FreshnessStatus,
    HistoricalOptionPanel,
    HistoricalOptionSnapshot,
    MarketCapability,
    MarketDataRequestContext,
    MarketDataSubject,
    MarketDataSubjectType,
    MarketObservation,
    ProviderProvenance,
    UnknownReason,
    deserialize_market_data,
    historical_option_panel_or_unknown,
    market_observation_identity,
    serialize_market_data,
)
from tests.strategies.test_cboe_put_strategy import SPX, _put


def _snapshot(month: int) -> HistoricalOptionSnapshot:
    observed = datetime(2025, month, 15, tzinfo=UTC)
    contract = replace(_put(Decimal(4000 + month)), observed_at=observed)
    return HistoricalOptionSnapshot(
        SPX.instrument, observed, observed + timedelta(hours=1), f"source-{month}", (contract,)
    )


def test_a08_panel_is_point_in_time_immutable_and_replay_identical() -> None:
    snapshots = tuple(_snapshot(month) for month in range(1, 13))
    panel = HistoricalOptionPanel(SPX.instrument, datetime(2025, 12, 31, tzinfo=UTC), snapshots)
    replay = HistoricalOptionPanel(SPX.instrument, panel.as_of, snapshots)
    assert replay.identity == panel.identity


def test_a08_is_canonical_market_observation_with_wire_roundtrip() -> None:
    panel = HistoricalOptionPanel(
        SPX.instrument,
        datetime(2025, 12, 31, tzinfo=UTC),
        tuple(_snapshot(month) for month in range(1, 13)),
    )
    evidence = (EvidenceReference(EvidenceKind.OBSERVATION, "a08-source"),)
    subject = MarketDataSubject(
        SPX.instrument,
        MarketDataSubjectType.OPTION_UNDERLYING,
        MarketCapability.HISTORICAL_OPTION_PANEL_V1,
        MarketDataRequestContext(panel.as_of, panel.as_of, ("contracts",), (), evidence),
    )
    observation_id = market_observation_identity(
        "fixture", MarketCapability.HISTORICAL_OPTION_PANEL_V1, subject, panel.as_of, panel, "v1"
    )
    observation = MarketObservation(
        observation_id,
        MarketCapability.HISTORICAL_OPTION_PANEL_V1,
        subject,
        panel.as_of,
        panel.as_of,
        panel,
        "v1",
        ProviderProvenance("fixture", "request", evidence),
        FreshnessMetadata(panel.as_of, panel.as_of, 60, 0, FreshnessStatus.FRESH),
        CompletenessMetadata(("contracts",), ("contracts",), ()),
    )
    assert deserialize_market_data(serialize_market_data(observation)) == observation


def test_a08_identity_changes_when_observed_option_values_change() -> None:
    snapshot = _snapshot(1)
    changed_contract = replace(snapshot.contracts[0], delta=Decimal("-0.25"))
    changed = replace(snapshot, contracts=(changed_contract,))
    assert changed.identity != snapshot.identity


def test_a08_snapshot_canonicalizes_provider_contract_order() -> None:
    observed = datetime(2025, 1, 15, tzinfo=UTC)
    first = replace(_put(Decimal(4000)), observed_at=observed)
    second = replace(_put(Decimal(4100)), observed_at=observed)
    left = HistoricalOptionSnapshot(
        SPX.instrument, observed, observed + timedelta(hours=1), "source", (first, second)
    )
    right = HistoricalOptionSnapshot(
        SPX.instrument, observed, observed + timedelta(hours=1), "source", (second, first)
    )
    assert left.contracts == right.contracts
    assert left.identity == right.identity


def test_a08_rejects_same_symbol_with_different_canonical_subject() -> None:
    snapshot = _snapshot(1)
    different_identity = replace(
        SPX.instrument,
        identity=CanonicalInstrumentIdentity("test", "different-spx"),
    )
    with pytest.raises(ValueError, match="underlying must match"):
        replace(snapshot, subject=different_identity)


def test_a08_rejects_lookahead_and_nonchronological_evidence() -> None:
    snapshot = _snapshot(2)
    with pytest.raises(ValueError, match="unavailable as_of"):
        HistoricalOptionPanel(SPX.instrument, datetime(2025, 1, 31, tzinfo=UTC), (snapshot,))
    with pytest.raises(ValueError, match="chronological"):
        HistoricalOptionPanel(
            SPX.instrument,
            datetime(2025, 12, 31, tzinfo=UTC),
            (_snapshot(2), _snapshot(1)),
        )
    assert historical_option_panel_or_unknown(
        SPX.instrument, datetime(2025, 12, 31, tzinfo=UTC), ()
    ) == UnknownReason("historical_option_panel_unavailable")


def test_a17_requires_complete_lags_two_through_twelve_and_skips_lag_one() -> None:
    history = {
        lag: MonthlyOptionReturn(
            date(2025, lag, 1), Decimal(lag) / Decimal(100), "panel", f"position-{lag}"
        )
        for lag in range(1, 13)
    }
    expected = sum((Decimal(lag) / Decimal(100) for lag in range(2, 13)), Decimal(0)) / Decimal(11)
    assert straddle_momentum_formation(history) == expected
    del history[7]
    assert straddle_momentum_formation(history) == UnknownReason(
        "insufficient_straddle_return_history"
    )
