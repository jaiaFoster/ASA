"""SPRINT-013 S13-04A: canonical historical evidence repository port and
prospective accumulation, exercised against an in-memory fake -- the same
role every other strategy_runtime persistence Protocol test plays.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from domain import CanonicalInstrumentIdentity, EvidenceKind, EvidenceReference
from domain.strategy_evidence import HistoricalSkewObservation
from market_data.session_calendar import UsEquitySessionCalendar
from strategy_runtime.historical_evidence import (
    HistoricalSkewRepository,
    SyntheticOrBackdatedObservationError,
    historical_coverage,
    record_prospective_skew_observation,
)

AAPL = CanonicalInstrumentIdentity("figi", "BBG000B9XRY4")
MSFT = CanonicalInstrumentIdentity("figi", "BBG000BPH459")
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "tradier:option-chain:AAPL"),)
CALENDAR = UsEquitySessionCalendar()


@dataclass
class _FixedClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


class InMemoryHistoricalSkewRepository:
    def __init__(self) -> None:
        self._by_instrument: dict[
            CanonicalInstrumentIdentity, dict[datetime, HistoricalSkewObservation]
        ] = {}

    def append(self, observation: HistoricalSkewObservation) -> None:
        bucket = self._by_instrument.setdefault(observation.instrument, {})
        bucket.setdefault(observation.effective_time, observation)

    def history_for(
        self, instrument: CanonicalInstrumentIdentity
    ) -> tuple[HistoricalSkewObservation, ...]:
        bucket = self._by_instrument.get(instrument, {})
        return tuple(sorted(bucket.values(), key=lambda item: item.effective_time))


def _observation(
    instrument: CanonicalInstrumentIdentity,
    effective_time: datetime,
    *,
    call_skew: Decimal = Decimal("0.05"),
    put_skew: Decimal = Decimal("0.07"),
) -> HistoricalSkewObservation:
    return HistoricalSkewObservation(instrument, call_skew, put_skew, effective_time, EVIDENCE)


def _a_session_close() -> datetime:
    # A real, deterministic, already-closed session -- avoids depending on
    # whatever real calendar date this test happens to run on.
    return CALENDAR.session(datetime(2026, 7, 27).date()).closes_at  # Monday


class TestHistoricalSkewRepositoryProtocolContract:
    def test_empty_history_is_an_empty_tuple_not_an_error(self) -> None:
        repository: HistoricalSkewRepository = InMemoryHistoricalSkewRepository()
        assert repository.history_for(AAPL) == ()

    def test_canonical_identity_is_idempotent(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        session = _a_session_close()
        repository.append(_observation(AAPL, session, call_skew=Decimal("0.05")))
        repository.append(_observation(AAPL, session, call_skew=Decimal("0.05")))

        assert len(repository.history_for(AAPL)) == 1

    def test_value_oscillation_does_not_collide_with_an_earlier_observation(self) -> None:
        # A duplicate append for the same (instrument, effective_time) but
        # with DIFFERENT values must not silently overwrite the first --
        # the first truthfully recorded snapshot wins, never a later
        # differently-valued claim for the same already-recorded session.
        repository = InMemoryHistoricalSkewRepository()
        session = _a_session_close()
        repository.append(_observation(AAPL, session, call_skew=Decimal("0.05")))
        repository.append(_observation(AAPL, session, call_skew=Decimal("0.99")))

        (only,) = repository.history_for(AAPL)
        assert only.call_skew == Decimal("0.05")

    def test_different_sessions_remain_distinct(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        first = _a_session_close()
        second = CALENDAR.session(datetime(2026, 7, 28).date()).closes_at
        repository.append(_observation(AAPL, first))
        repository.append(_observation(AAPL, second))

        assert len(repository.history_for(AAPL)) == 2

    def test_different_subjects_never_collide(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        session = _a_session_close()
        repository.append(_observation(AAPL, session))
        repository.append(_observation(MSFT, session))

        assert len(repository.history_for(AAPL)) == 1
        assert len(repository.history_for(MSFT)) == 1

    def test_query_ordering_is_deterministic_oldest_first(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        first = _a_session_close()
        second = CALENDAR.session(datetime(2026, 7, 28).date()).closes_at
        # Appended out of order -- query must still return oldest first.
        repository.append(_observation(AAPL, second))
        repository.append(_observation(AAPL, first))

        ordered = repository.history_for(AAPL)
        assert [item.effective_time for item in ordered] == [first, second]

    def test_utc_normalization(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        session = _a_session_close()
        assert session.tzinfo is not None
        repository.append(_observation(AAPL, session))
        (only,) = repository.history_for(AAPL)
        assert only.effective_time.astimezone(UTC).utcoffset() == timedelta(0)


class TestRecordProspectiveSkewObservation:
    def test_one_qualified_session_creates_one_observation(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        session = _a_session_close()
        clock = _FixedClock(session + timedelta(minutes=5))

        record_prospective_skew_observation(
            repository, clock, CALENDAR, _observation(AAPL, session)
        )

        assert len(repository.history_for(AAPL)) == 1

    def test_duplicate_same_session_snapshot_is_idempotent(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        session = _a_session_close()
        clock = _FixedClock(session + timedelta(minutes=5))

        record_prospective_skew_observation(
            repository, clock, CALENDAR, _observation(AAPL, session)
        )
        record_prospective_skew_observation(
            repository, clock, CALENDAR, _observation(AAPL, session)
        )

        assert len(repository.history_for(AAPL)) == 1

    def test_future_dated_observation_is_rejected(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        session = _a_session_close()
        clock = _FixedClock(session - timedelta(days=1))  # "now" is before the snapshot

        with pytest.raises(SyntheticOrBackdatedObservationError):
            record_prospective_skew_observation(
                repository, clock, CALENDAR, _observation(AAPL, session)
            )
        assert repository.history_for(AAPL) == ()

    def test_backdated_observation_is_rejected(self) -> None:
        repository = InMemoryHistoricalSkewRepository()
        old_session = CALENDAR.session(datetime(2026, 1, 5).date()).closes_at
        now = datetime(2026, 7, 27, 20, 0, tzinfo=UTC)
        clock = _FixedClock(now)

        with pytest.raises(SyntheticOrBackdatedObservationError):
            record_prospective_skew_observation(
                repository, clock, CALENDAR, _observation(AAPL, old_session)
            )
        assert repository.history_for(AAPL) == ()

    def test_current_open_session_snapshot_is_accepted(self) -> None:
        # The most recently completed (prior) session's own opens_at is
        # the floor -- a snapshot from the currently open (not yet
        # closed) session is chronologically after that floor and must
        # still be accepted, not only a fully closed session's snapshot.
        repository = InMemoryHistoricalSkewRepository()
        current_session_open = CALENDAR.session(datetime(2026, 7, 28).date()).opens_at
        now = current_session_open + timedelta(hours=2)
        clock = _FixedClock(now)

        record_prospective_skew_observation(
            repository, clock, CALENDAR, _observation(AAPL, current_session_open)
        )

        assert len(repository.history_for(AAPL)) == 1


class TestHistoricalCoverage:
    def test_empty_history_has_zero_count_and_no_earliest_date(self) -> None:
        assert historical_coverage(()) == (0, None)

    def test_count_and_earliest_reflect_oldest_first_ordering(self) -> None:
        first = _a_session_close()
        second = CALENDAR.session(datetime(2026, 7, 28).date()).closes_at
        observations = (_observation(AAPL, first), _observation(AAPL, second))

        count, earliest = historical_coverage(observations)
        assert count == 2
        assert earliest == first

    def test_40_valid_observations_inside_60_lookback_is_representable(self) -> None:
        # Not a manifest-gate test (that lives at the strategy-policy layer,
        # S13-04D) -- proves the repository/query layer itself has no
        # artificial ceiling that would prevent the Founder-approved
        # 60-observation lookback / 40-valid-minimum policy from ever being
        # satisfiable once real accumulation has run long enough.
        repository = InMemoryHistoricalSkewRepository()
        base = _a_session_close()
        for offset in range(60):
            repository.append(_observation(AAPL, base + timedelta(days=offset)))

        history = repository.history_for(AAPL)
        count, earliest = historical_coverage(history)
        assert count == 60
        assert earliest == base
