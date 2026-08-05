"""SPRINT-013 S13-04B: HistoricalSkewRepository exercised end to end
against a real (test) Postgres instance, through
PostgresHistoricalSkewRepository -- not the in-memory fake
tests/strategy_runtime/test_historical_evidence.py already covers.

Parity tests run the identical assertion against both the in-memory
repository and the real Postgres one, parametrized by a shared fixture,
so a semantic difference between them shows up as a single parametrized
test failing for one backend rather than two independently maintained
(and potentially drifting) test suites.

Migration upgrade/downgrade/re-upgrade round-trip verification is not a
test in this file: product-ci.yml's own backend job already runs
`alembic upgrade head` -> `pytest tests/asa` -> `alembic downgrade base
&& alembic upgrade head` for every PR touching migrations/ -- the exact
round trip this ticket asks for, already exercised structurally for
every migration including 0012, not just this one. "Existing tables and
repositories remain unaffected" is the same guarantee: the full
tests/asa suite (every other Postgres-backed repository's own tests)
runs again after the downgrade-then-reupgrade cycle in that same job.
"""

from __future__ import annotations

import os
import threading
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from asa.integrations.historical_skew_postgres import PostgresHistoricalSkewRepository
from domain import CanonicalInstrumentIdentity, EvidenceKind, EvidenceReference
from domain.strategy_evidence import HistoricalSkewObservation
from market_data.session_calendar import UsEquitySessionCalendar
from strategy_runtime.historical_evidence import ConflictingHistoricalObservationError

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv("ASA_TEST_DATABASE_URL"),
        reason="ASA_TEST_DATABASE_URL not set",
    ),
]

AAPL = CanonicalInstrumentIdentity("figi", "BBG000B9XRY4")
MSFT = CanonicalInstrumentIdentity("figi", "BBG000BPH459")
EVIDENCE = (
    EvidenceReference(EvidenceKind.OBSERVATION, "tradier:option-chain:AAPL", None),
    EvidenceReference(EvidenceKind.CANONICAL_FACT, "asa:normalized-skew:AAPL", 3),
)
CALENDAR = UsEquitySessionCalendar()
_SESSION_1 = CALENDAR.session(date(2026, 7, 27))
_SESSION_2 = CALENDAR.session(date(2026, 7, 28))


class InMemoryHistoricalSkewRepository:
    """Identical semantics to the Postgres repository under test -- see
    tests/strategy_runtime/test_historical_evidence.py's own copy of this
    fake, which this mirrors exactly, so the parity tests below actually
    exercise two independent implementations of the same contract.
    """

    def __init__(self) -> None:
        self._by_instrument: dict[
            CanonicalInstrumentIdentity, dict[date, HistoricalSkewObservation]
        ] = {}

    def append(self, observation: HistoricalSkewObservation, *, session_date: date) -> None:
        bucket = self._by_instrument.setdefault(observation.instrument, {})
        existing = bucket.get(session_date)
        if existing is not None:
            if (existing.call_skew, existing.put_skew) != (
                observation.call_skew,
                observation.put_skew,
            ):
                raise ConflictingHistoricalObservationError(
                    f"{observation.instrument} already has a recorded observation "
                    f"for session {session_date} with different skew values"
                )
            return
        bucket[session_date] = observation

    def history_for(
        self,
        instrument: CanonicalInstrumentIdentity,
        *,
        as_of: datetime | None = None,
        maximum_observations: int | None = None,
    ) -> tuple[HistoricalSkewObservation, ...]:
        bucket = self._by_instrument.get(instrument, {})
        ordered = sorted(bucket.values(), key=lambda item: item.effective_time)
        if as_of is not None:
            ordered = [item for item in ordered if item.effective_time <= as_of]
        if maximum_observations is not None:
            ordered = ordered[-maximum_observations:]
        return tuple(ordered)


@pytest.fixture
def postgres_repository() -> PostgresHistoricalSkewRepository:
    database_url = os.environ["ASA_TEST_DATABASE_URL"]
    os.environ["ASA_DATABASE_URL"] = database_url
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE historical_skew_observations"))
    return PostgresHistoricalSkewRepository(engine)


