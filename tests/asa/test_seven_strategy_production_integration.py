"""SP-07A anti-shelving proof for all seven research-selected strategies."""

import json
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest

from asa.scheduled_screening import (
    FIXED_SUBJECT_OPTION_UNIVERSE,
    PRODUCTION_SCREENING_UNIVERSE,
    SP500_COHORT_STRATEGY_IDS,
    run_scheduled_complete_family_refresh,
)
from market_data.attempts import InMemoryAcquisitionAttemptRepository
from screening.universe_membership import SP500_MEMBERSHIP
from strategy_runtime.adapters import (
    build_migrated_cutover_policy,
    build_migrated_shadow_registry,
    build_migrated_signal_catalog,
    build_migrated_strategy_registry,
)
from tests.asa.fakes import InMemoryLatestResultRepository, InMemoryObservationHistoryRepository

SELECTED = frozenset(
    {
        "event_vol_gxz_preea_straddle_to_expiry",
        "index_putwrite_cboe_put",
        "index_putwrite_cboe_puty",
        "index_short_vol_scs_near_atm_straddle",
        "xs_option_zhan_neg_lnprice_dn_call",
        "xs_option_heston_straddle_momentum_lowcost",
        "index_buywrite_cboe_bxm",
    }
)


def test_all_seven_are_registered_cataloged_bound_and_cut_over() -> None:
    now = datetime(2026, 10, 16, 21, tzinfo=UTC)
    registry = build_migrated_strategy_registry()
    shadows = build_migrated_shadow_registry(now)
    catalog = build_migrated_signal_catalog()
    policy = build_migrated_cutover_policy({})
    assert set(registry.strategy_ids()) >= SELECTED
    assert set(shadows.strategy_ids()) >= SELECTED
    assert {item.signal_id for item in catalog} >= SELECTED
    assert all(policy.is_cut_over(strategy_id) for strategy_id in SELECTED)


def test_all_seven_have_normal_scheduled_production_paths() -> None:
    cohort_ids = {strategy_id for strategy_id, _symbol in PRODUCTION_SCREENING_UNIVERSE}
    fixed_pairs = set(FIXED_SUBJECT_OPTION_UNIVERSE)
    assert "event_vol_gxz_preea_straddle_to_expiry" in cohort_ids
    assert {
        ("index_putwrite_cboe_put", "SPX"),
        ("index_putwrite_cboe_puty", "SPX"),
        ("index_short_vol_scs_near_atm_straddle", "SPX"),
        ("index_buywrite_cboe_bxm", "SPX"),
    } <= fixed_pairs


class _ClaimOnce:
    def __init__(self) -> None:
        self.claimed: list[str] = []

    def claim(self, slot_id: str, claimed_at: datetime) -> bool:
        del claimed_at
        if slot_id in self.claimed:
            return False
        self.claimed.append(slot_id)
        return True


def _no_transport(provider_id: str) -> object:
    raise AssertionError(f"capacity deferral must not build transport for {provider_id}")


ZHAN = "xs_option_zhan_neg_lnprice_dn_call"
HESTON = "xs_option_heston_straddle_momentum_lowcost"


def test_complete_family_deferral_is_persisted_typed_and_provider_free() -> None:
    repository = InMemoryLatestResultRepository()
    claims = _ClaimOnce()
    run_at = datetime(2026, 9, 30, 21, tzinfo=UTC)  # last session of September, after close
    deferred = run_scheduled_complete_family_refresh(
        repository=repository,
        claim_repository=claims,
        transport_factory=_no_transport,
        now=run_at,
    )
    members = SP500_MEMBERSHIP.symbols
    assert len(deferred) == len(members)
    assert {item.signal_id for item in deferred} == {ZHAN}
    assert {item.reason for item in deferred} == {"CAPACITY_DEFERRED_INCOMPLETE_COHORT"}
    assert {item.outcome for item in deferred} == {"missing_data"}
    assert all(item.request_count == 0 and item.error is None for item in deferred)
    rows = repository.get_for_signal(ZHAN)
    assert {row.symbol for row in rows} == set(members)
    assert all(row.evaluation_state == "missing_data" for row in rows)
    assert all(
        row.blockers == ("typed unknown evidence gap: CAPACITY_DEFERRED_INCOMPLETE_COHORT",)
        for row in rows
    )
    assert all(row.opportunity_id is None for row in rows)  # nothing ranked or entered
    # A repeated after-close tick on the same formation date is claimed once.
    again = run_scheduled_complete_family_refresh(
        repository=repository,
        claim_repository=claims,
        transport_factory=_no_transport,
        now=run_at.replace(minute=10),
    )
    assert again == ()
    assert claims.claimed == ["complete-family:zhan_delta_neutral_call_v1:2026-09-30"]


