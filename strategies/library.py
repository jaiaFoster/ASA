"""Immutable canonical Strategy Library catalog (STONK-006)."""

from __future__ import annotations

import hashlib

from strategies.errors import ManifestValidationError
from strategies.manifest import StrategyManifest, canonical_strategy_json
from strategies.stonk_manifests import STONK_STRATEGY_MANIFESTS

STRATEGY_LIBRARY_IDENTITY_NAMESPACE = "asa.strategy_library"
STRATEGY_LIBRARY_VERSION = "1.0.0"


class StrategyLibrary:
    """Finite deterministic catalog of complete Strategy Manifests."""

    __slots__ = ("_identity", "_manifests")
    _identity: str
    _manifests: tuple[StrategyManifest, ...]

    def __init__(self, manifests: tuple[StrategyManifest, ...]) -> None:
        if not manifests:
            raise ManifestValidationError("Strategy Library cannot be empty")
        ordered = tuple(
            sorted(manifests, key=lambda item: (item.strategy_id, item.strategy_version))
        )
        keys = tuple((item.strategy_id, item.strategy_version) for item in ordered)
        if len(keys) != len(set(keys)):
            raise ManifestValidationError("duplicate strategy ID and version in Strategy Library")
        current_ids = tuple(item.strategy_id for item in ordered)
        if len(current_ids) != len(set(current_ids)):
            raise ManifestValidationError(
                "Strategy Library v1 supports one current version per strategy ID"
            )
        object.__setattr__(self, "_manifests", ordered)
        payload = {
            "identity_namespace": STRATEGY_LIBRARY_IDENTITY_NAMESPACE,
            "library_version": STRATEGY_LIBRARY_VERSION,
            "manifest_ids": [item.manifest_id for item in ordered],
        }
        object.__setattr__(
            self,
            "_identity",
            hashlib.sha256(canonical_strategy_json(payload)).hexdigest(),
        )

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(self, name):
            raise AttributeError("StrategyLibrary is immutable")
        object.__setattr__(self, name, value)

    @property
    def manifests(self) -> tuple[StrategyManifest, ...]:
        return self._manifests

    @property
    def identity(self) -> str:
        return self._identity

    def strategy_ids(self) -> tuple[str, ...]:
        return tuple(item.strategy_id for item in self._manifests)

    def get(self, strategy_id: str) -> StrategyManifest:
        for manifest in self._manifests:
            if manifest.strategy_id == strategy_id:
                return manifest
        raise KeyError(strategy_id)


STONK_STRATEGY_LIBRARY = StrategyLibrary(STONK_STRATEGY_MANIFESTS)
