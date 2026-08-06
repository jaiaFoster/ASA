"""Subject-first, acquisition-sealing evidence builder for Earnings
Calendar (SPRINT-014 S14-PR-05).

Replaces screening.live_adapters.build_live_earnings_calendar_adapter's
own *acquisition* sequence with the same steps routed through a
market_data.subject_plan.SubjectAcquisitionPlan instead of calling
CapabilityFulfillmentService.fulfill() directly -- every attempt (success
and failure) is durably recorded and shared (S14-PR-01's own root-cause
fix), and no capability is fetched more than once even if selection logic
needs to look at it twice. The selection logic itself (which two
expirations to trade) is the exact same pure function
(analytics.expiration_selection.select_earnings_relative_expiration_pair)
this ticket's own two-phase pattern requires: it runs after bootstrap
evidence (quote, earnings event, available expirations) is resolved and
before the full union (both expirations' chains, daily closes) is
requested -- no provider access of its own.

This module is acquisition orchestration -- it belongs in screening/
(ADR-010: "screening owns acquisition planning and orchestration"),
called only by the composition root (asa/scheduled_screening.py), never
by strategy_runtime.adapters.earnings_calendar's own adapter function.
The adapter reads only the sealed SubjectSealedEvidence bundle this
module returns; it never imports this module, SubjectAcquisitionPlan, or
any provider-shaped type (verified by tests/architecture).

Financial logic is unchanged and reused verbatim: normalize_richness,
compute_iv_realized_spread, compute_realized_volatility,
select_atm_strike_at_expiration, combine_option_chains, and the manifest/
graph compilation live in screening.live_adapters/context_builders exactly
as they did before this ticket -- only how the underlying observations
are acquired changed.

Only two of the three requested capabilities (EARNINGS_CALENDAR_V1,
REAL_TIME_QUOTE_V1, OPTION_CHAIN_V1) are unconditionally attempted every
cycle; HISTORICAL_BARS_V1 (daily closes) is only requested once front/back
selection and the combined chain both succeed (the two-phase union), so it
is never listed as a MarketSnapshot-level "required" capability -- doing
so would make SnapshotRequest's own required-is-a-subset-of-requested
invariant fail on every cycle where it was never attempted.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import cast

from analytics.derived_fact_materialization import derived_fact_id, materialize_derived_fact
from analytics.derived_facts import (
    DERIVED_FACT_REGISTRY,
    REALIZED_VOLATILITY,
    compute_iv_realized_spread,
)
from analytics.expiration_selection import (
    ExpirationCandidate,
    select_earnings_relative_expiration_pair,
)
from analytics.features import DerivedFact, DerivedFactQualityStatus, DerivedFactSet
from analytics.realized_volatility import compute_realized_volatility
from domain import (
    EarningsEvent,
    ExpirationCycle,
    MarketCapability,
    OHLCVBar,
    OptionChain,
    OptionType,
    Quote,
)
from domain.canonical_fact import CanonicalFact
from domain.market_data import market_observation_identity
from domain.references import EvidenceKind, EvidenceReference
from facts.canonical_projection import project_canonical_fact
from market_data.fulfillment import CapabilityFulfillmentResult, FulfillmentStatus
from market_data.providers import CapabilityRequest, ProviderMetadata
from market_data.resolution import ResolutionPolicy
from market_data.session_calendar import MarketSessionStatus, UsEquitySessionCalendar
from market_data.subject_plan import SubjectAcquisitionPlan
from market_data.subject_snapshot import seal_subject_snapshot
from market_data.temporal import (
    DEFAULT_FRESHNESS_REQUIREMENT,
    FreshnessRequirement,
    UsabilityStatus,
    evaluate_temporal_usability,
)
from screening.earnings_calendar_fact_ids import (
    BACK_DAYS_TO_EXPIRATION_FACT,
    BACK_EXPIRATION_DATE_FACT,
    FRONT_DAYS_TO_EXPIRATION_FACT,
    FRONT_EXPIRATION_DATE_FACT,
    IV_REALIZED_RICHNESS_FACT,
    TARGET_STRIKE_FACT,
    TERM_STRUCTURE_RICHNESS_FACT,
)
from screening.live_adapters import _earnings_date, _spot_price
from screening.live_context import (
    build_capability_subject,
    combine_option_chains,
    normalize_expiration_response,
    select_atm_strike_at_expiration,
)
from strategies.requirements import earnings_calendar_requirement
from strategies.scoring import normalize_richness
from strategies.stonk_manifests import EARNINGS_CALENDAR_MANIFEST
from strategy_runtime.clock import Clock
from strategy_runtime.evidence import SubjectSealedEvidence

_ANALYTICS_UNIT_DECIMAL_RATIO = "decimal_ratio"
_ANALYTICS_UNIT_CALENDAR_DATE = "calendar_date"
_ANALYTICS_UNIT_DAYS = "days"
_ANALYTICS_UNIT_USD_STRIKE = "usd_strike"
_ALWAYS_REQUESTED_CAPABILITIES = (
    MarketCapability.EARNINGS_CALENDAR_V1,
    MarketCapability.REAL_TIME_QUOTE_V1,
    MarketCapability.OPTION_CHAIN_V1,
)

_RESOLUTION_POLICY_VERSION = "earnings-calendar-sealed-v1"
# Earnings Calendar's own sealing-time policy: how fresh a resolved
# observation must be, and which fields count as "complete," per
# capability -- distinct from FreshnessRequirement above (an
# acquisition-time usability gate over one provider's raw response, not a
# per-capability resolution-time gate over the observations a
# CapabilityFulfillmentService actually returned).
_REQUIRED_FIELDS_BY_CAPABILITY: dict[MarketCapability, tuple[str, ...]] = {
    MarketCapability.EARNINGS_CALENDAR_V1: ("earnings_date",),
    MarketCapability.REAL_TIME_QUOTE_V1: ("last",),
    MarketCapability.OPTION_CHAIN_V1: ("contracts",),
}
_FRESHNESS_THRESHOLD_SECONDS_BY_CAPABILITY: dict[MarketCapability, int] = {
    MarketCapability.EARNINGS_CALENDAR_V1: 3600 * 24 * 90,
    MarketCapability.REAL_TIME_QUOTE_V1: 3600,
    MarketCapability.OPTION_CHAIN_V1: 3600,
}


def default_resolution_policy_by_capability(
    provider_metadata: tuple[ProviderMetadata, ...],
) -> dict[MarketCapability, ResolutionPolicy]:
    """One ResolutionPolicy per capability in _ALWAYS_REQUESTED_CAPABILITIES,
    with provider_priority derived from exactly the ``provider_metadata``
    the caller is about to pass into acquire_sealed_earnings_calendar_evidence
    -- never a separately hand-maintained provider list, so a provider
    CapabilityFulfillmentService legitimately selected can never be
    silently rejected here as "not in policy." Alphabetical ordering
    matches strategy_runtime.market_data_planning's own
    _build_capability_registry() fulfillment-layer priority exactly, so
    sealing-time preference never disagrees with which provider actually
    served the request.
    """
    policies: dict[MarketCapability, ResolutionPolicy] = {}
    for capability in _ALWAYS_REQUESTED_CAPABILITIES:
        provider_priority = tuple(
            sorted(
                item.identity.provider_id
                for item in provider_metadata
                if capability in item.capabilities
            )
        )
        if not provider_priority:
            continue
        policies[capability] = ResolutionPolicy(
            _RESOLUTION_POLICY_VERSION,
            provider_priority,
            _FRESHNESS_THRESHOLD_SECONDS_BY_CAPABILITY[capability],
            _REQUIRED_FIELDS_BY_CAPABILITY[capability],
        )
    return policies


def _resolve_or_none(
    plan: SubjectAcquisitionPlan,
    symbol: str,
    capability: MarketCapability,
    now: datetime,
    required_fields: tuple[str, ...],
    *,
    expiration: date | None = None,
    effective_start: datetime | None = None,
    effective_end: datetime | None = None,
    freshness_requirement: FreshnessRequirement = DEFAULT_FRESHNESS_REQUIREMENT,
) -> tuple[CapabilityFulfillmentResult, object | None]:
    """Plan-backed counterpart of screening.live_adapters._acquire_or_raise:
    identical subject/request construction and temporal-usability check,
    but returns (result, value_or_None) instead of raising, so the caller
    seals whatever evidence exists rather than aborting the whole cycle on
    the first missing capability.
    """
    request_start = effective_start or now
    request_end = effective_end or now
    subject = build_capability_subject(
        symbol,
        capability,
        now,
        effective_start=request_start,
        effective_end=request_end,
        required_fields=required_fields,
        expiration=expiration,
    )
    request = CapabilityRequest(
        capability, (subject,), request_start, request_end, required_fields, 3600
    )
    result = plan.resolve(request)
    if result.status is FulfillmentStatus.FAILED or not result.observations:
        return result, None
    observation = result.observations[0]
    market_is_open = UsEquitySessionCalendar().status_at(now) is MarketSessionStatus.OPEN
    usability = evaluate_temporal_usability(
        observation.freshness, freshness_requirement, market_is_open=market_is_open
    )
    if usability.status is UsabilityStatus.REJECTED:
        return result, None
    return result, observation.value


def _resolve_expirations_or_none(
    plan: SubjectAcquisitionPlan, symbol: str, now: datetime
) -> tuple[CapabilityFulfillmentResult, tuple[ExpirationCycle, ...] | None]:
    """Plan-backed counterpart of screening.live_context.acquire_expirations.

    Requires exact FulfillmentStatus.FULFILLED (not DEGRADED) matching
    acquire_expirations's own stricter check -- a single MarketObservation
    per expiration, or one combined OptionChain observation, is only
    trustworthy from a primary-provider response, unlike a plain scalar
    capability where a fallback-provider DEGRADED result is still usable.
    Reuses normalize_expiration_response() verbatim -- the same response-
    shape normalization acquire_expirations() itself applies.
    """
    subject = build_capability_subject(
        symbol, MarketCapability.OPTION_CHAIN_V1, now, required_fields=("expirations",)
    )
    request = CapabilityRequest(
        MarketCapability.OPTION_CHAIN_V1, (subject,), now, now, ("expirations",), 3600
    )
    result = plan.resolve(request)
    if result.status is not FulfillmentStatus.FULFILLED or not result.observations:
        return result, None
    values = tuple(observation.value for observation in result.observations)
    return result, normalize_expiration_response(values, now.date())


def _resolve_closes_or_none(
    plan: SubjectAcquisitionPlan, symbol: str, now: datetime, *, lookback_days: int
) -> tuple[CapabilityFulfillmentResult, tuple[Decimal, ...] | None]:
    """Plan-backed counterpart of screening.live_adapters._acquire_daily_closes."""
    lookback_start = now - timedelta(days=lookback_days)
    subject = build_capability_subject(
        symbol,
        MarketCapability.HISTORICAL_BARS_V1,
        now,
        effective_start=lookback_start,
        effective_end=now,
        required_fields=("close",),
    )
    request = CapabilityRequest(
        MarketCapability.HISTORICAL_BARS_V1,
        (subject,),
        lookback_start,
        now,
        ("close",),
        int(timedelta(days=lookback_days + 1).total_seconds()),
    )
    result = plan.resolve(request)
    if result.status is FulfillmentStatus.FAILED or not result.observations:
        return result, None
    ordered = sorted(result.observations, key=lambda item: item.effective_time)
    closes = tuple(cast(OHLCVBar, item.value).close for item in ordered)
    if len(closes) < 2:
        return result, None
    return result, closes


def _combined_chain_result(
    front_result: CapabilityFulfillmentResult,
    combined_chain: OptionChain,
) -> CapabilityFulfillmentResult:
    """One sealed result representing both expirations' contracts as a
    single logical OPTION_CHAIN_V1 reading -- the same "one logical
    market-data snapshot" modeling choice combine_option_chains() itself
    already documents, applied one level up so MarketSnapshotBuilder's own
    one-fulfillment-per-capability contract (ASA-ARCH-007, unmodified)
    never needs to accept two OPTION_CHAIN_V1 results for one snapshot.
    Reuses the front result's already-validated attempt/observation shell
    via dataclasses.replace(); capability, subject, effective_time,
    provenance, freshness, and completeness all remain exactly as the
    front acquisition already established them -- only the observation's
    own value becomes the combined chain. observation_id is recomputed
    (never carried over): MarketObservation's own __post_init__ requires
    it to be content-derived from every field including value, so reusing
    the front-only observation's own id here would fail that check the
    instant value stops matching what produced it.
    """
    front_observation = front_result.observations[0]
    new_observation_id = market_observation_identity(
        front_observation.provenance.provider_id,
        front_observation.capability,
        front_observation.subject,
        front_observation.effective_time,
        combined_chain,
        front_observation.schema_version,
    )
    combined_observation = dataclasses.replace(
        front_observation, value=combined_chain, observation_id=new_observation_id
    )
    combined_attempt = dataclasses.replace(
        front_result.attempts[0], observations=(combined_observation,)
    )
    return dataclasses.replace(
        front_result, attempts=(combined_attempt,) + front_result.attempts[1:]
    )


def acquire_sealed_earnings_calendar_evidence(
    symbol: str,
    plan: SubjectAcquisitionPlan,
    clock: Clock,
    *,
    provider_metadata: tuple[ProviderMetadata, ...],
    freshness_requirement: FreshnessRequirement = DEFAULT_FRESHNESS_REQUIREMENT,
    resolution_policy_by_capability: dict[MarketCapability, ResolutionPolicy],
) -> SubjectSealedEvidence:
    """Two-phase acquisition (bootstrap -> pure selection -> union),
    sealed into one MarketSnapshot with projected canonical and derived
    facts. Always returns a bundle -- a missing or insufficient capability
    is reflected as an absent canonical/derived fact and an unresolved
    snapshot capability, never an exception. The adapter (strategy_runtime.
    adapters.earnings_calendar) is the one place that decides what an
    absent fact means for its own result.
    """
    now = clock.now()
    requirement = earnings_calendar_requirement()

    # -- Phase 1: bootstrap evidence -----------------------------------
    event_result, event_value = _resolve_or_none(
        plan,
        symbol,
        MarketCapability.EARNINGS_CALENDAR_V1,
        now,
        ("earnings_date",),
        effective_end=now + timedelta(days=requirement.lookahead_days),
    )
    quote_result, quote_value = _resolve_or_none(
        plan,
        symbol,
        MarketCapability.REAL_TIME_QUOTE_V1,
        now,
        ("last",),
        freshness_requirement=freshness_requirement,
    )
    expirations_result, expirations_value = _resolve_expirations_or_none(plan, symbol, now)

    spot_price: Decimal | None = None
    if quote_value is not None:
        try:
            spot_price = _spot_price(cast(Quote, quote_value))
        except Exception:  # noqa: BLE001 -- no usable price means UNKNOWN, not a crash
            spot_price = None

    # -- Strategy-owned selection: pure, no provider access -------------
    chain_result = expirations_result
    closes_result: CapabilityFulfillmentResult | None = None
    term_richness: Decimal | None = None
    iv_rv_richness: Decimal | None = None
    realized_vol: Decimal | None = None
    selected_front_cycle: ExpirationCycle | None = None
    selected_back_cycle: ExpirationCycle | None = None
    selected_target_strike: Decimal | None = None

    if event_value is not None and expirations_value is not None and spot_price is not None:
        available_expirations = expirations_value
        candidates = tuple(
            ExpirationCandidate(cycle.expiration_date, cycle.days_to_expiration)
            for cycle in available_expirations
        )
        earnings_date = _earnings_date(cast(EarningsEvent, event_value))
        selected = select_earnings_relative_expiration_pair(
            candidates,
            earnings_date,
            front_min_dte=requirement.expiration_policy.front_min_dte,
            front_max_dte=requirement.expiration_policy.front_max_dte,
            back_min_dte=requirement.expiration_policy.back_min_dte,
            back_max_dte=requirement.expiration_policy.back_max_dte,
            target_gap_days=requirement.expiration_policy.target_gap_days,
            gap_tolerance_days=requirement.expiration_policy.gap_tolerance_days,
        )
        if selected is not None:
            front_candidate, back_candidate = selected
            front_cycle = next(
                cycle
                for cycle in available_expirations
                if cycle.expiration_date == front_candidate.expiration_date
            )
            back_cycle = next(
                cycle
                for cycle in available_expirations
                if cycle.expiration_date == back_candidate.expiration_date
            )

            # -- Phase 2: union of the remaining demand ------------------
            front_result, front_chain_value = _resolve_or_none(
                plan,
                symbol,
                MarketCapability.OPTION_CHAIN_V1,
                now,
                ("contracts",),
                expiration=front_cycle.expiration_date,
            )
            back_result, back_chain_value = _resolve_or_none(
                plan,
                symbol,
                MarketCapability.OPTION_CHAIN_V1,
                now,
                ("contracts",),
                expiration=back_cycle.expiration_date,
            )

            if front_chain_value is not None and back_chain_value is not None:
                combined_chain = combine_option_chains(
                    (cast(OptionChain, front_chain_value), cast(OptionChain, back_chain_value)),
                    observed_at=now,
                )
                chain_result = _combined_chain_result(front_result, combined_chain)
                front_contract = back_contract = None
                try:
                    front_strike = select_atm_strike_at_expiration(
                        combined_chain, front_cycle.expiration_date, spot_price, OptionType.CALL
                    )
                    back_strike = select_atm_strike_at_expiration(
                        combined_chain, back_cycle.expiration_date, spot_price, OptionType.CALL
                    )
                    (front_contract,) = combined_chain.find(
                        expiration=front_cycle.expiration_date,
                        strike=front_strike,
                        option_type=OptionType.CALL,
                    )
                    (back_contract,) = combined_chain.find(
                        expiration=back_cycle.expiration_date,
                        strike=back_strike,
                        option_type=OptionType.CALL,
                    )
                except Exception:  # noqa: BLE001 -- any selection failure leaves richness UNKNOWN
                    front_contract = back_contract = None
                if (
                    front_contract is not None
                    and back_contract is not None
                    and front_contract.implied_volatility is not None
                    and back_contract.implied_volatility is not None
                ):
                    selected_front_cycle = front_cycle
                    selected_back_cycle = back_cycle
                    selected_target_strike = front_strike
                    term_richness = normalize_richness(
                        front_contract.implied_volatility - back_contract.implied_volatility
                    )
                    closes_result, closes_value = _resolve_closes_or_none(
                        plan, symbol, now, lookback_days=45
                    )
                    if closes_value is not None:
                        realized_vol = compute_realized_volatility(closes_value)
                        iv_rv_richness = normalize_richness(
                            compute_iv_realized_spread(
                                front_contract.implied_volatility, realized_vol
                            )
                        )
                    else:
                        realized_vol = None

    # -- Seal: one MarketSnapshot for whatever was actually resolved ----
    # HISTORICAL_BARS_V1 is deliberately never sealed into the snapshot:
    # its own observations are a genuine time series (many observations
    # from one provider, one per trading day), not competing candidate
    # values for one fact -- ObservationResolver.resolve() requires at
    # most one observation per provider and rejects anything else
    # ("Observation resolution requires one value per provider"), which is
    # correct for quote/event/chain (each is one point-in-time fact) but
    # a genuine shape mismatch for a series. The raw closes are still
    # durably recorded via the plan's own attempt persistence (S14-PR-03)
    # regardless; the meaningful derived value (realized_vol) is captured
    # below as a proper DerivedFact.
    sealed_results = [event_result, quote_result, chain_result]

    snapshot = seal_subject_snapshot(
        tuple(sealed_results),
        as_of=now,
        required_capabilities=_ALWAYS_REQUESTED_CAPABILITIES,
        resolution_policy_by_capability=resolution_policy_by_capability,
        provider_metadata=provider_metadata,
    )

    # -- Project canonical facts (scalars only, never a raw chain/event) --
    canonical_facts: list[CanonicalFact] = []
    resolution_by_capability = {item.capability: item for item in snapshot.resolution_results}
    quote_resolution = resolution_by_capability.get(MarketCapability.REAL_TIME_QUOTE_V1)
    if quote_resolution is not None and spot_price is not None:
        fact = project_canonical_fact(
            quote_resolution,
            value=spot_price,
            fact_id=f"spot_price:{symbol}:{snapshot.snapshot_digest}",
            version=1,
            fact_type="spot_price",
            created_time=now,
        )
        if fact is not None:
            canonical_facts.append(fact)
    event_resolution = resolution_by_capability.get(MarketCapability.EARNINGS_CALENDAR_V1)
    if event_resolution is not None and event_value is not None:
        # CanonicalFact.value must satisfy domain.values.require_normalized,
        # which accepts tz-aware datetimes but not a bare date -- unlike
        # DerivedFact.value (analytics/features.py's DerivedFactValue),
        # which explicitly allows date and is used as-is below for the
        # expiration-date facts.
        earnings_date_value = datetime.combine(
            _earnings_date(cast(EarningsEvent, event_value)), time.min, tzinfo=UTC
        )
        fact = project_canonical_fact(
            event_resolution,
            value=earnings_date_value,
            fact_id=f"earnings_date:{symbol}:{snapshot.snapshot_digest}",
            version=1,
            fact_type="earnings_date",
            created_time=now,
        )
        if fact is not None:
            canonical_facts.append(fact)

    # -- Materialize derived facts ---------------------------------------
    derived_facts: list[DerivedFact] = []
    evidence = (EvidenceReference(EvidenceKind.CANONICAL_FACT, snapshot.snapshot_id),)
    if realized_vol is not None:
        derived_facts.append(
            materialize_derived_fact(
                DERIVED_FACT_REGISTRY,
                REALIZED_VOLATILITY,
                symbol,
                snapshot.snapshot_digest,
                value=realized_vol,
                unit=_ANALYTICS_UNIT_DECIMAL_RATIO,
                effective_time=now,
                input_evidence=evidence,
                quality_status=DerivedFactQualityStatus.VALID,
            )
        )
    # term_structure_richness / iv_realized_volatility_richness are
    # strategy-owned policy, not generic analytics (SPRINT-013 S13-08
    # audit finding #6, project/reports/SPRINT-013-S13-08-audit.md:
    # "richness normalization [is] strategy/manifest-owned policy, not
    # core analytics" -- confirmed, not reversed here). They are
    # DerivedFacts (a deterministic point-in-time calculation over
    # canonical evidence, analytics/features.py's own definition) but
    # deliberately constructed directly rather than through
    # materialize_derived_fact()'s shared AnalyticsRegistry lookup, which
    # would misrepresent them as generic, any-strategy-reusable features.
    # formula_version is the strategy's own manifest version -- the
    # correct authority for a strategy-owned formula's version, not a
    # registry entry that does not and should not exist for it.
    if term_richness is not None:
        derived_facts.append(
            DerivedFact(
                derived_fact_id=derived_fact_id(
                    TERM_STRUCTURE_RICHNESS_FACT, symbol, snapshot.snapshot_digest
                ),
                value=term_richness,
                unit=_ANALYTICS_UNIT_DECIMAL_RATIO,
                formula_version=EARNINGS_CALENDAR_MANIFEST.strategy_version,
                effective_time=now,
                input_evidence=evidence,
                quality_status=DerivedFactQualityStatus.VALID,
            )
        )
    if iv_rv_richness is not None:
        derived_facts.append(
            DerivedFact(
                derived_fact_id=derived_fact_id(
                    IV_REALIZED_RICHNESS_FACT, symbol, snapshot.snapshot_digest
                ),
                value=iv_rv_richness,
                unit=_ANALYTICS_UNIT_DECIMAL_RATIO,
                formula_version=EARNINGS_CALENDAR_MANIFEST.strategy_version,
                effective_time=now,
                input_evidence=evidence,
                quality_status=DerivedFactQualityStatus.VALID,
            )
        )
    # The front/back expiration selection and its target strike are
    # likewise strategy-owned (the manifest's own expiration_select node
    # parameters govern which pair is chosen -- SPRINT-014 S14-PR-02).
    # ExpirationCycle itself is not a DerivedFactValue (that type is a
    # closed Decimal | int | bool | date | tuple[Decimal, ...] union,
    # analytics/features.py's own definition) -- its two fields the graph
    # actually reads (expiration_date, days_to_expiration; monthly/weekly
    # are read nowhere in strategies/stonk_components.py or screening/
    # context_builders.py, confirmed by grep) are sealed individually so
    # the adapter can reconstruct an equivalent ExpirationCycle without
    # ever re-running selection itself.
    if (
        selected_front_cycle is not None
        and selected_back_cycle is not None
        and selected_target_strike is not None
    ):
        derived_facts.append(
            DerivedFact(
                derived_fact_id=derived_fact_id(
                    FRONT_EXPIRATION_DATE_FACT, symbol, snapshot.snapshot_digest
                ),
                value=selected_front_cycle.expiration_date,
                unit=_ANALYTICS_UNIT_CALENDAR_DATE,
                formula_version=EARNINGS_CALENDAR_MANIFEST.strategy_version,
                effective_time=now,
                input_evidence=evidence,
                quality_status=DerivedFactQualityStatus.VALID,
            )
        )
        derived_facts.append(
            DerivedFact(
                derived_fact_id=derived_fact_id(
                    FRONT_DAYS_TO_EXPIRATION_FACT, symbol, snapshot.snapshot_digest
                ),
                value=selected_front_cycle.days_to_expiration,
                unit=_ANALYTICS_UNIT_DAYS,
                formula_version=EARNINGS_CALENDAR_MANIFEST.strategy_version,
                effective_time=now,
                input_evidence=evidence,
                quality_status=DerivedFactQualityStatus.VALID,
            )
        )
        derived_facts.append(
            DerivedFact(
                derived_fact_id=derived_fact_id(
                    BACK_EXPIRATION_DATE_FACT, symbol, snapshot.snapshot_digest
                ),
                value=selected_back_cycle.expiration_date,
                unit=_ANALYTICS_UNIT_CALENDAR_DATE,
                formula_version=EARNINGS_CALENDAR_MANIFEST.strategy_version,
                effective_time=now,
                input_evidence=evidence,
                quality_status=DerivedFactQualityStatus.VALID,
            )
        )
        derived_facts.append(
            DerivedFact(
                derived_fact_id=derived_fact_id(
                    BACK_DAYS_TO_EXPIRATION_FACT, symbol, snapshot.snapshot_digest
                ),
                value=selected_back_cycle.days_to_expiration,
                unit=_ANALYTICS_UNIT_DAYS,
                formula_version=EARNINGS_CALENDAR_MANIFEST.strategy_version,
                effective_time=now,
                input_evidence=evidence,
                quality_status=DerivedFactQualityStatus.VALID,
            )
        )
        derived_facts.append(
            DerivedFact(
                derived_fact_id=derived_fact_id(
                    TARGET_STRIKE_FACT, symbol, snapshot.snapshot_digest
                ),
                value=selected_target_strike,
                unit=_ANALYTICS_UNIT_USD_STRIKE,
                formula_version=EARNINGS_CALENDAR_MANIFEST.strategy_version,
                effective_time=now,
                input_evidence=evidence,
                quality_status=DerivedFactQualityStatus.VALID,
            )
        )

    return SubjectSealedEvidence(
        snapshot=snapshot,
        canonical_facts=tuple(canonical_facts),
        derived_facts=DerivedFactSet(tuple(derived_facts)),
    )