def _cron_ticks(day: date) -> tuple[datetime, ...]:
    config = json.loads(Path("railway.cron.json").read_text())
    minute, hour, _dom, _month, weekdays = config["deploy"]["cronSchedule"].split()
    assert minute == "*/10" and weekdays == "1-5"
    first, last = (int(item) for item in hour.split("-"))
    return tuple(
        datetime.combine(day, time(h, m), tzinfo=UTC)
        for h in range(first, last + 1)
        for m in range(0, 60, 10)
    )


@pytest.mark.parametrize(
    ("day", "strategy_id"),
    [
        (date(2026, 10, 30), ZHAN),  # EDT last session of month
        (date(2026, 11, 30), ZHAN),  # EST last session of month
        (date(2026, 12, 31), ZHAN),  # EST year end
        (date(2026, 10, 16), HESTON),  # EDT monthly expiration
        (date(2026, 11, 20), HESTON),  # EST monthly expiration
        (date(2026, 6, 18), HESTON),  # Juneteenth-adjusted monthly expiration
    ],
)
def test_configured_cron_reaches_every_formation_boundary(day: date, strategy_id: str) -> None:
    due_ticks = []
    for tick in _cron_ticks(day):
        binding = build_migrated_shadow_registry(tick).binding_for(strategy_id)
        assert binding.cross_subject_family_due is not None
        if binding.cross_subject_family_due(tick):
            due_ticks.append(tick)
    assert due_ticks, f"no configured cron tick after the {day} close"


def test_complete_family_admission_is_atomic_and_full_universe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asa.scheduled_screening as scheduled

    captured: list[tuple[tuple[str, str], ...]] = []

    def _capture(universe: tuple[tuple[str, str], ...], **_kwargs: object) -> tuple[object, ...]:
        captured.append(universe)
        return ()

    monkeypatch.setattr(scheduled, "run_scheduled_refresh", _capture)
    scheduled.run_scheduled_complete_family_refresh(
        now=datetime(2026, 9, 30, 21, tzinfo=UTC),
        maximum_subjects=10_000,
        claim_repository=_ClaimOnce(),
    )
    assert len(captured) == 1
    assert len(captured[0]) == len(scheduled.SP500_MEMBERSHIP.symbols)
    assert {strategy_id for strategy_id, _symbol in captured[0]} == {
        "xs_option_zhan_neg_lnprice_dn_call"
    }
    assert tuple(symbol for _strategy_id, symbol in captured[0]) == (
        scheduled.SP500_MEMBERSHIP.symbols
    )


def test_seven_strategy_matrix_has_exactly_one_production_path_each() -> None:
    now = datetime(2026, 10, 16, 21, tzinfo=UTC)
    shadows = build_migrated_shadow_registry(now)
    cohort = set(SP500_COHORT_STRATEGY_IDS)
    fixed = {strategy_id for strategy_id, _symbol in FIXED_SUBJECT_OPTION_UNIVERSE}
    complete = {
        strategy_id
        for strategy_id in shadows.strategy_ids()
        if shadows.binding_for(strategy_id).requires_complete_cross_subject_universe
    }
    for strategy_id in SELECTED:
        paths = [strategy_id in cohort, strategy_id in fixed, strategy_id in complete]
        assert sum(paths) == 1, (strategy_id, paths)
    assert complete == {ZHAN, HESTON}
    # Complete families are never routed through the rotating 30-name cohort.
    assert not complete & cohort


def test_typed_family_deferral_replays_to_identical_rows() -> None:
    run_at = datetime(2026, 10, 16, 21, tzinfo=UTC)  # Heston formation date
    first, second = InMemoryLatestResultRepository(), InMemoryLatestResultRepository()
    for repository in (first, second):
        run_scheduled_complete_family_refresh(
            repository=repository,
            claim_repository=_ClaimOnce(),
            transport_factory=_no_transport,
            now=run_at,
        )
    assert {row.signal_id for row in first.get_all()} == {HESTON}
    assert first.get_all() == second.get_all()


