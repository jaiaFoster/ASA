from __future__ import annotations

import dataclasses

import pytest

from domain.values import DomainInvariantError
from market_data import (
    MarketSnapshotBuilder,
    MarketSnapshot,
    SnapshotFixtureLibrary,
    SnapshotReplayRecord,
    SnapshotRequest,
    replay_market_snapshot,
)
from tests.market_data.test_snapshot import CAPABILITY, NOW, successful_inputs


def snapshot() -> MarketSnapshot:
    source, fulfillment, resolution, budgets = successful_inputs()
    return MarketSnapshotBuilder().build(
        SnapshotRequest(NOW, (CAPABILITY,), (CAPABILITY,)),
        (fulfillment,),
        (resolution,),
        (source.metadata,),
        (),
        budgets.accounting,
    )


def test_offline_replay_is_deterministic_and_reconstructs_observations() -> None:
    source = snapshot()
    record = SnapshotReplayRecord(source, source.snapshot_digest)
    first = replay_market_snapshot(record)
    second = replay_market_snapshot(record)
    assert first == second
    assert first.observations == source.observations
    assert first.resolution_results == source.resolution_results


def test_tampered_expected_digest_fails_closed() -> None:
    source = snapshot()
    with pytest.raises(DomainInvariantError, match="digest verification"):
        replay_market_snapshot(SnapshotReplayRecord(source, "0" * 64))


def test_fixture_library_loads_only_explicit_sealed_snapshot() -> None:
    source = snapshot()
    library = SnapshotFixtureLibrary((source,))
    assert library.load(source.snapshot_id) is source
    with pytest.raises(DomainInvariantError, match="not found"):
        library.load("missing")


def test_replay_signature_has_no_provider_factory_or_transport_path() -> None:
    source = snapshot()
    record = SnapshotReplayRecord(source, source.snapshot_digest)
    with pytest.raises(TypeError):
        replay_market_snapshot(record, object())  # type: ignore[call-arg]


def test_snapshot_contract_rejects_internal_digest_tampering() -> None:
    source = snapshot()
    with pytest.raises(DomainInvariantError, match="content-derived"):
        dataclasses.replace(source, snapshot_digest="f" * 64)
