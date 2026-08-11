"""LIVE-002 live adapter tests.

market_data's deterministic_fixture provider always returns exactly one
option expiration with one strike per side (market_data/fixture.py::
_value), which is not enough for any of the three target strategies' real
selection logic: Forward Factor and Earnings Calendar each need two
expirations spanning a DTE policy window, and Skew Momentum needs multiple
strikes/deltas to select both legs of a vertical spread.
MultiExpirationFixtureProvider overrides only option-chain value
generation to supply four expirations and a seven-strike delta ladder at
each -- everything else (provider_id, capabilities, budget, health,
validate, shutdown) stays the real deterministic_fixture implementation,
still zero network, still fully deterministic.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from domain import (
    AnnouncementTime,
    CanonicalInstrumentIdentity,
    CompletenessMetadata,
    EarningsEvent,
    EvidenceKind,
    EvidenceReference,
    ExpirationCollection,
    ExpirationCycle,
    FreshnessMetadata,
    FreshnessStatus,
    MarketCapability,
    MarketObservation,
    OHLCVBar,
    OHLCVSeries,
    OptionChain,
    OptionContract,
    OptionType,
    ProviderProvenance,
    Quote,
    Security,
    SecurityAssetType,
    market_observation_identity,
)
from domain.strategy_evidence import HistoricalSkewObservation
from market_data import (
    CapabilityFulfillmentService,
    CapabilityRegistry,
    ProviderDependencies,
    ProviderPriority,
    ProviderPriorityPolicy,
    ProviderRegistry,
    load_market_data_config,
)
from market_data.fixture import DeterministicFixtureProvider
from market_data.providers import (
    ProviderAttemptMetadata,
    ProviderErrorCode,
    ProviderFetchResult,
    ProviderResponseMetadata,
    normalized_provider_error,
)
from screening.adapters import TARGET_STRATEGY_REGISTRY
from screening.live_acquisition import build_capability_registry, build_request_budget_manager
from screening.live_adapters import (
    SKEW_MINIMUM_VALID_OBSERVATIONS,
    _acquire_optional_earnings,
    _acquire_or_raise,
    build_live_adapters,
    build_live_skew_momentum_adapter,
    capture_skew_snapshot,
)
from screening.results import ScreeningOutcomeStatus, ScreeningResult
from screening.runner import StrategyAdapterError, run_screening

NOW = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
SYMBOL = "AAPL"


class FixedClock:
    """Advances by one microsecond on every call -- a real clock always
    advances between successive requests too (an HTTP round-trip takes
    measurable time); a frozen clock is the unrealistic case, and collides
    with RequestBudgetPolicy's default burst_limit=1 (keyed by exact
    timestamp) the moment one adapter run needs more than one acquisition
    (every target strategy here does: at least a quote and a chain).
    Deterministic across repeated test runs since it always starts from
    the same NOW and advances by the same fixed increment.
    """

    def __init__(self, start: datetime = NOW) -> None:
        self._next = start

    def now(self) -> datetime:
        current = self._next
        self._next = current + timedelta(microseconds=1)
        return current


# (strike offset from spot, call delta) -- a simple, monotonic, realistic-
# shaped ladder. Put delta is the standard put_delta = call_delta - 1
# relationship. Not precise Black-Scholes, just enough spread for
# _nearest_delta (VerticalStructure's long/short leg selection) to have
# real candidates on both sides of its 0.50/0.25 targets.
_STRIKE_DELTA_LADDER = (
    (Decimal("-15"), Decimal("0.80")),
    (Decimal("-10"), Decimal("0.70")),
    (Decimal("-5"), Decimal("0.60")),
    (Decimal("0"), Decimal("0.50")),
    (Decimal("5"), Decimal("0.35")),
    (Decimal("10"), Decimal("0.25")),
    (Decimal("15"), Decimal("0.15")),
)
_SPOT = Decimal("210")

# (days out, ATM implied_volatility) -- spans both Earnings Calendar's
# front_min/max_dte=7/21, back_min/max_dte=22/75 policy and Forward
# Factor's front_min/max_dte=35/90, back_min/max_dte=49/139, gap 14-49
# policy, with the earnings pair exactly 30 days apart, deliberately
# without the two ranges overlapping, so each
# strategy's selector has exactly one unambiguous valid pair.
_EXPIRATIONS_DAYS_OUT_AND_IV = (
    (10, Decimal("0.55")),
    (40, Decimal("0.50")),
    (61, Decimal("0.48")),
    (91, Decimal("0.4548992562461861547567860943472296")),
)


def _synthetic_daily_bars_fetch_result(provider, request):  # noqa: ANN001
    """SPRINT-014 S14-PR-05A (Founder-approved bounded contract extension):
    one historical-bars request legitimately covers many trading days, but
    -- like market_data/tradier.py's own current _normalize() -- bundles
    every bar into one OHLCVSeries value, sealed into exactly one
    MarketObservation, so a generic, single-observation-per-demand
    consumer (screening.subject_planning/market_data.subject_snapshot's
    own ObservationResolver, which requires at most one observation per
    provider per capability) can resolve this capability at all. Updated
    from this fixture's own original SPRINT-011-CLOSEOUT/CLOSE-002 shape
    (one MarketObservation per day) once market_data/tradier.py's real
    shape moved to the OHLCVSeries contract -- DeterministicFixtureProvider
    .fetch() returns exactly one observation per request regardless of
    capability, not enough for realized-volatility/momentum computation,
    so this still needs its own real, non-constant close series instead of
    the base provider's single fixed bar. Shared by every fixture provider
    in this module that needs one.
    """
    received_at = provider._dependencies.clock.now().astimezone(UTC)  # noqa: SLF001
    reference = provider._request_reference(request)  # noqa: SLF001
    response = ProviderResponseMetadata(
        provider.provider_id,
        reference,
        received_at,
        "fixture",
        provider._scenario.latency_milliseconds,  # noqa: SLF001
        0,
        (("network_requests", "0"),),
    )
    attempt = ProviderAttemptMetadata(provider.provider_id, request.capability, 1, 1, response)
    (subject,) = request.subjects
    instrument = subject.canonical_instrument
    bars = []
    for day_offset in range(29, -1, -1):
        observed_at = received_at - timedelta(days=day_offset)
        # Deterministic drift + oscillation, never a flat series, so
        # realized volatility and trailing momentum are both genuinely
        # non-zero.
        close = Decimal("200") + Decimal(day_offset % 5) + Decimal(str((29 - day_offset) * 0.15))
        bars.append(
            OHLCVBar(
                instrument,
                86400,
                observed_at - timedelta(days=1),
                observed_at,
                close - Decimal("2"),
                close + Decimal("2"),
                close - Decimal("3"),
                close,
                Decimal("50000000"),
            )
        )
    series = OHLCVSeries(instrument, 86400, received_at, tuple(bars))
    evidence = (EvidenceReference(EvidenceKind.OBSERVATION, "fixture-bars-series"),)
    identity = market_observation_identity(
        provider.provider_id, request.capability, subject, received_at, series, "v1"
    )
    observation = MarketObservation(
        identity,
        request.capability,
        subject,
        received_at,
        received_at,
        series,
        "v1",
        ProviderProvenance(provider.provider_id, reference, evidence),
        FreshnessMetadata(
            received_at, received_at, request.maximum_age_seconds, 0, FreshnessStatus.FRESH
        ),
        CompletenessMetadata(
            subject.request_context.required_fields,
            subject.request_context.required_fields,
            (),
        ),
    )
    return ProviderFetchResult((observation,), None, (attempt,))


class MultiExpirationFixtureProvider(DeterministicFixtureProvider):
    """deterministic_fixture with a four-expiration, multi-strike option
    chain -- still zero network, still fully deterministic, only the
    chain's *shape* changes, so every target strategy's real selection
    logic (DTE-window pairing, earnings-relative pairing, delta-based leg
    selection) has genuine candidates to choose from instead of exactly
    one contract per side.
    """

    def _value(self, subject, address, observed_at, evidence):  # noqa: ANN001
        instrument = subject.canonical_instrument
        capability = subject.requested_capability
        if capability is MarketCapability.REAL_TIME_QUOTE_V1:
            return Quote(
                instrument,
                _SPOT - Decimal("0.10"),
                _SPOT + Decimal("0.10"),
                _SPOT,
                Decimal("100"),
                Decimal("120"),
                Decimal("1000000"),
                instrument.currency,
            )
        security = Security(instrument, address.upper(), SecurityAssetType.EQUITY, "XNAS")
        if capability is MarketCapability.EARNINGS_CALENDAR_V1:
            event_date = observed_at.date() + timedelta(days=14)
            return EarningsEvent(
                f"fixture:{address}:{event_date.isoformat()}",
                security,
                event_date,
                AnnouncementTime.AFTER_CLOSE,
                Decimal("0.05"),
                True,
                (),
                observed_at,
                evidence,
            )
        if capability is MarketCapability.HISTORICAL_BARS_V1:
            return OHLCVBar(
                instrument,
                86400,
                observed_at - timedelta(days=1),
                observed_at,
                Decimal("205"),
                Decimal("212"),
                Decimal("204"),
                Decimal("210"),
                Decimal("50000000"),
            )
        required_fields = subject.request_context.required_fields
        if "expirations" in required_fields and "contracts" not in required_fields:
            # SPRINT-014 S14-PR-05A (Founder-approved bounded contract
            # extension): matches market_data/tradier.py's own real
            # discrimination -- an expirations-only OPTION_CHAIN_V1
            # request normalizes to one ExpirationCollection, never a full
            # chain, so a generic subject-first consumer resolving this
            # capability's own discovery demand sees the same shape a real
            # provider returns, not a fixture-only special case.
            as_of = observed_at.date()
            unique_dates = sorted(
                {as_of + timedelta(days=days_out) for days_out, _ in _EXPIRATIONS_DAYS_OUT_AND_IV}
            )
            return ExpirationCollection(
                as_of,
                tuple(
                    ExpirationCycle(
                        expiration,
                        (expiration - as_of).days,
                        expiration.weekday() == 4 and 15 <= expiration.day <= 21,
                        not (expiration.weekday() == 4 and 15 <= expiration.day <= 21),
                        as_of,
                        evidence,
                    )
                    for expiration in unique_dates
                ),
            )
        contracts = tuple(
            OptionContract(
                CanonicalInstrumentIdentity(
                    "fixture-option",
                    f"{address}-{days_out}-{_SPOT + offset}-{kind.value}",
                ),
                security,
                observed_at.date() + timedelta(days=days_out),
                _SPOT + offset,
                kind,
                Decimal("4.90"),
                Decimal("5.10"),
                Decimal("5.00"),
                1000,
                5000,
                call_delta if kind is OptionType.CALL else call_delta - 1,
                Decimal("0.03"),
                Decimal("-0.10"),
                Decimal("0.20"),
                Decimal("0.01"),
                iv,
                observed_at,
                evidence,
            )
            for days_out, iv in _EXPIRATIONS_DAYS_OUT_AND_IV
            for offset, call_delta in _STRIKE_DELTA_LADDER
            for kind in (OptionType.CALL, OptionType.PUT)
        )
        return OptionChain(
            f"fixture:{address}:multi-expiration", security, observed_at, contracts, evidence
        )

    def fetch(self, request, budget):  # noqa: ANN001
        # SPRINT-011-CLOSEOUT/CLOSE-002: see _synthetic_daily_bars_fetch_result's
        # own docstring. Every other capability still goes through the
        # real base implementation.
        if request.capability is not MarketCapability.HISTORICAL_BARS_V1:
            return super().fetch(request, budget)
        return _synthetic_daily_bars_fetch_result(self, request)


class CapturingMultiExpirationFixtureProvider(MultiExpirationFixtureProvider):
    requests: list[object] = []

    def fetch(self, request, budget):  # noqa: ANN001
        type(self).requests.append(request)
        return super().fetch(request, budget)


class AsymmetricForwardFactorFixtureProvider(MultiExpirationFixtureProvider):
    """GS/MU-shaped front/back ladders whose nearest front strikes are absent later."""

    def _value(self, subject, address, observed_at, evidence):  # noqa: ANN001
        value = super()._value(subject, address, observed_at, evidence)
        if not isinstance(value, OptionChain):
            return value
        back_expiration = observed_at.date() + timedelta(days=91)
        omitted = {
            (OptionType.PUT, _SPOT - Decimal("10")),
            (OptionType.CALL, _SPOT + Decimal("5")),
        }
        return OptionChain(
            value.option_chain_id,
            value.underlying,
            value.observed_at,
            tuple(
                item
                for item in value.contracts
                if not (
                    item.expiration == back_expiration
                    and (item.option_type, item.strike) in omitted
                )
            ),
            value.evidence,
        )


class UnconfirmedEarningsFixtureProvider(MultiExpirationFixtureProvider):
    def _value(self, subject, address, observed_at, evidence):  # noqa: ANN001
        value = super()._value(subject, address, observed_at, evidence)
        if isinstance(value, EarningsEvent):
            return EarningsEvent(
                value.earnings_event_id,
                value.security,
                value.earnings_date,
                value.announcement_time,
                value.estimated_move,
                False,
                value.historical_sequence,
                value.observed_at,
                value.evidence,
            )
        return value


def _no_transport(_provider_id: str) -> object:
    return object()


def _fulfillment(
    provider_cls=DeterministicFixtureProvider,
    clock: FixedClock | None = None,
    *,
    burst_limit: int | None = None,
):
    # One shared clock instance for both the budget manager and the
    # provider's dependencies: RequestBudgetManager.authorize()'s burst-key
    # is keyed by *its own* clock reading, independent of whatever clock a
    # caller later passes to run_screening() -- sharing one advancing
    # instance here is what actually avoids burst collisions across the
    # several acquisitions one adapter run makes (a quote and a chain, at
    # minimum).
    #
    # burst_limit override: the configured default (market_data/config.py's
    # RequestBudgetConfig) is sized for one strategy per pair -- the real
    # production shape (asa/scheduled_screening.py builds one budget per
    # (signal_id, symbol) pair). Tests that deliberately run every target
    # strategy together against one shared budget (TARGET_STRATEGY_REGISTRY
    # with no strategy_ids filter -- itself a real screening/cli.py --live
    # multi-strategy path, just not the automated scheduled one) need more
    # headroom than any single real pair does; pass it explicitly here
    # rather than inflating the global default for every single-strategy
    # caller.
    shared_clock = clock or FixedClock()
    config = load_market_data_config({})
    (fixture_config,) = tuple(item for item in config.providers if item.enabled)
    if burst_limit is not None:
        fixture_config = dataclasses.replace(
            fixture_config,
            request_budget=dataclasses.replace(
                fixture_config.request_budget, burst_limit=burst_limit
            ),
        )
    budget_manager = build_request_budget_manager((fixture_config,), shared_clock)
    provider = provider_cls(
        fixture_config, ProviderDependencies(object(), shared_clock, budget_manager)
    )
    registry = ProviderRegistry((provider,))
    capability_registry = build_capability_registry(registry)
    return CapabilityFulfillmentService(registry, capability_registry, budget_manager), shared_clock


class TestSkewMomentumLiveNeedsMultipleStrikes:
    def test_reports_strategy_exception_against_the_single_strike_default_fixture(self) -> None:
        """The plain deterministic_fixture provider has exactly one call
        and one put per expiration -- VerticalStructure's short-leg,
        delta-target selection has no second strike to choose from. This
        is a genuine data-richness requirement, not an artifact of this
        test's own setup -- the same failure would occur against any real
        chain missing sufficient strikes.
        """
        fulfillment, clock = _fulfillment()
        adapters = build_live_adapters(SYMBOL, fulfillment)
        (result,) = run_screening(
            TARGET_STRATEGY_REGISTRY,
            adapters,
            clock,
            strategy_ids=("skew_momentum",),
        )
        assert result.outcome_status is ScreeningOutcomeStatus.STRATEGY_EXCEPTION

    def test_produces_a_valid_pass_result_against_the_multi_strike_fixture(self) -> None:
        fulfillment, clock = _fulfillment(MultiExpirationFixtureProvider)
        adapters = build_live_adapters(SYMBOL, fulfillment)
        (result,) = run_screening(
            TARGET_STRATEGY_REGISTRY,
            adapters,
            clock,
            strategy_ids=("skew_momentum",),
        )
        assert result.outcome_status in (
            ScreeningOutcomeStatus.PASS,
            ScreeningOutcomeStatus.NO_SIGNAL,
        )
        assert result.subject_identity == f"symbol:{SYMBOL}"

    def test_requests_bounded_history_horizon_proven_for_sparse_live_series(self) -> None:
        CapturingMultiExpirationFixtureProvider.requests.clear()
        fulfillment, clock = _fulfillment(CapturingMultiExpirationFixtureProvider)
        adapters = build_live_adapters(SYMBOL, fulfillment)

        run_screening(
            TARGET_STRATEGY_REGISTRY,
            adapters,
            clock,
            strategy_ids=("skew_momentum",),
        )

        request = next(
            item
            for item in CapturingMultiExpirationFixtureProvider.requests
            if item.capability is MarketCapability.HISTORICAL_BARS_V1  # type: ignore[attr-defined]
        )
        assert request.effective_end - request.effective_start == timedelta(days=180)  # type: ignore[attr-defined]


class _StubHistoricalSkewRepository:
    """Structurally satisfies screening.live_adapters.
    HistoricalSkewHistoryReader via duck typing -- no shared base class,
    matching that Protocol's own file-local, zero-import-coupling design.
    """

    def __init__(self, observations: tuple[HistoricalSkewObservation, ...] = ()) -> None:
        self._observations = observations

    def history_for(
        self,
        instrument: CanonicalInstrumentIdentity,
        *,
        as_of: datetime | None = None,
        maximum_observations: int | None = None,
    ) -> tuple[HistoricalSkewObservation, ...]:
        return self._observations


def _historical_skew_observations(count: int) -> tuple[HistoricalSkewObservation, ...]:
    instrument = CanonicalInstrumentIdentity("symbol", SYMBOL)
    evidence = (EvidenceReference(EvidenceKind.OBSERVATION, "fixture-skew-history"),)
    return tuple(
        HistoricalSkewObservation(
            instrument=instrument,
            call_skew=Decimal("0.01") + Decimal(i) * Decimal("0.001"),
            put_skew=Decimal("0.02") + Decimal(i) * Decimal("0.001"),
            effective_time=NOW - timedelta(days=count - i),
            evidence=evidence,
        )
        for i in range(count)
    )


class TestSkewMomentumHistoricalEvidenceReadPath:
    """SPRINT-013 S13-04D: call_skew_zscore/put_skew_zscore/historical_
    valid_observations wired from an injected repository's own history_for()
    -- never a proxy, always UNKNOWN (None) below the approved minimum or
    with no repository at all.
    """

    def _run(self, repository: _StubHistoricalSkewRepository | None) -> ScreeningResult:
        fulfillment, clock = _fulfillment(MultiExpirationFixtureProvider)
        adapters = {
            "skew_momentum": build_live_skew_momentum_adapter(
                SYMBOL, fulfillment, historical_skew_repository=repository
            )
        }
        (result,) = run_screening(
            TARGET_STRATEGY_REGISTRY, adapters, clock, strategy_ids=("skew_momentum",)
        )
        assert result.explanation is not None
        return result

    def test_no_repository_leaves_historical_evidence_unknown(self) -> None:
        result = self._run(None)
        assert result.explanation is not None
        facts = dict(result.explanation.canonical_facts)
        derived = dict(result.explanation.named_derived_facts)
        assert facts["historical_valid_observations"] == 0
        assert derived["call_skew_zscore"] is None
        assert derived["put_skew_zscore"] is None

    def test_below_minimum_history_leaves_zscore_unknown_but_reports_true_count(self) -> None:
        below_minimum = SKEW_MINIMUM_VALID_OBSERVATIONS - 1
        repository = _StubHistoricalSkewRepository(_historical_skew_observations(below_minimum))
        result = self._run(repository)
        assert result.explanation is not None
        facts = dict(result.explanation.canonical_facts)
        derived = dict(result.explanation.named_derived_facts)
        assert facts["historical_valid_observations"] == below_minimum
        assert derived["call_skew_zscore"] is None
        assert derived["put_skew_zscore"] is None

    def test_at_minimum_history_computes_a_real_zscore(self) -> None:
        repository = _StubHistoricalSkewRepository(
            _historical_skew_observations(SKEW_MINIMUM_VALID_OBSERVATIONS)
        )
        result = self._run(repository)
        assert result.explanation is not None
        facts = dict(result.explanation.canonical_facts)
        derived = dict(result.explanation.named_derived_facts)
        assert facts["historical_valid_observations"] == SKEW_MINIMUM_VALID_OBSERVATIONS
        assert isinstance(derived["call_skew_zscore"], Decimal)
        assert isinstance(derived["put_skew_zscore"], Decimal)


class TestCaptureSkewSnapshot:
    """SPRINT-013 S13-04D: capture_skew_snapshot is pure acquisition and
    packaging -- it never decides whether a candidate may be recorded
    (that is strategy_runtime.historical_evidence.record_prospective_
    skew_observation's own, sole responsibility), and it never invents an
    instrument scheme other than the codebase's own established "symbol"
    convention for a live equity/ETF ticker.
    """

    def test_returns_an_observation_matching_the_live_signals_own_computed_skew(self) -> None:
        fulfillment, clock = _fulfillment(MultiExpirationFixtureProvider)
        now = clock.now()
        observation = capture_skew_snapshot(fulfillment, SYMBOL, now)
        assert observation.instrument == CanonicalInstrumentIdentity("symbol", SYMBOL)
        assert observation.evidence

    def test_effective_time_and_evidence_come_from_the_acquired_chain(self) -> None:
        fulfillment, clock = _fulfillment(MultiExpirationFixtureProvider)
        now = clock.now()
        observation = capture_skew_snapshot(fulfillment, SYMBOL, now)
        assert abs(observation.effective_time - now) < timedelta(seconds=1)
        assert all(item.kind is EvidenceKind.OBSERVATION for item in observation.evidence)


class TestForwardFactorAndEarningsCalendarNeedTwoExpirations:
    def test_confirmed_no_event_survives_another_providers_transient_failure(self) -> None:
        class _Fulfillment:
            def fulfill(self, _request, **_kwargs):  # noqa: ANN001, ANN202
                return SimpleNamespace(
                    observations=(),
                    attempts=(
                        SimpleNamespace(
                            error=SimpleNamespace(code=ProviderErrorCode.RATE_LIMITED)
                        ),
                        SimpleNamespace(error=SimpleNamespace(code=ProviderErrorCode.NO_DATA)),
                    ),
                )

        assert (
            _acquire_optional_earnings(
                _Fulfillment(), SYMBOL, NOW, NOW.date() + timedelta(days=60)  # type: ignore[arg-type]
            )
            is None
        )

    def test_forward_factor_reports_missing_data_against_the_single_expiration_default_fixture(
        self,
    ) -> None:
        fulfillment, clock = _fulfillment()
        adapters = build_live_adapters(SYMBOL, fulfillment)
        (result,) = run_screening(
            TARGET_STRATEGY_REGISTRY,
            adapters,
            clock,
            strategy_ids=("forward_factor",),
        )
        assert result.outcome_status is ScreeningOutcomeStatus.MISSING_DATA
        assert result.failure_detail is not None
        assert "DTE policy" in result.failure_detail

    def test_forward_factor_succeeds_against_the_two_expiration_fixture(self) -> None:
        fulfillment, clock = _fulfillment(MultiExpirationFixtureProvider)
        adapters = build_live_adapters(SYMBOL, fulfillment)
        (result,) = run_screening(
            TARGET_STRATEGY_REGISTRY,
            adapters,
            clock,
            strategy_ids=("forward_factor",),
        )
        assert result.outcome_status in (
            ScreeningOutcomeStatus.PASS,
            ScreeningOutcomeStatus.NO_SIGNAL,
        )
        assert result.subject_identity == f"symbol:{SYMBOL}"
        assert result.signal_classification == "FAIL"

    def test_forward_factor_asymmetric_ladders_return_normal_outcome(self) -> None:
        fulfillment, clock = _fulfillment(AsymmetricForwardFactorFixtureProvider)
        adapters = build_live_adapters(SYMBOL, fulfillment)
        (result,) = run_screening(
            TARGET_STRATEGY_REGISTRY,
            adapters,
            clock,
            strategy_ids=("forward_factor",),
        )

        assert result.outcome_status in (
            ScreeningOutcomeStatus.PASS,
            ScreeningOutcomeStatus.NO_SIGNAL,
        )
        assert result.subject_identity == f"symbol:{SYMBOL}"
        assert result.failure_detail is None

    def test_unconfirmed_earnings_does_not_trigger_exclusion(self) -> None:
        fulfillment, clock = _fulfillment(UnconfirmedEarningsFixtureProvider)
        adapters = build_live_adapters(SYMBOL, fulfillment)
        (result,) = run_screening(
            TARGET_STRATEGY_REGISTRY,
            adapters,
            clock,
            strategy_ids=("forward_factor",),
        )
        assert result.signal_classification in {"PASS", "WATCH"}

    def test_earnings_calendar_succeeds_against_the_two_expiration_fixture(self) -> None:
        fulfillment, clock = _fulfillment(MultiExpirationFixtureProvider)
        adapters = build_live_adapters(SYMBOL, fulfillment)
        (result,) = run_screening(
            TARGET_STRATEGY_REGISTRY,
            adapters,
            clock,
            strategy_ids=("earnings_calendar",),
        )
        assert result.outcome_status in (
            ScreeningOutcomeStatus.PASS,
            ScreeningOutcomeStatus.NO_SIGNAL,
        )
        assert result.subject_identity == f"symbol:{SYMBOL}"

    def test_earnings_calendar_requests_the_complete_upcoming_policy_window(self) -> None:
        CapturingMultiExpirationFixtureProvider.requests.clear()
        fulfillment, clock = _fulfillment(CapturingMultiExpirationFixtureProvider)
        adapters = build_live_adapters(SYMBOL, fulfillment)
        run_screening(
            TARGET_STRATEGY_REGISTRY,
            adapters,
            clock,
            strategy_ids=("earnings_calendar",),
        )
        request = next(
            item
            for item in CapturingMultiExpirationFixtureProvider.requests
            if item.capability is MarketCapability.EARNINGS_CALENDAR_V1  # type: ignore[attr-defined]
        )
        assert request.effective_end - request.effective_start == timedelta(days=75)  # type: ignore[attr-defined]
        assert request.subjects[0].request_context.semantic_end == request.effective_end  # type: ignore[attr-defined]


class TestCapabilityNotOfferedByAnyEnabledProvider:
    def test_earnings_calendar_reports_missing_data_not_strategy_exception(self) -> None:
        """A real deployment might enable only a provider that doesn't
        serve earnings data at all (e.g. only Tradier). CapabilityRegistry
        .lookup() raises DomainInvariantError in that case rather than
        returning a not-fulfilled result -- _acquire_or_raise must still
        convert that into a clean, isolated MISSING_DATA outcome per this
        module's own documented contract, never let it escape as a raw
        exception into the runner's generic STRATEGY_EXCEPTION handling.
        """
        shared_clock = FixedClock()
        config = load_market_data_config({})
        (fixture_config,) = tuple(item for item in config.providers if item.enabled)
        budget_manager = build_request_budget_manager((fixture_config,), shared_clock)
        provider = MultiExpirationFixtureProvider(
            fixture_config, ProviderDependencies(object(), shared_clock, budget_manager)
        )
        registry = ProviderRegistry((provider,))
        priorities = tuple(
            ProviderPriority(capability, (provider.provider_id,))
            for capability in provider.capabilities
            if capability is not MarketCapability.EARNINGS_CALENDAR_V1
        )
        capability_registry = CapabilityRegistry(
            registry, ProviderPriorityPolicy("test-v1", priorities)
        )
        fulfillment = CapabilityFulfillmentService(registry, capability_registry, budget_manager)
        adapters = build_live_adapters(SYMBOL, fulfillment)
        (result,) = run_screening(
            TARGET_STRATEGY_REGISTRY, adapters, shared_clock, strategy_ids=("earnings_calendar",)
        )
        assert result.outcome_status is ScreeningOutcomeStatus.MISSING_DATA
        assert result.failure_detail is not None
        assert "no enabled provider declares or satisfies" in result.failure_detail


class TestFullLiveRunAcrossAllThreeStrategies:
    def test_all_three_run_and_are_isolated_from_each_other(self) -> None:
        # All three strategies deliberately share one budget here (no
        # strategy_ids filter) -- see _fulfillment()'s burst_limit
        # docstring for why this needs more headroom than one pair's own
        # production-shaped budget.
        fulfillment, clock = _fulfillment(MultiExpirationFixtureProvider, burst_limit=20)
        adapters = build_live_adapters(SYMBOL, fulfillment)
        results = run_screening(TARGET_STRATEGY_REGISTRY, adapters, clock)
        assert {result.strategy_id for result in results} == {
            "earnings_calendar",
            "forward_factor",
            "skew_momentum",
        }
        assert all(result.subject_identity == f"symbol:{SYMBOL}" for result in results)


class TradierShapedMultiExpirationProvider(DeterministicFixtureProvider):
    """Reproduces real Tradier's actual two-step option-chain acquisition
    shape (market_data/tradier.py's own required_fields branching), unlike
    MultiExpirationFixtureProvider above (which -- like the real offline
    fixture -- always returns every expiration's contracts in one unscoped
    response, regardless of what was asked for). Each OPTION_CHAIN_V1
    contracts request here is scoped to exactly the expiration named in the
    subject's own "expiration" projection -- looked up the same way real
    Tradier looks it up (subject.projection_for(self.provider_id,
    "expiration", ...)), so this proves TRADIER-PATCH-003's adapters
    actually drive the real two-step flow (discover expirations, select,
    acquire per expiration), not just that they still work against a
    provider generous enough not to need it.

    option_chain_requests records every OPTION_CHAIN_V1 request's
    required_fields, in order, for request-count and deduplication
    assertions.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.option_chain_requests: list[tuple[str, ...]] = []

    def fetch(self, request, budget):  # noqa: ANN001
        if request.capability is MarketCapability.OPTION_CHAIN_V1:
            self.option_chain_requests.append(request.required_fields)
            if (
                "expirations" in request.required_fields
                and "contracts" not in request.required_fields
            ):
                return self._expirations_response(request)
            if "contracts" in request.required_fields:
                return self._chain_response_for_one_expiration(request)
        if request.capability is MarketCapability.HISTORICAL_BARS_V1:
            return _synthetic_daily_bars_fetch_result(self, request)
        return super().fetch(request, budget)

    def _attempt(self, request, reference, received_at):  # noqa: ANN001
        response = ProviderResponseMetadata(
            self.provider_id, reference, received_at, "fixture", 0, 0, (("network_requests", "0"),)
        )
        return ProviderAttemptMetadata(self.provider_id, request.capability, 1, 1, response)

    def _expirations_response(self, request):  # noqa: ANN001
        received_at = self._dependencies.clock.now().astimezone(UTC)
        reference = self._request_reference(request)
        (subject,) = request.subjects
        as_of = received_at.date()
        evidence = (EvidenceReference(EvidenceKind.OBSERVATION, "test:tradier-shaped-multi"),)
        observations = tuple(
            MarketObservation(
                market_observation_identity(
                    self.provider_id, request.capability, subject, received_at, cycle, "v1"
                ),
                request.capability,
                subject,
                received_at,
                received_at,
                cycle,
                "v1",
                ProviderProvenance(self.provider_id, reference, evidence),
                FreshnessMetadata(
                    received_at, received_at, request.maximum_age_seconds, 0, FreshnessStatus.FRESH
                ),
                CompletenessMetadata(request.required_fields, request.required_fields, ()),
            )
            for cycle in (
                ExpirationCycle(
                    as_of + timedelta(days=days_out), days_out, False, True, as_of, evidence
                )
                for days_out, _iv in _EXPIRATIONS_DAYS_OUT_AND_IV
            )
        )
        return ProviderFetchResult(
            observations, None, (self._attempt(request, reference, received_at),)
        )

    def _chain_response_for_one_expiration(self, request):  # noqa: ANN001
        (subject,) = request.subjects
        projection = subject.projection_for(self.provider_id, "expiration", request.effective_end)
        expiration = date.fromisoformat(projection.address_value)
        received_at = self._dependencies.clock.now().astimezone(UTC)
        reference = self._request_reference(request)
        as_of = received_at.date()
        days_out = (expiration - as_of).days
        iv = next(iv for offset_days, iv in _EXPIRATIONS_DAYS_OUT_AND_IV if offset_days == days_out)
        symbol = subject.canonical_instrument.display_symbol
        security = Security(
            subject.canonical_instrument, symbol.upper(), SecurityAssetType.EQUITY, "XNAS"
        )
        evidence = (
            EvidenceReference(
                EvidenceKind.OBSERVATION, f"test:tradier-shaped-chain:{expiration.isoformat()}"
            ),
        )
        contracts = tuple(
            OptionContract(
                CanonicalInstrumentIdentity(
                    "fixture-option",
                    f"{symbol}-{expiration.isoformat()}-{_SPOT + offset}-{kind.value}",
                ),
                security,
                expiration,
                _SPOT + offset,
                kind,
                Decimal("4.90"),
                Decimal("5.10"),
                Decimal("5.00"),
                1000,
                5000,
                call_delta if kind is OptionType.CALL else call_delta - 1,
                Decimal("0.03"),
                Decimal("-0.10"),
                Decimal("0.20"),
                Decimal("0.01"),
                iv,
                received_at,
                evidence,
            )
            for offset, call_delta in _STRIKE_DELTA_LADDER
            for kind in (OptionType.CALL, OptionType.PUT)
        )
        chain = OptionChain(
            f"test:tradier-shaped:{expiration.isoformat()}",
            security,
            received_at,
            contracts,
            evidence,
        )
        observation = MarketObservation(
            market_observation_identity(
                self.provider_id, request.capability, subject, received_at, chain, "v1"
            ),
            request.capability,
            subject,
            received_at,
            received_at,
            chain,
            "v1",
            ProviderProvenance(self.provider_id, reference, evidence),
            FreshnessMetadata(
                received_at, received_at, request.maximum_age_seconds, 0, FreshnessStatus.FRESH
            ),
            CompletenessMetadata(request.required_fields, request.required_fields, ()),
        )
        return ProviderFetchResult(
            (observation,), None, (self._attempt(request, reference, received_at),)
        )


class TestTwoStepLiveAcquisitionAgainstATradierShapedProvider:
    def test_forward_factor_receives_front_and_back_expiration_chains(self) -> None:
        fulfillment, clock = _fulfillment(TradierShapedMultiExpirationProvider)
        adapters = build_live_adapters(SYMBOL, fulfillment)
        (result,) = run_screening(
            TARGET_STRATEGY_REGISTRY, adapters, clock, strategy_ids=("forward_factor",)
        )
        assert result.outcome_status in (
            ScreeningOutcomeStatus.PASS,
            ScreeningOutcomeStatus.NO_SIGNAL,
        )

    def test_skew_momentum_receives_its_one_required_expiration_chain(self) -> None:
        fulfillment, clock = _fulfillment(TradierShapedMultiExpirationProvider)
        adapters = build_live_adapters(SYMBOL, fulfillment)
        (result,) = run_screening(
            TARGET_STRATEGY_REGISTRY, adapters, clock, strategy_ids=("skew_momentum",)
        )
        assert result.outcome_status in (
            ScreeningOutcomeStatus.PASS,
            ScreeningOutcomeStatus.NO_SIGNAL,
        )

    def test_forward_factor_makes_exactly_three_option_chain_requests(self) -> None:
        # One expirations-only request, one contracts request per selected
        # expiration (front, back) -- proves the two-step flow, not a
        # single all-expirations fetch. Constructed directly (not via
        # _fulfillment()) to keep a direct reference to the provider
        # instance for its own request-log, without reaching into
        # CapabilityFulfillmentService's private internals.
        shared_clock = FixedClock()
        config = load_market_data_config({})
        (fixture_config,) = tuple(item for item in config.providers if item.enabled)
        budget_manager = build_request_budget_manager((fixture_config,), shared_clock)
        provider = TradierShapedMultiExpirationProvider(
            fixture_config, ProviderDependencies(object(), shared_clock, budget_manager)
        )
        registry = ProviderRegistry((provider,))
        capability_registry = build_capability_registry(registry)
        fulfillment = CapabilityFulfillmentService(registry, capability_registry, budget_manager)
        adapters = build_live_adapters(SYMBOL, fulfillment)
        run_screening(
            TARGET_STRATEGY_REGISTRY, adapters, shared_clock, strategy_ids=("forward_factor",)
        )
        assert len(provider.option_chain_requests) == 3
        assert provider.option_chain_requests[0] == ("expirations",)
        assert all(request == ("contracts",) for request in provider.option_chain_requests[1:])

    def test_a_failed_expiration_specific_chain_request_does_not_crash_the_run(self) -> None:
        # The back-expiration chain request fails (a genuine per-request
        # provider failure -- rate limit, timeout, bad data -- unrelated to
        # whether the front request already succeeded); the whole
        # screening run must still isolate this as one MISSING_DATA result
        # for forward_factor, not crash or corrupt the other strategies.
        class _BackExpirationFailsProvider(TradierShapedMultiExpirationProvider):
            def _chain_response_for_one_expiration(self, request):  # noqa: ANN001
                (subject,) = request.subjects
                projection = subject.projection_for(
                    self.provider_id, "expiration", request.effective_end
                )
                expiration = date.fromisoformat(projection.address_value)
                if (expiration - self._dependencies.clock.now().date()).days >= 49:
                    reference = self._request_reference(request)
                    received_at = self._dependencies.clock.now().astimezone(UTC)
                    error = normalized_provider_error(
                        ProviderErrorCode.PROVIDER_UNAVAILABLE,
                        "simulated back-expiration failure",
                        self.provider_id,
                        request.capability,
                        reference,
                    )
                    return ProviderFetchResult(
                        (), error, (self._attempt(request, reference, received_at),)
                    )
                return super()._chain_response_for_one_expiration(request)

        # All three strategies deliberately share one budget here (no
        # strategy_ids filter) -- see _fulfillment()'s burst_limit
        # docstring.
        fulfillment, clock = _fulfillment(_BackExpirationFailsProvider, burst_limit=20)
        adapters = build_live_adapters(SYMBOL, fulfillment)
        results = run_screening(TARGET_STRATEGY_REGISTRY, adapters, clock)
        by_strategy = {result.strategy_id: result for result in results}
        assert by_strategy["forward_factor"].outcome_status is ScreeningOutcomeStatus.MISSING_DATA
        # skew_momentum only needs one (front-month) expiration, unaffected
        # by the back-expiration failure -- proves isolation is per
        # acquisition, not a whole-provider outage.
        assert by_strategy["skew_momentum"].outcome_status in (
            ScreeningOutcomeStatus.PASS,
            ScreeningOutcomeStatus.NO_SIGNAL,
        )


class TestAcquisitionErrorClassificationEndToEnd:
    def test_a_selected_provider_with_a_malformed_subject_is_invalid_acquisition_subject(
        self,
    ) -> None:
        # A regression guard for #156's original defect class: if a caller
        # ever again asks TradierShapedMultiExpirationProvider for
        # OPTION_CHAIN_V1 contracts without supplying an expiration
        # (exactly the bug TRADIER-PATCH-002 fixed), the provider IS
        # selected -- CapabilityRegistry finds it -- but its own
        # subject.projection_for(..., "expiration", ...) lookup fails.
        # _acquire_or_raise must classify this as invalid_acquisition_subject,
        # never the no_capable_provider message (a provider WAS selected).
        fulfillment, clock = _fulfillment(TradierShapedMultiExpirationProvider)
        try:
            _acquire_or_raise(
                fulfillment,
                SYMBOL,
                MarketCapability.OPTION_CHAIN_V1,
                clock.now(),
                ("contracts",),
                # expiration deliberately omitted.
            )
            raise AssertionError("expected StrategyAdapterError")
        except StrategyAdapterError as error:
            assert error.outcome_status is ScreeningOutcomeStatus.MISSING_DATA
            assert "a provider was selected for option_chain_v1 for AAPL" in str(error)
            assert "canonical request subject was incomplete or invalid" in str(error)
            assert "no enabled provider declares" not in str(error)

    def test_no_capable_provider_is_never_reported_as_invalid_subject(self) -> None:
        # The inverse regression guard, using the existing no-capable-
        # provider fixture from TestCapabilityNotOfferedByAnyEnabledProvider
        # above: confirms the two message classes stay genuinely distinct,
        # not just that each one individually looks right in isolation.
        shared_clock = FixedClock()
        config = load_market_data_config({})
        (fixture_config,) = tuple(item for item in config.providers if item.enabled)
        budget_manager = build_request_budget_manager((fixture_config,), shared_clock)
        provider = MultiExpirationFixtureProvider(
            fixture_config, ProviderDependencies(object(), shared_clock, budget_manager)
        )
        registry = ProviderRegistry((provider,))
        priorities = tuple(
            ProviderPriority(capability, (provider.provider_id,))
            for capability in provider.capabilities
            if capability is not MarketCapability.EARNINGS_CALENDAR_V1
        )
        capability_registry = CapabilityRegistry(
            registry, ProviderPriorityPolicy("test-v1", priorities)
        )
        fulfillment = CapabilityFulfillmentService(registry, capability_registry, budget_manager)
        try:
            _acquire_or_raise(
                fulfillment,
                SYMBOL,
                MarketCapability.EARNINGS_CALENDAR_V1,
                shared_clock.now(),
                ("earnings_date",),
            )
            raise AssertionError("expected StrategyAdapterError")
        except StrategyAdapterError as error:
            assert "no enabled provider declares or satisfies" in str(error)
            assert "canonical request subject was incomplete or invalid" not in str(error)
