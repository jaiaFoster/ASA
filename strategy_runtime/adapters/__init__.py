"""Production strategy contracts and subject-first knowledge bindings.

Acquisition is owned by generic subject planning.  The production registry
contains no acquisition-capable adapter; authoritative evaluation is built
from immutable prepared knowledge by the subject preparation registry.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from domain import MarketCapability
from market_data import CapabilityRegistry
from market_data.capability_coalescing import reduce_option_chain_results
from market_data.resolution import ResolutionPolicy
from screening.subject_planning import CapabilityResultReducer
from strategies import (
    EARNINGS_CALENDAR_MANIFEST,
    FORWARD_FACTOR_CALENDAR_MANIFEST,
    SKEW_MOMENTUM_VERTICAL_MANIFEST,
)
from strategies.earnings_calendar_planning import earnings_calendar_resolved_field_requirements
from strategies.forward_factor_planning import (
    resolved_field_requirements as forward_factor_resolved_field_requirements,
)
from strategies.skew_momentum_planning import (
    resolved_field_requirements as skew_momentum_resolved_field_requirements,
)
from strategy_runtime.adapters.earnings_calendar import (
    EARNINGS_CALENDAR_CONTRACT,
)
from strategy_runtime.adapters.earnings_calendar_subject_first import (
    build_earnings_calendar_subject_preparation_binding,
)
from strategy_runtime.adapters.forward_factor import (
    FORWARD_FACTOR_CONTRACT,
)
from strategy_runtime.adapters.forward_factor_subject_first import (
    build_forward_factor_subject_preparation_binding,
)
from strategy_runtime.adapters.skew_momentum_subject_first import (
    build_skew_momentum_subject_preparation_binding,
)
from strategy_runtime.adapters.skew_momentum_vertical import (
    SKEW_MOMENTUM_VERTICAL_CONTRACT,
)
from strategy_runtime.catalog import SignalCatalogEntry
from strategy_runtime.context import RuntimeContext
from strategy_runtime.historical_evidence import HistoricalSkewRepository
from strategy_runtime.manifest_contract import validate_manifest_contract
from strategy_runtime.market_data_planning import resolution_policy_for_capabilities
from strategy_runtime.orchestration import CutoverPolicy
from strategy_runtime.registry import StrategyRegistry
from strategy_runtime.result import UniversalScreeningResult
from strategy_runtime.subject_preparation import SubjectPreparationRegistry

__all__ = [
    "build_migrated_cutover_policy",
    "build_migrated_shadow_registry",
    "build_migrated_signal_catalog",
    "build_migrated_strategy_registry",
    "migrated_shadow_capability_reducers",
    "migrated_shadow_resolution_policy",
]


def _subject_first_only(_context: RuntimeContext) -> UniversalScreeningResult:
    raise RuntimeError("production strategies require prepared read-only knowledge")


def build_migrated_strategy_registry() -> StrategyRegistry[UniversalScreeningResult]:
    """Register all production contracts without acquisition authority."""
    pairs = (
        (FORWARD_FACTOR_CALENDAR_MANIFEST, FORWARD_FACTOR_CONTRACT),
        (SKEW_MOMENTUM_VERTICAL_MANIFEST, SKEW_MOMENTUM_VERTICAL_CONTRACT),
        (EARNINGS_CALENDAR_MANIFEST, EARNINGS_CALENDAR_CONTRACT),
    )
    for manifest, contract in pairs:
        validate_manifest_contract(manifest, contract)
    return StrategyRegistry(
        (
            (FORWARD_FACTOR_CONTRACT, _subject_first_only),
            (SKEW_MOMENTUM_VERTICAL_CONTRACT, _subject_first_only),
            (EARNINGS_CALENDAR_CONTRACT, _subject_first_only),
        )
    )


def build_migrated_shadow_registry(
    now: datetime, historical_skew_repository: HistoricalSkewRepository | None = None
) -> SubjectPreparationRegistry[object]:
    """Every migrated strategy with a registered subject-first shadow
    binding, assembled once per invocation/cycle (SPRINT-014 S14-PR-05A,
    Architect checkpoint: sixteenth review, "both roots must use the same
    new orchestration primitives"). Today, only Earnings Calendar has one;
    strategy_runtime.orchestration's own shared seam looks strategy_ids up
    here generically by registry membership, never by a hand-written
    if-branch -- a strategy with no entry here is simply never shadowed.

    Rebuilt fresh per caller invocation, never cached across cycles/
    requests, because build_earnings_calendar_subject_preparation_binding
    itself closes its own bootstrap demands and phase-two expansion over
    this exact ``now``.
    """
    return SubjectPreparationRegistry(
        (
            (
                FORWARD_FACTOR_CONTRACT.strategy_id,
                build_forward_factor_subject_preparation_binding(now),
            ),
            (
                SKEW_MOMENTUM_VERTICAL_CONTRACT.strategy_id,
                build_skew_momentum_subject_preparation_binding(now, historical_skew_repository),
            ),
            (
                EARNINGS_CALENDAR_CONTRACT.strategy_id,
                build_earnings_calendar_subject_preparation_binding(now),
            ),
        )
    )


def migrated_shadow_capability_reducers() -> dict[MarketCapability, CapabilityResultReducer]:
    """Generic multi-result capability reducers any registered shadow
    binding's own subject plan might need while sealing -- currently just
    OPTION_CHAIN_V1 (Earnings Calendar's own discovery-then-per-expiration-
    contract acquisition shape), forwarded unchanged into
    strategy_runtime.orchestration.prepare_subject_shadow_knowledge by
    both production roots.
    """
    return {MarketCapability.OPTION_CHAIN_V1: reduce_option_chain_results}


def migrated_shadow_resolution_policy(
    capability_registry: CapabilityRegistry,
    strategy_ids: tuple[str, ...] | None = None,
) -> dict[MarketCapability, ResolutionPolicy]:
    """Resolution policies for every capability today's one registered
    shadow binding (Earnings Calendar) needs sealed, built from this
    subject's own already-built CapabilityRegistry -- never a second,
    hand-copied provider-priority list in asa/ (Architect checkpoint:
    fourteenth review, "provider metadata and resolution policies must be
    constructed from existing market-data configuration/registry
    ownership").
    """
    selected = set(
        strategy_ids
        or (
            EARNINGS_CALENDAR_CONTRACT.strategy_id,
            FORWARD_FACTOR_CONTRACT.strategy_id,
            SKEW_MOMENTUM_VERTICAL_CONTRACT.strategy_id,
        )
    )
    requirements: dict[MarketCapability, tuple[tuple[str, ...], int]] = {}
    if EARNINGS_CALENDAR_CONTRACT.strategy_id in selected:
        requirements.update(earnings_calendar_resolved_field_requirements())
    if FORWARD_FACTOR_CONTRACT.strategy_id in selected:
        requirements.update(forward_factor_resolved_field_requirements())
    if SKEW_MOMENTUM_VERTICAL_CONTRACT.strategy_id in selected:
        requirements.update(skew_momentum_resolved_field_requirements())
    return resolution_policy_for_capabilities(capability_registry, requirements)


def build_migrated_signal_catalog() -> tuple[SignalCatalogEntry, ...]:
    """Public capability metadata projected from the universal contracts."""
    entries = (
        SignalCatalogEntry.from_contract(
            EARNINGS_CALENDAR_CONTRACT,
            manifest_id=EARNINGS_CALENDAR_MANIFEST.manifest_id,
        ),
        SignalCatalogEntry.from_contract(
            FORWARD_FACTOR_CONTRACT,
            manifest_id=FORWARD_FACTOR_CALENDAR_MANIFEST.manifest_id,
        ),
        SignalCatalogEntry.from_contract(
            SKEW_MOMENTUM_VERTICAL_CONTRACT,
            manifest_id=SKEW_MOMENTUM_VERTICAL_MANIFEST.manifest_id,
        ),
    )
    return tuple(sorted(entries, key=lambda item: item.signal_id))


def build_migrated_cutover_policy(values: Mapping[str, str]) -> CutoverPolicy:
    """Return the single authoritative subject-first production policy.

    M3 deliberately removes the temporary per-strategy rollback path.
    ``values`` remains accepted until the composition-root API is simplified,
    but no environment value can reactivate strategy-owned acquisition.
    """
    del values
    return CutoverPolicy(
        {
            FORWARD_FACTOR_CONTRACT.strategy_id: True,
            SKEW_MOMENTUM_VERTICAL_CONTRACT.strategy_id: True,
            EARNINGS_CALENDAR_CONTRACT.strategy_id: True,
        }
    )