def _projection(repository: InMemoryLatestResultRepository) -> set[tuple[object, ...]]:
    # Run identity (wall-clock cycle id, demand ids) is excluded; the typed
    # decision is not.
    return {
        (
            row.signal_id,
            row.symbol,
            row.evaluation_state,
            row.verdict,
            tuple(blocker.split(" (")[0] for blocker in row.blockers),
            row.metrics.get("decision.reason"),
        )
        for row in repository.get_all()
    }


def test_seven_strategy_composition_root_replay_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    """All seven, through the real scheduled root with fixture transport, twice.

    The cohort strategy runs through the scheduled per-subject root and the
    complete families through their typed deferral path; each produces a
    persisted typed row, no pair raises, and the replay is identical apart
    from run identity. The fixture transport models equity subjects only, so
    the fixed-SPX strategies (PUT, PUTY, BXM, SCS) are replay-proven by their
    own provider-free strategy suites rather than here.
    """
    import asa.scheduled_screening as scheduled
    from tests.asa._fixture_market_data_access import build_fixture_market_data_access_factory

    monkeypatch.setattr(
        scheduled, "build_shared_market_data_access", build_fixture_market_data_access_factory()
    )
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    universe = (("event_vol_gxz_preea_straddle_to_expiry", "AAPL"),)
    run_at = datetime(2026, 10, 16, 21, tzinfo=UTC)  # Heston formation date

    def _cycle() -> InMemoryLatestResultRepository:
        repository = InMemoryLatestResultRepository()
        outcomes = scheduled.run_scheduled_refresh(
            universe,
            repository=repository,
            history_repository=InMemoryObservationHistoryRepository(),
            acquisition_attempt_repository=InMemoryAcquisitionAttemptRepository(),
            now=run_at,
        )
        outcomes += run_scheduled_complete_family_refresh(
            repository=repository,
            claim_repository=_ClaimOnce(),
            transport_factory=_no_transport,
            now=run_at,
        )
        assert all(item.error is None for item in outcomes)
        return repository

    first, second = _cycle(), _cycle()
    assert {row.signal_id for row in first.get_all()} == {
        "event_vol_gxz_preea_straddle_to_expiry",
        HESTON,  # Zhan is not due on a monthly-expiration date
    }
    assert all(row.evaluation_state for row in first.get_all())
    assert _projection(first) == _projection(second)


def test_fixed_spx_subject_prepares_all_four_index_strategies_together(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Production regression (SP-08A real session, 2026-10-02).

    BXM and SCS declare distinct INDEX_SETTLEMENT_VALUE_V1 lookbacks on the
    shared SPX subject. Without a registered reducer the seal raised, so the
    whole SPX subject failed preparation and PUT, PUTY, BXM and SCS all
    persisted ``subject_preparation_failed``. With every provider unreachable
    each strategy must instead persist its own typed evidence reason.
    """
    import logging

    import asa.scheduled_screening as scheduled
    from market_data.transport import ReadOnlyTransportError

    class _Down:
        def get(self, request: object) -> object:
            raise ReadOnlyTransportError("provider unreachable")

    caplog.set_level(logging.WARNING)
    os_env = {"ASA_TRADIER_ENABLED": "true", "ASA_TRADIER_ACCESS_TOKEN": "fixture-token"}
    with pytest.MonkeyPatch.context() as patch:
        for key, value in os_env.items():
            patch.setenv(key, value)
        patch.setenv("ASA_US_TREASURY_ENABLED", "true")
        repository = InMemoryLatestResultRepository()
        pairs = tuple(pair for pair in FIXED_SUBJECT_OPTION_UNIVERSE if pair[1] == "SPX")
        outcomes = scheduled.run_scheduled_refresh(
            pairs,
            repository=repository,
            history_repository=InMemoryObservationHistoryRepository(),
            acquisition_attempt_repository=InMemoryAcquisitionAttemptRepository(),
            transport_factory=lambda _provider: _Down(),
        )
    assert {item.signal_id for item in outcomes} == {pair[0] for pair in pairs}
    assert all(item.error is None for item in outcomes)
    assert not any(
        record.message == "shadow_subject_preparation_failed" for record in caplog.records
    )
    rows = repository.get_all()
    assert {row.signal_id for row in rows} == {pair[0] for pair in pairs}
    for row in rows:
        assert row.evaluation_state == "missing_data"
        assert row.blockers and all("subject_preparation_failed" not in b for b in row.blockers)
