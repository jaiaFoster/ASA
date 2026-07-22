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

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from domain import (
    AnnouncementTime,
    CanonicalInstrumentIdentity,
    CompletenessMetadata,
    EarningsEvent,
    EvidenceKind,
    EvidenceReference,
    ExpirationCycle,
    FreshnessMetadata,
    FreshnessStatus,
    MarketCapability,
    MarketObservation,
    OHLCVBar,
    OptionChain,
    OptionContract,
    OptionType,
    ProviderProvenance,
    Quote,
    Security,
    SecurityAssetType,
    market_observation_identity,
)
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
from screening.live_adapters import build_live_adapters
from screening.results import ScreeningOutcomeStatus
from screening.runner import run_screening

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
# policy, deliberately without the two ranges overlapping, so each
# strategy's selector has exactly one unambiguous valid pair.
_EXPIRATIONS_DAYS_OUT_AND_IV = (
    (10, Decimal("0.55")),
    (25, Decimal("0.50")),
    (61, Decimal("0.48")),
    (91, Decimal("0.4548992562461861547567860943472296")),
)


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


def _no_transport(_provider_id: str) -> object:
    return object()


def _fulfillment(provider_cls=DeterministicFixtureProvider, clock: FixedClock | None = None):
    # One shared clock instance for both the budget manager and the
    # provider's dependencies: RequestBudgetManager.authorize()'s burst-key
    # is keyed by *its own* clock reading, independent of whatever clock a
    # caller later passes to run_screening() -- sharing one advancing
    # instance here is what actually avoids burst collisions across the
    # several acquisitions one adapter run makes (a quote and a chain, at
    # minimum).
    shared_clock = clock or FixedClock()
    config = load_market_data_config({})
    (fixture_config,) = tuple(item for item in config.providers if item.enabled)
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
        assert result.outcome_status in (ScreeningOutcomeStatus.PASS, ScreeningOutcomeStatus.NO_SIGNAL)
        assert result.subject_identity == f"symbol:{SYMBOL}"


class TestForwardFactorAndEarningsCalendarNeedTwoExpirations:
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
        assert result.outcome_status in (ScreeningOutcomeStatus.PASS, ScreeningOutcomeStatus.NO_SIGNAL)
        assert result.subject_identity == f"symbol:{SYMBOL}"

    def test_earnings_calendar_succeeds_against_the_two_expiration_fixture(self) -> None:
        fulfillment, clock = _fulfillment(MultiExpirationFixtureProvider)
        adapters = build_live_adapters(SYMBOL, fulfillment)
        (result,) = run_screening(
            TARGET_STRATEGY_REGISTRY,
            adapters,
            clock,
            strategy_ids=("earnings_calendar",),
        )
        assert result.outcome_status in (ScreeningOutcomeStatus.PASS, ScreeningOutcomeStatus.NO_SIGNAL)
        assert result.subject_identity == f"symbol:{SYMBOL}"


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
        capability_registry = CapabilityRegistry(registry, ProviderPriorityPolicy("test-v1", priorities))
        fulfillment = CapabilityFulfillmentService(registry, capability_registry, budget_manager)
        adapters = build_live_adapters(SYMBOL, fulfillment)
        (result,) = run_screening(
            TARGET_STRATEGY_REGISTRY, adapters, shared_clock, strategy_ids=("earnings_calendar",)
        )
        assert result.outcome_status is ScreeningOutcomeStatus.MISSING_DATA
        assert result.failure_detail is not None
        assert "no enabled live provider offers" in result.failure_detail


class TestFullLiveRunAcrossAllThreeStrategies:
    def test_all_three_run_and_are_isolated_from_each_other(self) -> None:
        fulfillment, clock = _fulfillment(MultiExpirationFixtureProvider)
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
            if "expirations" in request.required_fields and "contracts" not in request.required_fields:
                return self._expirations_response(request)
            if "contracts" in request.required_fields:
                return self._chain_response_for_one_expiration(request)
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
                FreshnessMetadata(received_at, received_at, request.maximum_age_seconds, 0, FreshnessStatus.FRESH),
                CompletenessMetadata(request.required_fields, request.required_fields, ()),
            )
            for cycle in (
                ExpirationCycle(as_of + timedelta(days=days_out), days_out, False, True, as_of, evidence)
                for days_out, _iv in _EXPIRATIONS_DAYS_OUT_AND_IV
            )
        )
        return ProviderFetchResult(observations, None, (self._attempt(request, reference, received_at),))

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
        security = Security(subject.canonical_instrument, symbol.upper(), SecurityAssetType.EQUITY, "XNAS")
        evidence = (
            EvidenceReference(EvidenceKind.OBSERVATION, f"test:tradier-shaped-chain:{expiration.isoformat()}"),
        )
        contracts = tuple(
            OptionContract(
                CanonicalInstrumentIdentity(
                    "fixture-option", f"{symbol}-{expiration.isoformat()}-{_SPOT + offset}-{kind.value}"
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
            f"test:tradier-shaped:{expiration.isoformat()}", security, received_at, contracts, evidence
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
            FreshnessMetadata(received_at, received_at, request.maximum_age_seconds, 0, FreshnessStatus.FRESH),
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
        assert result.outcome_status in (ScreeningOutcomeStatus.PASS, ScreeningOutcomeStatus.NO_SIGNAL)

    def test_skew_momentum_receives_its_one_required_expiration_chain(self) -> None:
        fulfillment, clock = _fulfillment(TradierShapedMultiExpirationProvider)
        adapters = build_live_adapters(SYMBOL, fulfillment)
        (result,) = run_screening(
            TARGET_STRATEGY_REGISTRY, adapters, clock, strategy_ids=("skew_momentum",)
        )
        assert result.outcome_status in (ScreeningOutcomeStatus.PASS, ScreeningOutcomeStatus.NO_SIGNAL)

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
        run_screening(TARGET_STRATEGY_REGISTRY, adapters, shared_clock, strategy_ids=("forward_factor",))
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
                projection = subject.projection_for(self.provider_id, "expiration", request.effective_end)
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
                    return ProviderFetchResult((), error, (self._attempt(request, reference, received_at),))
                return super()._chain_response_for_one_expiration(request)

        fulfillment, clock = _fulfillment(_BackExpirationFailsProvider)
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
