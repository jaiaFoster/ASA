"""Production strategy contracts and subject-first knowledge bindings.

Acquisition is owned by generic subject planning.  The production registry
contains no acquisition-capable adapter; authoritative evaluation is built
from immutable prepared knowledge by the subject preparation registry.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType

from analytics.calendar_facts import TradingCalendarView, new_york_time, third_friday_roll_date
from domain import MarketCapability
from market_data import CapabilityRegistry
from market_data.capability_coalescing import (
    reduce_historical_bar_results,
    reduce_option_chain_results,
    reduce_rate_observation_results,
)
from market_data.resolution import ResolutionPolicy
from market_data.session_calendar import UsEquitySessionCalendar
from screening.subject_planning import CapabilityResultReducer
from strategies import (
    EARNINGS_CALENDAR_MANIFEST,
    FORWARD_FACTOR_CALENDAR_MANIFEST,
    SKEW_MOMENTUM_VERTICAL_MANIFEST,
)
from strategies.bxm_manifest import BXM_MANIFEST
from strategies.bxm_planning import resolved_field_requirements as bxm_resolved_field_requirements
from strategies.cboe_put_manifest import CBOE_PUT_MANIFEST
from strategies.cboe_put_planning import (
    resolved_field_requirements as cboe_put_resolved_field_requirements,
)
from strategies.cboe_puty_manifest import CBOE_PUTY_MANIFEST
from strategies.earnings_calendar_planning import earnings_calendar_resolved_field_requirements
from strategies.forward_factor_planning import (
    resolved_field_requirements as forward_factor_resolved_field_requirements,
)
from strategies.gxz_manifest import GXZ_MANIFEST
from strategies.gxz_planning import resolved_field_requirements as gxz_resolved_field_requirements
from strategies.manifest_version_pins import version_pin_violations
from strategies.put_credit_spread_manifest import SPY_PUT_CREDIT_SPREAD_MANIFEST
from strategies.put_credit_spread_planning import (
    resolved_field_requirements as put_credit_spread_resolved_field_requirements,
)
from strategies.scs_manifest import SCS_MANIFEST
from strategies.scs_planning import resolved_field_requirements as scs_resolved_field_requirements
from strategies.skew_momentum_planning import (
    resolved_field_requirements as skew_momentum_resolved_field_requirements,
)
from strategies.stock_benchmark_manifests import B001_MANIFEST, B002_MANIFEST
from strategies.stock_benchmark_planning import (
    b001_resolved_field_requirements,
    b002_resolved_field_requirements,
)
from strategy_runtime.adapters.bxm import BXM_CONTRACT
from strategy_runtime.adapters.bxm_subject_first import build_bxm_subject_preparation_binding
from strategy_runtime.adapters.cboe_put import CBOE_PUT_CONTRACT
from strategy_runtime.adapters.cboe_put_subject_first import (
    build_cboe_put_subject_preparation_binding,
)
from strategy_runtime.adapters.cboe_puty import CBOE_PUTY_CONTRACT
from strategy_runtime.adapters.cboe_puty_subject_first import (
    build_cboe_puty_subject_preparation_binding,
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
from strategy_runtime.adapters.gxz import GXZ_CONTRACT
from strategy_runtime.adapters.gxz_subject_first import build_gxz_subject_preparation_binding
from strategy_runtime.adapters.put_credit_spread import SPY_PUT_CREDIT_SPREAD_CONTRACT
from strategy_runtime.adapters.put_credit_spread_subject_first import (
    build_put_credit_spread_subject_preparation_binding,
)
from strategy_runtime.adapters.scs import SCS_CONTRACT
from strategy_runtime.adapters.scs_subject_first import build_scs_subject_preparation_binding
from strategy_runtime.adapters.skew_momentum_subject_first import (
    build_skew_momentum_subject_preparation_binding,
)
from strategy_runtime.adapters.skew_momentum_vertical import (
    SKEW_MOMENTUM_VERTICAL_CONTRACT,
)
from strategy_runtime.adapters.stock_benchmarks import B001_CONTRACT, B002_CONTRACT
from strategy_runtime.adapters.stock_benchmarks_subject_first import (
    build_b001_subject_preparation_binding,
    build_b002_subject_preparation_binding,
)
from strategy_runtime.catalog import SignalCatalogEntry
from strategy_runtime.context import RuntimeContext
from strategy_runtime.historical_evidence import HistoricalSkewRepository
from strategy_runtime.manifest_contract import validate_manifest_contract
from strategy_runtime.market_data_planning import resolution_policy_for_capabilities
from strategy_runtime.orchestration import CutoverPolicy
from strategy_runtime.persistence import LifecyclePositionState
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
        (B001_MANIFEST, B001_CONTRACT),
        (B002_MANIFEST, B002_CONTRACT),
        (SPY_PUT_CREDIT_SPREAD_MANIFEST, SPY_PUT_CREDIT_SPREAD_CONTRACT),
        (GXZ_MANIFEST, GXZ_CONTRACT),
        (CBOE_PUT_MANIFEST, CBOE_PUT_CONTRACT),
        (CBOE_PUTY_MANIFEST, CBOE_PUTY_CONTRACT),
        (BXM_MANIFEST, BXM_CONTRACT),
        (SCS_MANIFEST, SCS_CONTRACT),
    )
    for manifest, contract in pairs:
        validate_manifest_contract(manifest, contract)
    violations = version_pin_violations(manifest for manifest, _ in pairs)
    if violations:
        raise ValueError("; ".join(violations))
    return StrategyRegistry(
        (
            (FORWARD_FACTOR_CONTRACT, _subject_first_only),
            (SKEW_MOMENTUM_VERTICAL_CONTRACT, _subject_first_only),
            (EARNINGS_CALENDAR_CONTRACT, _subject_first_only),
            (B001_CONTRACT, _subject_first_only),
            (B002_CONTRACT, _subject_first_only),
            (SPY_PUT_CREDIT_SPREAD_CONTRACT, _subject_first_only),
            (GXZ_CONTRACT, _subject_first_only),
            (CBOE_PUT_CONTRACT, _subject_first_only),
            (CBOE_PUTY_CONTRACT, _subject_first_only),
            (BXM_CONTRACT, _subject_first_only),
            (SCS_CONTRACT, _subject_first_only),
        )
    )


def build_migrated_shadow_registry(
    now: datetime,
    historical_skew_repository: HistoricalSkewRepository | None = None,
    lifecycle_identity_by_strategy_subject: Mapping[tuple[str, str], str] = MappingProxyType({}),
    lifecycle_state_by_strategy_subject: Mapping[
        tuple[str, str], LifecyclePositionState
    ] = MappingProxyType({}),
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
    local = new_york_time(now)
    first = local.date().replace(day=1)
    following = first.replace(year=first.year + (first.month == 12), month=first.month % 12 + 1)
    sessions = UsEquitySessionCalendar()
    bxm_roll_date = third_friday_roll_date(
        TradingCalendarView(
            lambda value: sessions.session(value) is not None,
            first,
            following,
        ),
        local.year,
        local.month,
    )
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
            (B001_CONTRACT.strategy_id, build_b001_subject_preparation_binding(now)),
            (B002_CONTRACT.strategy_id, build_b002_subject_preparation_binding(now)),
            (
                SPY_PUT_CREDIT_SPREAD_CONTRACT.strategy_id,
                build_put_credit_spread_subject_preparation_binding(now),
            ),
            (GXZ_CONTRACT.strategy_id, build_gxz_subject_preparation_binding(now)),
            (CBOE_PUT_CONTRACT.strategy_id, build_cboe_put_subject_preparation_binding(now)),
            (CBOE_PUTY_CONTRACT.strategy_id, build_cboe_puty_subject_preparation_binding(now)),
            (
                BXM_CONTRACT.strategy_id,
                build_bxm_subject_preparation_binding(
                    now,
                    bxm_roll_date,
                    MappingProxyType(
                        {
                            subject: identity
                            for (strategy_id, subject), identity in (
                                lifecycle_identity_by_strategy_subject.items()
                            )
                            if strategy_id == BXM_CONTRACT.strategy_id
                        }
                    ),
                ),
            ),
            (
                SCS_CONTRACT.strategy_id,
                build_scs_subject_preparation_binding(
                    now,
                    MappingProxyType(
                        {
                            subject: state
                            for (strategy_id, subject), state in (
                                lifecycle_state_by_strategy_subject.items()
                            )
                            if strategy_id == SCS_CONTRACT.strategy_id
                        }
                    ),
                ),
            ),
        )
    )


def migrated_shadow_capability_reducers() -> dict[MarketCapability, CapabilityResultReducer]:
    """Generic multi-result capability reducers registered bindings need.

    OPTION_CHAIN_V1 combines discovery/per-expiration requests. Historical
    bars combine the distinct lookback windows declared by Skew Momentum
    and Earnings Calendar. Both are forwarded unchanged into
    strategy_runtime.orchestration.prepare_subject_shadow_knowledge by
    both production roots.
    """
    return {
        MarketCapability.HISTORICAL_BARS_V1: reduce_historical_bar_results,
        MarketCapability.OPTION_CHAIN_V1: reduce_option_chain_results,
        MarketCapability.RATE_OBSERVATION_V1: reduce_rate_observation_results,
    }


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
            B001_CONTRACT.strategy_id,
            B002_CONTRACT.strategy_id,
            SPY_PUT_CREDIT_SPREAD_CONTRACT.strategy_id,
            GXZ_CONTRACT.strategy_id,
            CBOE_PUT_CONTRACT.strategy_id,
            CBOE_PUTY_CONTRACT.strategy_id,
            BXM_CONTRACT.strategy_id,
            SCS_CONTRACT.strategy_id,
        )
    )
    requirements: dict[MarketCapability, tuple[tuple[str, ...], int]] = {}
    if EARNINGS_CALENDAR_CONTRACT.strategy_id in selected:
        requirements.update(earnings_calendar_resolved_field_requirements())
    if FORWARD_FACTOR_CONTRACT.strategy_id in selected:
        requirements.update(forward_factor_resolved_field_requirements())
    if SKEW_MOMENTUM_VERTICAL_CONTRACT.strategy_id in selected:
        requirements.update(skew_momentum_resolved_field_requirements())
    if B001_CONTRACT.strategy_id in selected:
        requirements.update(b001_resolved_field_requirements())
    if B002_CONTRACT.strategy_id in selected:
        requirements.update(b002_resolved_field_requirements())
    if SPY_PUT_CREDIT_SPREAD_CONTRACT.strategy_id in selected:
        requirements.update(put_credit_spread_resolved_field_requirements())
    if GXZ_CONTRACT.strategy_id in selected:
        requirements.update(gxz_resolved_field_requirements())
    if CBOE_PUT_CONTRACT.strategy_id in selected:
        requirements.update(cboe_put_resolved_field_requirements())
    if CBOE_PUTY_CONTRACT.strategy_id in selected:
        requirements.update(cboe_put_resolved_field_requirements())
    if BXM_CONTRACT.strategy_id in selected:
        requirements.update(bxm_resolved_field_requirements())
    if SCS_CONTRACT.strategy_id in selected:
        requirements.update(scs_resolved_field_requirements())
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
        SignalCatalogEntry.from_contract(B001_CONTRACT, manifest_id=B001_MANIFEST.manifest_id),
        SignalCatalogEntry.from_contract(B002_CONTRACT, manifest_id=B002_MANIFEST.manifest_id),
        SignalCatalogEntry.from_contract(
            SPY_PUT_CREDIT_SPREAD_CONTRACT,
            manifest_id=SPY_PUT_CREDIT_SPREAD_MANIFEST.manifest_id,
        ),
        SignalCatalogEntry.from_contract(GXZ_CONTRACT, manifest_id=GXZ_MANIFEST.manifest_id),
        SignalCatalogEntry.from_contract(
            CBOE_PUT_CONTRACT, manifest_id=CBOE_PUT_MANIFEST.manifest_id
        ),
        SignalCatalogEntry.from_contract(
            CBOE_PUTY_CONTRACT, manifest_id=CBOE_PUTY_MANIFEST.manifest_id
        ),
        SignalCatalogEntry.from_contract(BXM_CONTRACT, manifest_id=BXM_MANIFEST.manifest_id),
        SignalCatalogEntry.from_contract(SCS_CONTRACT, manifest_id=SCS_MANIFEST.manifest_id),
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
            # B001/B002 have no legacy adapter at all (their production
            # registry entry is _subject_first_only, which raises) -- the
            # subject-first path must be authoritative from day one.
            B001_CONTRACT.strategy_id: True,
            B002_CONTRACT.strategy_id: True,
            SPY_PUT_CREDIT_SPREAD_CONTRACT.strategy_id: True,
            GXZ_CONTRACT.strategy_id: True,
            CBOE_PUT_CONTRACT.strategy_id: True,
            CBOE_PUTY_CONTRACT.strategy_id: True,
            BXM_CONTRACT.strategy_id: True,
        }
    )
