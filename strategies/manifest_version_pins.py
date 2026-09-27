"""Semantic-version pins for assumption-bearing manifests (SP-01E).

Freeze rule `changing_semantics_changing_assumption_requires_strategy_semantic_version_change`:
every production manifest that declares research or implementation
assumptions pins its `(strategy_id, strategy_version) -> manifest_id`. A change
to an assumption or its parameter value changes `manifest_id`. If
`strategy_version` is not bumped, the pin no longer matches and the registry
check fails, so the change cannot ship silently under the old version.
"""

from __future__ import annotations

from typing import Iterable, Mapping  # noqa: UP035 -- strategies/ import allowlist

from strategies.manifest import StrategyManifest

# Populated by each strategy ticket when it registers an assumption-bearing
# manifest. Keys are (strategy_id, strategy_version).
MANIFEST_VERSION_PINS: Mapping[tuple[str, str], str] = {
    (
        "event_vol_gxz_preea_straddle_to_expiry",
        "1.0.0-research",
    ): "8d0293718bb2e4228bc2a30aa3b6381f58a1ef9fd247e899b6b1d491b78778ef",
}


def version_pin_violations(
    manifests: Iterable[StrategyManifest],
    pins: Mapping[tuple[str, str], str] = MANIFEST_VERSION_PINS,
) -> tuple[str, ...]:
    """Violations for assumption-bearing manifests; empty means consistent."""
    violations: list[str] = []
    for manifest in manifests:
        if not manifest.assumptions:
            continue
        key = (manifest.strategy_id, manifest.strategy_version)
        pinned = pins.get(key)
        if pinned is None:
            violations.append(f"{key[0]}@{key[1]}: assumption-bearing manifest has no version pin")
        elif pinned != manifest.manifest_id:
            violations.append(
                f"{key[0]}@{key[1]}: semantics changed without a strategy_version change"
            )
    return tuple(violations)
