"""Durable historical evidence: reusable repository port and prospective
accumulation for canonical historical fact families (SPRINT-013 S13-04).

Skew Momentum is the first consumer, not the owner -- this module is
generic across every historical fact family domain/strategy_evidence.py
defines. HistoricalSkewRepository is the first concrete port because no
approved provider can supply historical option-skew truthfully (this
ticket's own current-state trace, project/reports/SPRINT-013-S13-04-
trace.md, finding #6), so accumulation must start now, prospectively --
one qualified snapshot per subject per session -- to ever reach the
Founder-approved 60-observation lookback / 40-valid minimum
(strategies/stonk_manifests.py's own SKEW_MOMENTUM_VERTICAL_MANIFEST
parameters, approved in issue #255).

Pure Protocol, no infrastructure imports -- matching strategy_runtime/
persistence.py's own established convention exactly: a concrete
implementation is dependency-injected by whatever caller constructs one
(asa/integrations owns the concrete Postgres adapter, S13-04B); this
package itself never imports one. Wiring a live adapter to actually call
record_prospective_skew_observation() every scheduled cycle is S13-04D's
own scope, deliberately not done here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from domain import CanonicalInstrumentIdentity
from domain.strategy_evidence import HistoricalSkewObservation
from market_data.session_calendar import UsEquitySessionCalendar
from strategy_runtime.clock import Clock


class HistoricalSkewRepository(Protocol):
    """Append-only, idempotent by (instrument, effective_time): a
    duplicate snapshot for a session already recorded is a no-op, never a
    second row and never an overwrite -- once truthfully recorded, a
    session's own snapshot does not change retroactively, regardless of
    what a later, differently-valued append() call for the same session
    might claim. This is the "no value-only identity that collides when
    values oscillate" requirement, satisfied by construction: the
    identity key is (instrument, effective_time) alone, values are never
    part of it.
    """

    def append(self, observation: HistoricalSkewObservation) -> None: ...

    def history_for(
        self, instrument: CanonicalInstrumentIdentity
    ) -> tuple[HistoricalSkewObservation, ...]:
        """Deterministically ordered oldest-first; an empty tuple when no
        observation has been recorded yet for this instrument -- never
        raises, matching this instrument simply having no history yet as
        a distinct, valid state, not an error.
        """
        ...


class SyntheticOrBackdatedObservationError(ValueError):
    """Raised by record_prospective_skew_observation() when an
    observation's effective_time cannot be a genuine, freshly observed
    snapshot -- see that function's own docstring for the exact rule.
    """


def record_prospective_skew_observation(
    repository: HistoricalSkewRepository,
    clock: Clock,
    calendar: UsEquitySessionCalendar,
    observation: HistoricalSkewObservation,
) -> None:
    """The one entry point through which a skew snapshot may ever be
    recorded (SPRINT-013 S13-04) -- callers must never call
    ``repository.append()`` directly, so this rule can never be bypassed.

    Rejects anything that cannot be a genuine, freshly observed snapshot:
    a future-dated ``effective_time``, or one older than the most
    recently completed trading session as of ``clock.now()``. This is
    what "no synthetic or repeated current-chain backfill" (this
    ticket's own hard rule) actually enforces in code, not only in
    review -- a caller cannot construct an observation dated months ago
    and have it silently accepted as real history.

    Idempotent by construction: ``repository.append()`` itself is a
    no-op for an (instrument, effective_time) pair already recorded, so
    calling this once per scheduled cycle for the same trading session
    is always safe, however many times a cycle actually runs that
    session.
    """
    now = clock.now()
    if observation.effective_time > now:
        raise SyntheticOrBackdatedObservationError(
            "historical skew observation effective_time is in the future"
        )
    earliest_acceptable = calendar.latest_completed_session(now).opens_at
    if observation.effective_time < earliest_acceptable:
        raise SyntheticOrBackdatedObservationError(
            "historical skew observation effective_time predates the most "
            "recently completed trading session -- prospective accumulation "
            "only ever records the current session's own snapshot, never a "
            "backdated one"
        )
    repository.append(observation)


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