@pytest.fixture(params=["in_memory", "postgres"])
def repository(
    request: pytest.FixtureRequest,
) -> InMemoryHistoricalSkewRepository | PostgresHistoricalSkewRepository:
    if request.param == "in_memory":
        return InMemoryHistoricalSkewRepository()
    return request.getfixturevalue("postgres_repository")


def _observation(
    instrument: CanonicalInstrumentIdentity,
    effective_time: datetime,
    *,
    call_skew: Decimal = Decimal("0.0512345"),
    put_skew: Decimal = Decimal("0.0798765"),
    evidence: tuple[EvidenceReference, ...] = EVIDENCE,
) -> HistoricalSkewObservation:
    return HistoricalSkewObservation(instrument, call_skew, put_skew, effective_time, evidence)


class TestRepositoryParity:
    """Each test runs once per backend (in_memory, postgres) via the
    ``repository`` fixture's own parametrization.
    """

    def test_empty_history_is_an_empty_tuple(self, repository) -> None:
        assert repository.history_for(AAPL) == ()

    def test_duplicate_same_values_insert_remains_one_row(self, repository) -> None:
        observation = _observation(AAPL, _SESSION_1.closes_at)
        repository.append(observation, session_date=_SESSION_1.trading_date)
        repository.append(observation, session_date=_SESSION_1.trading_date)

        assert len(repository.history_for(AAPL)) == 1

    def test_duplicate_conflicting_values_insert_raises(self, repository) -> None:
        repository.append(
            _observation(AAPL, _SESSION_1.closes_at, call_skew=Decimal("0.05")),
            session_date=_SESSION_1.trading_date,
        )
        with pytest.raises(ConflictingHistoricalObservationError):
            repository.append(
                _observation(AAPL, _SESSION_1.closes_at, call_skew=Decimal("0.99")),
                session_date=_SESSION_1.trading_date,
            )

        (only,) = repository.history_for(AAPL)
        assert only.call_skew == Decimal("0.05")  # untouched by the rejected attempt

    def test_different_sessions_remain_distinct(self, repository) -> None:
        repository.append(
            _observation(AAPL, _SESSION_1.closes_at), session_date=_SESSION_1.trading_date
        )
        repository.append(
            _observation(AAPL, _SESSION_2.closes_at), session_date=_SESSION_2.trading_date
        )

        assert len(repository.history_for(AAPL)) == 2

    def test_different_instruments_never_collide(self, repository) -> None:
        repository.append(
            _observation(AAPL, _SESSION_1.closes_at), session_date=_SESSION_1.trading_date
        )
        repository.append(
            _observation(MSFT, _SESSION_1.closes_at), session_date=_SESSION_1.trading_date
        )

        assert len(repository.history_for(AAPL)) == 1
        assert len(repository.history_for(MSFT)) == 1

    def test_deterministic_oldest_first_ordering(self, repository) -> None:
        # Appended out of order -- query must still return oldest first.
        repository.append(
            _observation(AAPL, _SESSION_2.closes_at), session_date=_SESSION_2.trading_date
        )
        repository.append(
            _observation(AAPL, _SESSION_1.closes_at), session_date=_SESSION_1.trading_date
        )

        ordered = repository.history_for(AAPL)
        assert [item.effective_time for item in ordered] == [
            _SESSION_1.closes_at,
            _SESSION_2.closes_at,
        ]

    def test_as_of_excludes_later_sessions(self, repository) -> None:
        repository.append(
            _observation(AAPL, _SESSION_1.closes_at), session_date=_SESSION_1.trading_date
        )
        repository.append(
            _observation(AAPL, _SESSION_2.closes_at), session_date=_SESSION_2.trading_date
        )

        bounded = repository.history_for(AAPL, as_of=_SESSION_1.closes_at)
        assert [item.effective_time for item in bounded] == [_SESSION_1.closes_at]

    def test_maximum_observations_returns_latest_n_oldest_first(self, repository) -> None:
        repository.append(
            _observation(AAPL, _SESSION_1.closes_at), session_date=_SESSION_1.trading_date
        )
        repository.append(
            _observation(AAPL, _SESSION_2.closes_at), session_date=_SESSION_2.trading_date
        )

        bounded = repository.history_for(AAPL, maximum_observations=1)
        assert [item.effective_time for item in bounded] == [_SESSION_2.closes_at]


