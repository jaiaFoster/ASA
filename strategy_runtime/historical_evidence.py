"""Durable historical evidence: reusable repository port and prospective
accumulation for canonical historical fact families (SPRINT-013 S13-04,
corrected in S13-04A.1 -- see this module's own docstring sections below
for exactly what changed and why).

Skew Momentum is the first consumer, not the owner -- this module is
generic across every historical fact family domain/strategy_evidence.py
defines. HistoricalSkewRepository is the first concrete port because no
approved provider can supply historical option-skew truthfully (this
ticket's own current-state trace, project/reports/SPRINT-013-S13-04-
trace.md, finding #6), so accumulation must start now, prospectively --
one qualified snapshot per subject per *trading session* -- to ever reach
the Founder-approved 60-observation lookback / 40-valid minimum
(strategies/stonk_manifests.py's own SKEW_MOMENTUM_VERTICAL_MANIFEST
parameters, approved in issue #255).

Pure Protocol, no infrastructure imports -- matching strategy_runtime/
persistence.py's own established convention exactly: a concrete
implementation is dependency-injected by whatever caller constructs one
(asa/integrations owns the concrete Postgres adapter, S13-04B); this
package itself never imports one. Wiring a live adapter to actually call
record_prospective_skew_observation() every scheduled cycle is S13-04D's
own scope, deliberately not done here.

S13-04A.1 correction (Founder review of PR #274, before S13-04B freezes
a schema): the original version keyed repository identity on raw
``effective_time`` and accepted any observation whose effective_time fell
anywhere inside the currently *open* session. That let repeated intraday
scheduled cycles record multiple observations for one trading day and let
an intraday chain masquerade as "the close" -- directly contradicting the
approved policy's own ``observation_frequency:
one_canonical_close_snapshot_per_session`` and this ticket's own
``canonical_end_of_session_skew_snapshot_contract`` requirement. Fixed by:
canonicalizing every recorded observation's ``effective_time`` to its own
trading session's ``closes_at`` (so two attempts for the same session are
byte-identical once canonicalized, not just approximately the same);
keying identity on ``(instrument, trading_session_date)`` instead of raw
timestamp; only ever accepting the most recently *completed* session (an
open, not-yet-closed session is always rejected, not just a future one);
and raising on a genuine content conflict (same session, different skew
values) instead of silently keeping whichever arrived first.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from typing import Protocol

from domain import CanonicalInstrumentIdentity
from domain.strategy_evidence import HistoricalSkewObservation
from market_data.session_calendar import UsEquitySessionCalendar
from strategy_runtime.clock import Clock


class HistoricalSkewRepository(Protocol):
    """Append-only, idempotent by (instrument, trading_session_date) --
    never by raw timestamp, so repeated intraday cycles for the same
    session can never inflate the recorded history (S13-04A.1). A
    duplicate append for a session already recorded with the exact same
    call/put skew values is a no-op; one with *different* values for an
    already-recorded session is a content conflict (see
    ConflictingHistoricalObservationError), never a silent overwrite and
    never a second row.
    """

    def append(self, observation: HistoricalSkewObservation, *, session_date: date) -> None: ...

    def history_for(
        self,
        instrument: CanonicalInstrumentIdentity,
        *,
        as_of: datetime | None = None,
        maximum_observations: int | None = None,
    ) -> tuple[HistoricalSkewObservation, ...]:
        """Deterministically ordered oldest-first; an empty tuple when no
        observation has been recorded yet for this instrument -- never
        raises, matching this instrument simply having no history yet as
        a distinct, valid state, not an error.

        ``as_of``, when supplied, excludes any observation whose
        ``effective_time`` is after it -- "the history as it truthfully
        stood at evaluation time," not "everything ever recorded since,"
        so a caller can reproduce what an earlier evaluation actually saw.
        ``maximum_observations``, when supplied, keeps only the most
        recent that many after the ``as_of`` filter -- the bounded query
        strategy policy's own lookback (e.g. "latest 60 completed
        sessions") needs without requiring an unbounded full-history scan
        for every request (S13-04A.1's own bounded-query correction).
        """
        ...


class SyntheticOrBackdatedObservationError(ValueError):
    """Raised by record_prospective_skew_observation() when an
    observation's effective_time cannot be a genuine, freshly observed
    end-of-session snapshot -- see that function's own docstring for the
    exact rule.
    """


class ConflictingHistoricalObservationError(ValueError):
    """Raised when a trading session already has a recorded skew
    observation whose call_skew or put_skew values differ from a new
    append() attempt for the same (instrument, trading_session_date) --
    S13-04A.1's own correction, replacing the original's silent
    first-write-wins. Canonical financial evidence must never silently
    discard a disagreement; a genuine correction requires a separate,
    explicit, versioned workflow, not an overwrite here.

    Compares only the financial values (call_skew, put_skew), not
    ``evidence`` -- two independently scheduled cycles recording the same
    session's close from the same real market state are expected to carry
    slightly different provenance/evidence references even when they
    agree on the actual numbers; that is not a conflict. ``effective_time``
    is not compared either, since record_prospective_skew_observation()
    always canonicalizes it to the same session close time before this
    check ever runs -- two observations for the same session are already
    guaranteed to share it.
    """


def record_prospective_skew_observation(
    repository: HistoricalSkewRepository,
    clock: Clock,
    calendar: UsEquitySessionCalendar,
    observation: HistoricalSkewObservation,
) -> None:
    """The one entry point through which a skew snapshot may ever be
    recorded (SPRINT-013 S13-04) -- callers must never call
    ``repository.append()`` directly, so the rules here can never be
    bypassed.

    Accepts only a snapshot of the most recently *completed* trading
    session as of ``clock.now()`` -- a currently open (not yet closed)
    session is always rejected (S13-04A.1: "one canonical end-of-session
    snapshot" means the session has actually ended), and so is anything
    future-dated or older than that one completed session. The recorded
    observation's own ``effective_time`` is canonicalized to that
    session's ``closes_at`` before it is ever stored, regardless of the
    exact moment within that session the caller's own snapshot was
    actually captured -- "one canonical end-of-session snapshot" means
    every observation for a given session shares exactly one timestamp,
    not whichever moment a particular scheduled cycle happened to run at.

    Idempotent by construction for an unchanged snapshot: repository.
    append() is a no-op for an (instrument, trading_session_date) pair
    already recorded with the same values, so calling this once per
    scheduled cycle for the same trading session is always safe, however
    many times a cycle actually runs after that session has closed.
    """
    now = clock.now()
    if observation.effective_time > now:
        raise SyntheticOrBackdatedObservationError(
            "historical skew observation effective_time is in the future"
        )
    completed = calendar.latest_completed_session(now)
    if not completed.opens_at <= observation.effective_time <= completed.closes_at:
        raise SyntheticOrBackdatedObservationError(
            "historical skew observation effective_time does not fall within "
            "the most recently completed trading session -- prospective "
            "accumulation only ever records that one session's own "
            "end-of-session snapshot, never an open session's intraday "
            "chain and never a backdated one"
        )
    canonical = replace(observation, effective_time=completed.closes_at)
    repository.append(canonical, session_date=completed.trading_date)


def historical_coverage(
    observations: tuple[HistoricalSkewObservation, ...],
) -> tuple[int, datetime | None]:
    """(count, earliest effective_time) for a queried history -- the
    exact pair the Skew History section's own requirement 3 ("expose
    available count and earliest qualifying date") needs, derived purely
    from what history_for() already returns rather than a third
    repository method to keep in sync with the other two.
    """
    if not observations:
        return 0, None
    return len(observations), observations[0].effective_time
