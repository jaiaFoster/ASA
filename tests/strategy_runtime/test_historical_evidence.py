"""SPRINT-013 S13-04A (corrected in S13-04A.1): canonical historical
evidence repository port and prospective accumulation, exercised against
an in-memory fake -- the same role every other strategy_runtime
persistence Protocol test plays.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from domain import CanonicalInstrumentIdentity, EvidenceKind, EvidenceReference
from domain.strategy_evidence import HistoricalSkewObservation
from market_data.session_calendar import MarketSession, UsEquitySessionCalendar
from strategy_runtime.historical_evidence import (
    ConflictingHistoricalObservationError,
    HistoricalSkewRepository,
    SyntheticOrBackdatedObservationError,
    historical_coverage,
    record_prospective_skew_observation,
)

AAPL = CanonicalInstrumentIdentity("figi", "BBG000B9XRY4")
MSFT = CanonicalInstrumentIdentity("figi", "BBG000BPH459")
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "tradier:option-chain:AAPL"),)
CALENDAR = UsEquitySessionCalendar()

# Two real, deterministic, already-closed Monday/Tuesday sessions -- avoids
# depending on whatever real calendar date these tests happen to run on.
_SESSION_1 = CALENDAR.session(date(2026, 7, 27))
_SESSION_2 = CALENDAR.session(date(2026, 7, 28))


@dataclass
class _FixedClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


class InMemoryHistoricalSkewRepository:
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


def _observation(
    instrument: CanonicalInstrumentIdentity,
    effective_time: datetime,
    *,
    call_skew: Decimal = Decimal("0.05"),
    put_skew: Decimal = Decimal("0.07"),
) -> HistoricalSkewObservation:
    return HistoricalSkewObservation(instrument, call_skew, put_skew, effective_time, EVIDENCE)


def _append_directly(
    repository: InMemoryHistoricalSkewRepository,
    instrument: CanonicalInstrumentIdentity,
    session: MarketSession,
    *,
    call_skew: Decimal = Decimal("0.05"),
    put_skew: Decimal = Decimal("0.07"),
) -> None:
    observation = _observation(
        instrument, session.closes_at, call_skew=call_skew, put_skew=put_skew
    )
    repository.append(observation, session_date=session.trading_date)


class TestHistoricalSkewRepositoryProtocolContract:
    def test_empty_history_is_an_empty_tuple_not_an_error(self) -> None:
        repository: HistoricalSkewRepository = InMemoryHistoricalSkewRepository()
        assert repository.history_for(AAPL) == ()

    def test_canonical_identity_is_idempotent(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        _append_directly(repository, AAPL, _SESSION_1, call_skew=Decimal("0.05"))
        _append_directly(repository, AAPL, _SESSION_1, call_skew=Decimal("0.05"))

        assert len(repository.history_for(AAPL)) == 1

    def test_conflicting_content_for_an_already_recorded_session_is_rejected(self) -> None:
        # A second append for the same session with DIFFERENT skew values
        # must raise, never silently overwrite or silently keep the first
        # (S13-04A.1's own correction of the original silent-first-write
        # behavior a Founder review flagged before S13-04B's migration).
        repository = InMemoryHistoricalSkewRepository()
        _append_directly(repository, AAPL, _SESSION_1, call_skew=Decimal("0.05"))

        with pytest.raises(ConflictingHistoricalObservationError):
            _append_directly(repository, AAPL, _SESSION_1, call_skew=Decimal("0.99"))

        (only,) = repository.history_for(AAPL)
        assert only.call_skew == Decimal("0.05")  # untouched by the rejected attempt

    def test_different_sessions_remain_distinct(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        _append_directly(repository, AAPL, _SESSION_1)
        _append_directly(repository, AAPL, _SESSION_2)

        assert len(repository.history_for(AAPL)) == 2

    def test_different_subjects_never_collide(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        _append_directly(repository, AAPL, _SESSION_1)
        _append_directly(repository, MSFT, _SESSION_1)

        assert len(repository.history_for(AAPL)) == 1
        assert len(repository.history_for(MSFT)) == 1

    def test_query_ordering_is_deterministic_oldest_first(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        # Appended out of order -- query must still return oldest first.
        _append_directly(repository, AAPL, _SESSION_2)
        _append_directly(repository, AAPL, _SESSION_1)

        ordered = repository.history_for(AAPL)
        assert [item.effective_time for item in ordered] == [
            _SESSION_1.closes_at,
            _SESSION_2.closes_at,
        ]

    def test_utc_normalization(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        assert _SESSION_1.closes_at.tzinfo is not None
        _append_directly(repository, AAPL, _SESSION_1)
        (only,) = repository.history_for(AAPL)
        assert only.effective_time.astimezone(UTC).utcoffset() == timedelta(0)

    def test_as_of_excludes_observations_after_the_given_time(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        _append_directly(repository, AAPL, _SESSION_1)
        _append_directly(repository, AAPL, _SESSION_2)

        bounded = repository.history_for(AAPL, as_of=_SESSION_1.closes_at)
        assert [item.effective_time for item in bounded] == [_SESSION_1.closes_at]

    def test_maximum_observations_keeps_only_the_most_recent(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        _append_directly(repository, AAPL, _SESSION_1)
        _append_directly(repository, AAPL, _SESSION_2)

        bounded = repository.history_for(AAPL, maximum_observations=1)
        assert [item.effective_time for item in bounded] == [_SESSION_2.closes_at]


class TestRecordProspectiveSkewObservation:
    def test_one_qualified_session_creates_one_observation(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        clock = _FixedClock(_SESSION_2.opens_at + timedelta(hours=1))  # session 1 now completed

        record_prospective_skew_observation(
            repository, clock, CALENDAR, _observation(AAPL, _SESSION_1.closes_at)
        )

        assert len(repository.history_for(AAPL)) == 1

    def test_effective_time_is_canonicalized_to_the_session_close(self) -> None:
        # A snapshot captured mid-session (e.g. one minute after open) is
        # still recorded against that session's own official close time,
        # not the moment it happened to be captured -- "one canonical
        # end-of-session snapshot" means every observation for a session
        # shares exactly one timestamp.
        repository = InMemoryHistoricalSkewRepository()
        clock = _FixedClock(_SESSION_2.opens_at + timedelta(hours=1))
        captured_mid_session = _SESSION_1.opens_at + timedelta(minutes=1)

        record_prospective_skew_observation(
            repository, clock, CALENDAR, _observation(AAPL, captured_mid_session)
        )

        (only,) = repository.history_for(AAPL)
        assert only.effective_time == _SESSION_1.closes_at

    def test_duplicate_same_session_snapshot_is_idempotent(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        clock = _FixedClock(_SESSION_2.opens_at + timedelta(hours=1))

        record_prospective_skew_observation(
            repository, clock, CALENDAR, _observation(AAPL, _SESSION_1.closes_at)
        )
        record_prospective_skew_observation(
            repository, clock, CALENDAR, _observation(AAPL, _SESSION_1.closes_at)
        )

        assert len(repository.history_for(AAPL)) == 1

    def test_repeated_intraday_cycles_cannot_inflate_one_sessions_count(self) -> None:
        # The exact regression this correction exists to prevent: several
        # scheduled cycles, each capturing its own live chain at a
        # different moment, must still collapse to exactly one recorded
        # observation for the one session they all actually belong to.
        repository = InMemoryHistoricalSkewRepository()
        clock = _FixedClock(_SESSION_2.opens_at + timedelta(hours=1))

        for minute in (5, 65, 125, 185):
            record_prospective_skew_observation(
                repository,
                clock,
                CALENDAR,
                _observation(AAPL, _SESSION_1.opens_at + timedelta(minutes=minute)),
            )

        assert len(repository.history_for(AAPL)) == 1

    def test_future_dated_observation_is_rejected(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        clock = _FixedClock(_SESSION_1.closes_at - timedelta(days=1))

        with pytest.raises(SyntheticOrBackdatedObservationError):
            record_prospective_skew_observation(
                repository, clock, CALENDAR, _observation(AAPL, _SESSION_1.closes_at)
            )
        assert repository.history_for(AAPL) == ()

    def test_backdated_observation_is_rejected(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        old_session = CALENDAR.session(date(2026, 1, 5))
        clock = _FixedClock(_SESSION_2.opens_at + timedelta(hours=1))

        with pytest.raises(SyntheticOrBackdatedObservationError):
            record_prospective_skew_observation(
                repository, clock, CALENDAR, _observation(AAPL, old_session.closes_at)
            )
        assert repository.history_for(AAPL) == ()

    def test_current_open_session_snapshot_is_rejected(self) -> None:
        # S13-04A.1's own correction: a snapshot from the session that is
        # currently open (not yet closed) as of "now" must be rejected,
        # not accepted -- only the most recently *completed* session's
        # own close may ever be recorded.
        repository = InMemoryHistoricalSkewRepository()
        now = _SESSION_2.opens_at + timedelta(hours=1)  # session 2 is still open at "now"
        clock = _FixedClock(now)

        with pytest.raises(SyntheticOrBackdatedObservationError):
            record_prospective_skew_observation(
                repository,
                clock,
                CALENDAR,
                _observation(AAPL, _SESSION_2.opens_at + timedelta(minutes=30)),
            )
        assert repository.history_for(AAPL) == ()


class TestHistoricalCoverage:
    def test_empty_history_has_zero_count_and_no_earliest_date(self) -> None:
        assert historical_coverage(()) == (0, None)

    def test_count_and_earliest_reflect_oldest_first_ordering(self) -> None:
        observations = (
            _observation(AAPL, _SESSION_1.closes_at),
            _observation(AAPL, _SESSION_2.closes_at),
        )

        count, earliest = historical_coverage(observations)
        assert count == 2
        assert earliest == _SESSION_1.closes_at

    def test_40_valid_observations_inside_60_lookback_is_representable(self) -> None:
        # Not a manifest-gate test (that lives at the strategy-policy layer,
        # S13-04D) -- proves the repository/query layer itself has no
        # artificial ceiling that would prevent the Founder-approved
        # 60-observation lookback / 40-valid-minimum policy from ever being
        # satisfiable once real accumulation has run long enough.
        repository = InMemoryHistoricalSkewRepository()
        cursor = date(2026, 1, 5)
        recorded_closes: list[datetime] = []
        while len(recorded_closes) < 60:
            session = CALENDAR.session(cursor)
            if session is not None:
                _append_directly(repository, AAPL, session)
                recorded_closes.append(session.closes_at)
            cursor += timedelta(days=1)

        history = repository.history_for(AAPL)
        count, earliest = historical_coverage(history)
        assert count == 60
        assert earliest == recorded_closes[0]
