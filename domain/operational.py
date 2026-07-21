"""Provider-neutral contracts between intelligence and operations (ASA-ARCH-001).

Structural definitions only.  These values contain no portfolio policy,
execution planning, persistence, provider, or broker behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from domain.references import Confidence, EvidenceReference
from domain.values import (
    DomainInvariantError,
    require_finite_decimal,
    require_tz_aware,
    require_unit_interval,
)


def _require_text(value: str, owner: str, field_name: str) -> None:
    if not value or value != value.strip():
        raise DomainInvariantError(f"{owner}.{field_name} must be non-empty normalized text")


def _require_non_negative(value: Decimal, owner: str, field_name: str) -> None:
    require_finite_decimal(value, owner, field_name)
    if value < 0:
        raise DomainInvariantError(f"{owner}.{field_name} cannot be negative")


class InstrumentKind(str, Enum):
    """Instrument categories understood by the provider-neutral domain."""

    EQUITY = "equity"
    OPTION = "option"
    CASH = "cash"


class PositionDirection(str, Enum):
    """Explicit exposure direction; quantity values never encode direction."""

    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True, slots=True)
class CanonicalInstrumentIdentity:
    """Opaque, namespaced identity assigned before entering the domain.

    Consumers compare the complete ``(scheme, value)`` pair.  They must not
    parse either string to recover symbol, expiry, strike, or provider IDs.
    """

    scheme: str
    value: str

    def __post_init__(self) -> None:
        _require_text(self.scheme, "CanonicalInstrumentIdentity", "scheme")
        _require_text(self.value, "CanonicalInstrumentIdentity", "value")


@dataclass(frozen=True, slots=True)
class SectorClassification:
    """A pinned sector code in an explicitly named taxonomy."""

    taxonomy: str
    taxonomy_version: str
    code: str

    def __post_init__(self) -> None:
        for field_name in ("taxonomy", "taxonomy_version", "code"):
            _require_text(getattr(self, field_name), "SectorClassification", field_name)


@dataclass(frozen=True, slots=True)
class MonetaryAmount:
    """A finite decimal amount with an explicit ISO-style currency code."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        require_finite_decimal(self.amount, "MonetaryAmount", "amount")
        _require_text(self.currency, "MonetaryAmount", "currency")


@dataclass(frozen=True, slots=True)
class Instrument:
    """Canonical instrument description, independent of every broker model."""

    identity: CanonicalInstrumentIdentity
    kind: InstrumentKind
    display_symbol: str
    currency: str
    sector: SectorClassification | None = None
    underlying_identity: CanonicalInstrumentIdentity | None = None

    def __post_init__(self) -> None:
        _require_text(self.display_symbol, "Instrument", "display_symbol")
        _require_text(self.currency, "Instrument", "currency")
        if self.kind is InstrumentKind.OPTION and self.underlying_identity is None:
            raise DomainInvariantError("Instrument.underlying_identity is required for options")
        if self.kind is not InstrumentKind.OPTION and self.underlying_identity is not None:
            raise DomainInvariantError(
                "Instrument.underlying_identity is only valid for option instruments"
            )


@dataclass(frozen=True, slots=True)
class Holding:
    """One valued position in an immutable PortfolioSnapshot.

    ``quantity`` is an absolute unit count and ``direction`` carries its sign.
    ``market_value`` is absolute current value; ``gross_exposure`` is the
    supplied non-negative policy exposure.  Neither is derived in this model.
    """

    holding_id: str
    account_id: str
    instrument: Instrument
    direction: PositionDirection
    quantity: Decimal
    market_value: MonetaryAmount
    gross_exposure: MonetaryAmount
    valued_at: datetime
    valuation_evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        _require_text(self.holding_id, "Holding", "holding_id")
        _require_text(self.account_id, "Holding", "account_id")
        _require_non_negative(self.quantity, "Holding", "quantity")
        if self.quantity == 0:
            raise DomainInvariantError("Holding.quantity must be greater than zero")
        _require_non_negative(self.market_value.amount, "Holding", "market_value.amount")
        _require_non_negative(self.gross_exposure.amount, "Holding", "gross_exposure.amount")
        if self.market_value.currency != self.gross_exposure.currency:
            raise DomainInvariantError("Holding valuation currencies must match")
        require_tz_aware(self.valued_at, "Holding", "valued_at")
        if not self.valuation_evidence:
            raise DomainInvariantError("Holding.valuation_evidence cannot be empty")


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """Complete portfolio state at one semantic observation time.

    Cash is the signed settled ledger balance.  Buying power is the
    non-negative amount currently available for new positions after external
    account restrictions.  Gross exposure is supplied valuation evidence,
    not a quantity or average-cost calculation performed by this contract.
    """

    portfolio_snapshot_id: str
    portfolio_id: str
    base_currency: str
    holdings: tuple[Holding, ...]
    cash_balance: MonetaryAmount
    buying_power: MonetaryAmount
    net_liquidation_value: MonetaryAmount
    gross_exposure: MonetaryAmount
    observed_at: datetime
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        _require_text(self.portfolio_snapshot_id, "PortfolioSnapshot", "portfolio_snapshot_id")
        _require_text(self.portfolio_id, "PortfolioSnapshot", "portfolio_id")
        _require_text(self.base_currency, "PortfolioSnapshot", "base_currency")
        require_tz_aware(self.observed_at, "PortfolioSnapshot", "observed_at")
        currencies = {
            self.cash_balance.currency,
            self.buying_power.currency,
            self.net_liquidation_value.currency,
            self.gross_exposure.currency,
            *(holding.market_value.currency for holding in self.holdings),
        }
        if currencies != {self.base_currency}:
            raise DomainInvariantError("PortfolioSnapshot monetary values must use base_currency")
        _require_non_negative(self.buying_power.amount, "PortfolioSnapshot", "buying_power.amount")
        _require_non_negative(
            self.gross_exposure.amount, "PortfolioSnapshot", "gross_exposure.amount"
        )
        holding_ids = tuple(holding.holding_id for holding in self.holdings)
        if len(holding_ids) != len(set(holding_ids)):
            raise DomainInvariantError("PortfolioSnapshot contains duplicate holding_id values")
        if not self.evidence:
            raise DomainInvariantError("PortfolioSnapshot.evidence cannot be empty")


