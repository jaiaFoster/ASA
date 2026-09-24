"""Ports for forward-outcome collection (OUTCOME-INTELLIGENCE OI-03/OI-04)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from asa.contracts.forward_outcome import ForwardOutcomeObservation
from strategy_runtime.forward_outcome import LegQuote


class ForwardOutcomeConflictError(RuntimeError):
    """A different outcome for an already-recorded (candidate, horizon)."""


class ForwardOutcomeRepository(Protocol):
    def append(self, observation: ForwardOutcomeObservation) -> ForwardOutcomeObservation:
        """Append-only; identical content is idempotent, a different one raises."""

    def for_candidate(self, candidate_id: UUID) -> tuple[ForwardOutcomeObservation, ...]: ...


@dataclass(frozen=True, slots=True)
class OutcomeEvidence:
    """Provider-neutral evidence for one subject at one collection tick."""

    underlying_price: Decimal | None
    underlying_observed_at: datetime | None
    leg_quotes: dict[str, LegQuote]
    chain_observed_at: datetime | None
    provenance: tuple[str, ...]
    unknown_reasons: tuple[str, ...] = ()


class OutcomeEvidenceSource(Protocol):
    def collect(
        self, symbol: str, expirations: tuple[date, ...], now: datetime
    ) -> OutcomeEvidence: ...