class TestPostgresRoundTrip:
    def test_first_insert_round_trips_every_canonical_field(
        self, postgres_repository: PostgresHistoricalSkewRepository
    ) -> None:
        observation = _observation(
            AAPL,
            _SESSION_1.closes_at,
            call_skew=Decimal("0.0512345"),
            put_skew=Decimal("0.0798765"),
        )
        postgres_repository.append(observation, session_date=_SESSION_1.trading_date)

        (only,) = postgres_repository.history_for(AAPL)
        assert only.instrument == AAPL
        assert only.call_skew == Decimal("0.0512345")
        assert only.put_skew == Decimal("0.0798765")
        assert only.effective_time == _SESSION_1.closes_at
        assert only.evidence == EVIDENCE

    def test_evidence_references_round_trip_deterministically(
        self, postgres_repository: PostgresHistoricalSkewRepository
    ) -> None:
        multi_evidence = (
            EvidenceReference(EvidenceKind.OBSERVATION, "tradier:a", None),
            EvidenceReference(EvidenceKind.INDICATOR, "asa:derived:b", 7),
        )
        observation = _observation(AAPL, _SESSION_1.closes_at, evidence=multi_evidence)
        postgres_repository.append(observation, session_date=_SESSION_1.trading_date)

        (only,) = postgres_repository.history_for(AAPL)
        assert only.evidence == multi_evidence

    def test_utc_aware_effective_time_round_trips_exactly(
        self, postgres_repository: PostgresHistoricalSkewRepository
    ) -> None:
        assert _SESSION_1.closes_at.tzinfo is not None
        observation = _observation(AAPL, _SESSION_1.closes_at)
        postgres_repository.append(observation, session_date=_SESSION_1.trading_date)

        (only,) = postgres_repository.history_for(AAPL)
        assert only.effective_time.astimezone(UTC) == _SESSION_1.closes_at.astimezone(UTC)
        assert only.effective_time.utcoffset() is not None

    def test_concurrent_identical_inserts_are_idempotent(
        self, postgres_repository: PostgresHistoricalSkewRepository
    ) -> None:
        observation = _observation(AAPL, _SESSION_1.closes_at)
        barrier = threading.Barrier(2)
        errors: list[Exception] = []

        def _write() -> None:
            barrier.wait(timeout=5)
            try:
                postgres_repository.append(observation, session_date=_SESSION_1.trading_date)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=_write) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert errors == []  # identical concurrent writes never raise
        assert len(postgres_repository.history_for(AAPL)) == 1

    def test_concurrent_conflicting_inserts_do_not_silently_pass(
        self, postgres_repository: PostgresHistoricalSkewRepository
    ) -> None:
        first = _observation(AAPL, _SESSION_1.closes_at, call_skew=Decimal("0.05"))
        second = _observation(AAPL, _SESSION_1.closes_at, call_skew=Decimal("0.99"))
        barrier = threading.Barrier(2)
        errors: list[Exception] = []

        def _write(observation: HistoricalSkewObservation) -> None:
            barrier.wait(timeout=5)
            try:
                postgres_repository.append(observation, session_date=_SESSION_1.trading_date)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [
            threading.Thread(target=_write, args=(first,)),
            threading.Thread(target=_write, args=(second,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        # Exactly one of the two concurrent writers wins the row; the
        # other must observe a genuine content conflict, not silently
        # succeed and not silently do nothing without any signal.
        assert len(errors) == 1
        assert isinstance(errors[0], ConflictingHistoricalObservationError)
        (only,) = postgres_repository.history_for(AAPL)
        assert only.call_skew in (Decimal("0.05"), Decimal("0.99"))