@dataclass(frozen=True, slots=True)
class ProposedPosition:
    """Intelligence output describing desired exposure, never an order.

    ``quantity`` is the absolute size of this proposal, not an order delta or
    a post-execution portfolio target.  Operational policy compares it with
    the separately supplied snapshot before any read-only plan is presented.
    """

    proposed_position_id: str
    opportunity_id: str
    ranking_result_id: str
    ranking_id: str
    proposal_algorithm_version: str
    portfolio_id: str
    account_id: str
    instrument: Instrument
    direction: PositionDirection
    target_allocation: Decimal
    quantity: Decimal
    estimated_unit_price: MonetaryAmount
    gross_exposure: MonetaryAmount
    evidence_confidence: Confidence
    rationale: tuple[str, ...]
    effective_parameters: tuple[tuple[str, Decimal], ...]
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "proposed_position_id",
            "opportunity_id",
            "ranking_result_id",
            "ranking_id",
            "proposal_algorithm_version",
            "portfolio_id",
            "account_id",
        ):
            _require_text(getattr(self, field_name), "ProposedPosition", field_name)
        require_finite_decimal(self.target_allocation, "ProposedPosition", "target_allocation")
        require_unit_interval(self.target_allocation, "ProposedPosition", "target_allocation")
        if self.target_allocation == 0:
            raise DomainInvariantError("ProposedPosition.target_allocation must be greater than zero")
        _require_non_negative(self.quantity, "ProposedPosition", "quantity")
        if self.quantity == 0:
            raise DomainInvariantError("ProposedPosition.quantity must be greater than zero")
        _require_non_negative(
            self.estimated_unit_price.amount,
            "ProposedPosition",
            "estimated_unit_price.amount",
        )
        _require_non_negative(
            self.gross_exposure.amount, "ProposedPosition", "gross_exposure.amount"
        )
        if self.estimated_unit_price.currency != self.gross_exposure.currency:
            raise DomainInvariantError("ProposedPosition valuation currencies must match")
        if not self.rationale:
            raise DomainInvariantError("ProposedPosition.rationale cannot be empty")
        if any(not item or item != item.strip() for item in self.rationale):
            raise DomainInvariantError("ProposedPosition.rationale must be normalized text")
        parameter_keys = tuple(key for key, _ in self.effective_parameters)
        if not parameter_keys:
            raise DomainInvariantError("ProposedPosition.effective_parameters cannot be empty")
        if len(parameter_keys) != len(set(parameter_keys)):
            raise DomainInvariantError("ProposedPosition effective parameter keys must be unique")
        if parameter_keys != tuple(sorted(parameter_keys)):
            raise DomainInvariantError(
                "ProposedPosition effective parameter keys must be in canonical order"
            )
        if "reference_capital" not in parameter_keys:
            raise DomainInvariantError(
                "ProposedPosition.effective_parameters must include reference_capital"
            )
        for key, value in self.effective_parameters:
            _require_text(key, "ProposedPosition", "effective_parameters key")
            require_finite_decimal(value, "ProposedPosition", "effective_parameters value")
        if not self.evidence:
            raise DomainInvariantError("ProposedPosition.evidence cannot be empty")


@dataclass(frozen=True, slots=True)
class PortfolioDecisionRequest:
    """Operational input envelope; proposal order preserves Ranking order."""

    decision_request_id: str
    ranking_result_id: str
    portfolio_snapshot: PortfolioSnapshot
    proposed_positions: tuple[ProposedPosition, ...]

    def __post_init__(self) -> None:
        _require_text(self.decision_request_id, "PortfolioDecisionRequest", "decision_request_id")
        _require_text(self.ranking_result_id, "PortfolioDecisionRequest", "ranking_result_id")
        proposal_ids = tuple(item.proposed_position_id for item in self.proposed_positions)
        if len(proposal_ids) != len(set(proposal_ids)):
            raise DomainInvariantError(
                "PortfolioDecisionRequest contains duplicate proposed_position_id values"
            )
        if any(
            item.ranking_result_id != self.ranking_result_id
            for item in self.proposed_positions
        ):
            raise DomainInvariantError(
                "PortfolioDecisionRequest proposals must reference ranking_result_id"
            )
        if any(
            item.portfolio_id != self.portfolio_snapshot.portfolio_id
            for item in self.proposed_positions
        ):
            raise DomainInvariantError(
                "PortfolioDecisionRequest proposals must target the snapshot portfolio_id"
            )
