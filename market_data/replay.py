"""Offline-only Market Snapshot replay integration (MD-015)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from domain import MarketObservation
from domain.values import DomainInvariantError
from market_data.resolution import ResolutionResult
from market_data.snapshot import MarketSnapshot, market_snapshot_digest


@dataclass(frozen=True, slots=True)
class SnapshotReplayRecord:
    snapshot: MarketSnapshot
    expected_digest: str
    replay_algorithm_version: str = "asa.market_data_replay/v1"

    def __post_init__(self) -> None:
        if not self.expected_digest or self.expected_digest != self.expected_digest.strip():
            raise DomainInvariantError("SnapshotReplayRecord expected digest must be normalized")
        if self.replay_algorithm_version != "asa.market_data_replay/v1":
            raise DomainInvariantError("SnapshotReplayRecord algorithm version is unsupported")


@dataclass(frozen=True, slots=True)
class SnapshotReplayResult:
    replay_id: str
    snapshot_id: str
    snapshot_digest: str
    observations: tuple[MarketObservation, ...]
    resolution_results: tuple[ResolutionResult, ...]
    verified: bool

    def __post_init__(self) -> None:
        if not self.verified:
            raise DomainInvariantError("SnapshotReplayResult must represent verified replay")


class SnapshotFixtureLibrary:
    """Immutable in-memory inventory of explicit snapshot fixtures."""

    __slots__ = ("_snapshots",)

    def __init__(self, snapshots: tuple[MarketSnapshot, ...]) -> None:
        ordered = tuple(sorted(snapshots, key=lambda item: item.snapshot_id))
        if not ordered or len({item.snapshot_id for item in ordered}) != len(ordered):
            raise DomainInvariantError("SnapshotFixtureLibrary requires unique snapshots")
        self._snapshots = ordered

    def load(self, snapshot_id: str) -> MarketSnapshot:
        matches = tuple(item for item in self._snapshots if item.snapshot_id == snapshot_id)
        if len(matches) != 1:
            raise DomainInvariantError("Snapshot fixture was not found")
        return matches[0]


def replay_market_snapshot(record: SnapshotReplayRecord) -> SnapshotReplayResult:
    """Verify and replay sealed content; no injectable acquisition dependency exists."""

    actual_digest = market_snapshot_digest(record.snapshot)
    if actual_digest != record.snapshot.snapshot_digest or actual_digest != record.expected_digest:
        raise DomainInvariantError("Market Snapshot replay digest verification failed")
    payload = json.dumps(
        {
            "algorithm": record.replay_algorithm_version,
            "snapshot_digest": actual_digest,
            "snapshot_id": record.snapshot.snapshot_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    replay_id = f"asa.market_data_replay/v1:{hashlib.sha256(payload).hexdigest()}"
    return SnapshotReplayResult(
        replay_id,
        record.snapshot.snapshot_id,
        actual_digest,
        record.snapshot.observations,
        record.snapshot.resolution_results,
        True,
    )
