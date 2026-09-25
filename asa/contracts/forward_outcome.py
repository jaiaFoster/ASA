"""Immutable forward-outcome observation of one tracked proposal (OI-02/OI-04)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from strategy_runtime.forward_outcome import OutcomeStatus


@dataclass(frozen=True, slots=True)
class ForwardOutcomeObservation:
    """One (subject, horizon) outcome; never rewritten.

    ``subject_id`` is the tracked candidate id for a ``user_tracked`` subject
    or the enrollment id for a ``system_actionable`` one. The two live in
    structurally separate ledgers (ND-01).

    ``modeled_mark`` / ``modeled_pnl`` are midpoint or terminal-intrinsic
    models against the frozen modeled entry -- never an executed fill.
    """

    subject_id: UUID
    horizon_id: str
    status: OutcomeStatus
    due_at: datetime
    collected_at: datetime
    horizon_policy_version: str
    frozen_proposal_identity: str | None
    observed_at: datetime | None
    underlying_price: Decimal | None
    modeled_mark: Decimal | None
    modeled_pnl: Decimal | None
    mark_basis: str | None
    mark_model_version: str | None
    unknown_reasons: tuple[str, ...]
    provenance: tuple[str, ...]
    content_identity: str

    def __post_init__(self) -> None:
        if (self.status is OutcomeStatus.OBSERVED) != (self.observed_at is not None):
            raise ValueError("only an observed outcome carries evidence time")
        if self.status is not OutcomeStatus.OBSERVED and (
            self.modeled_mark is not None or self.underlying_price is not None
        ):
            raise ValueError("missed/unobservable outcomes carry no values")
        if (self.modeled_mark is None) != (self.modeled_pnl is None):
            raise ValueError("modeled mark and P&L are present together or absent together")
