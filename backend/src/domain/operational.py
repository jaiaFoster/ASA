"""Provider-neutral contracts between intelligence and operations (ASA-ARCH-001).

Structural definitions only.  These values contain no portfolio policy,
execution planning, persistence, provider, or broker behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from domain.outcome_metrics import ExpectedOutcomeMetrics
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


class RiskPolicyType(str, Enum):
    BUYING_POWER = "buying_power"
    CASH_RESERVE = "cash_reserve"
    MAX_POSITION_ALLOCATION = "max_position_allocation"
    MAX_SINGLE_ASSET_EXPOSURE = "max_single_asset_exposure"
    MAX_SECTOR_EXPOSURE = "max_sector_exposure"
    DUPLICATE_EXPOSURE = "duplicate_exposure"
    MAXIMUM_LOSS = "maximum_loss"


class RiskPolicyScope(str, Enum):
    PLATFORM = "platform"
    STRATEGY = "strategy"


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
class RiskPolicy:
    risk_policy_id: str
    policy_type: RiskPolicyType
    scope: RiskPolicyScope
    policy_version: str
    parameters: tuple[tuple[str, Decimal | bool], ...]
    strategy_id: str | None
    rationale: tuple[str, ...]
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        _require_text(self.risk_policy_id, "RiskPolicy", "risk_policy_id")
        _require_text(self.policy_version, "RiskPolicy", "policy_version")
        if self.scope is RiskPolicyScope.STRATEGY and self.strategy_id is None:
            raise DomainInvariantError("Strategy RiskPolicy requires strategy_id")
        if self.scope is RiskPolicyScope.PLATFORM and self.strategy_id is not None:
            raise DomainInvariantError("Platform RiskPolicy cannot have strategy_id")
        keys = tuple(key for key, _ in self.parameters)
        if keys != tuple(sorted(set(keys))):
            raise DomainInvariantError("RiskPolicy parameters must be unique and canonical")
        expected = {
            RiskPolicyType.BUYING_POWER: "minimum_remaining_amount",
            RiskPolicyType.CASH_RESERVE: "minimum_cash_ratio",
            RiskPolicyType.MAX_POSITION_ALLOCATION: "maximum_ratio",
            RiskPolicyType.MAX_SINGLE_ASSET_EXPOSURE: "maximum_ratio",
            RiskPolicyType.MAX_SECTOR_EXPOSURE: "maximum_ratio",
            RiskPolicyType.DUPLICATE_EXPOSURE: "allow_increase_existing",
            RiskPolicyType.MAXIMUM_LOSS: "maximum_amount",
        }[self.policy_type]
        if keys != (expected,):
            raise DomainInvariantError(f"{self.policy_type.value} requires exactly {expected}")
        value = self.parameters[0][1]
        if self.policy_type is RiskPolicyType.DUPLICATE_EXPOSURE:
            if type(value) is not bool:
                raise DomainInvariantError("allow_increase_existing must be bool")
        else:
            if type(value) is not Decimal or not value.is_finite():
                raise DomainInvariantError("RiskPolicy numeric parameter must be finite Decimal")
            if value < 0:
                raise DomainInvariantError("RiskPolicy numeric parameter cannot be negative")
            if self.policy_type in {
                RiskPolicyType.CASH_RESERVE,
                RiskPolicyType.MAX_POSITION_ALLOCATION,
                RiskPolicyType.MAX_SINGLE_ASSET_EXPOSURE,
                RiskPolicyType.MAX_SECTOR_EXPOSURE,
            } and value > 1:
                raise DomainInvariantError("RiskPolicy ratio must be within [0, 1]")
        if not self.rationale or not self.evidence:
            raise DomainInvariantError("RiskPolicy requires rationale and evidence")


@dataclass(frozen=True, slots=True)
class Position:
    position_id: str
    account_id: str
    instrument: Instrument
    direction: PositionDirection
    quantity: Decimal
    quantity_increment: Decimal
    average_cost_per_unit: MonetaryAmount
    current_price_per_unit: MonetaryAmount
    price_multiplier: Decimal
    unit_exposure: MonetaryAmount
    market_value: MonetaryAmount
    gross_exposure: MonetaryAmount
    realized_pnl: MonetaryAmount
    unrealized_pnl: MonetaryAmount
    valued_at: datetime
    valuation_evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        _require_text(self.position_id, "Position", "position_id")
        _require_text(self.account_id, "Position", "account_id")
        for name in ("quantity", "quantity_increment", "price_multiplier"):
            value = getattr(self, name)
            _require_non_negative(value, "Position", name)
            if value == 0:
                raise DomainInvariantError(f"Position.{name} must be positive")
        if self.quantity % self.quantity_increment:
            raise DomainInvariantError("Position.quantity must use quantity_increment")
        currencies = {
            self.average_cost_per_unit.currency,
            self.current_price_per_unit.currency,
            self.unit_exposure.currency,
            self.market_value.currency,
            self.gross_exposure.currency,
            self.realized_pnl.currency,
            self.unrealized_pnl.currency,
        }
        if len(currencies) != 1:
            raise DomainInvariantError("Position monetary values must use one currency")
        if currencies != {self.instrument.currency}:
            raise DomainInvariantError("Position monetary currency must match Instrument")
        if self.average_cost_per_unit.amount <= 0 or self.current_price_per_unit.amount <= 0:
            raise DomainInvariantError("Position unit prices must be positive")
        expected_unit = self.current_price_per_unit.amount * self.price_multiplier
        if self.unit_exposure.amount != expected_unit:
            raise DomainInvariantError("Position.unit_exposure must equal price times multiplier")
        if self.market_value.amount != self.quantity * expected_unit:
            raise DomainInvariantError("Position.market_value must equal quantity times unit exposure")
        if self.gross_exposure.amount != self.market_value.amount:
            raise DomainInvariantError("Position gross exposure must equal market value in v1")
        expected_unrealized = (
            (self.current_price_per_unit.amount - self.average_cost_per_unit.amount)
            if self.direction is PositionDirection.LONG
            else (self.average_cost_per_unit.amount - self.current_price_per_unit.amount)
        ) * self.price_multiplier * self.quantity
        if self.unrealized_pnl.amount != expected_unrealized:
            raise DomainInvariantError("Position.unrealized_pnl is incoherent")
        require_tz_aware(self.valued_at, "Position", "valued_at")
        if not self.valuation_evidence:
            raise DomainInvariantError("Position.valuation_evidence cannot be empty")


@dataclass(frozen=True, slots=True)
class InstrumentValuation:
    instrument_valuation_id: str
    instrument: Instrument
    account_id: str
    current_price: MonetaryAmount
    price_multiplier: Decimal
    unit_exposure: MonetaryAmount
    quantity_increment: Decimal
    valued_at: datetime
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        _require_text(self.instrument_valuation_id, "InstrumentValuation", "instrument_valuation_id")
        _require_text(self.account_id, "InstrumentValuation", "account_id")
        for name in ("price_multiplier", "quantity_increment"):
            value = getattr(self, name)
            _require_non_negative(value, "InstrumentValuation", name)
            if value == 0:
                raise DomainInvariantError(f"InstrumentValuation.{name} must be positive")
        if self.current_price.amount <= 0 or self.unit_exposure.amount <= 0:
            raise DomainInvariantError("InstrumentValuation prices and exposure must be positive")
        if self.current_price.currency != self.unit_exposure.currency:
            raise DomainInvariantError("InstrumentValuation currencies must match")
        if self.current_price.currency != self.instrument.currency:
            raise DomainInvariantError("InstrumentValuation currency must match Instrument")
        if self.unit_exposure.amount != self.current_price.amount * self.price_multiplier:
            raise DomainInvariantError("InstrumentValuation unit exposure must equal price times multiplier")
        require_tz_aware(self.valued_at, "InstrumentValuation", "valued_at")
        if not self.evidence:
            raise DomainInvariantError("InstrumentValuation.evidence cannot be empty")


@dataclass(frozen=True, slots=True)
class Portfolio:
    portfolio_id: str
    portfolio_state_id: str
    revision: int
    account_id: str
    base_currency: str
    currency_quantum: Decimal
    positions: tuple[Position, ...]
    cash_balance: MonetaryAmount
    buying_power: MonetaryAmount
    net_liquidation_value: MonetaryAmount
    gross_exposure: MonetaryAmount
    realized_pnl: MonetaryAmount
    unrealized_pnl: MonetaryAmount
    platform_risk_policies: tuple[RiskPolicy, ...]
    policy_activation_evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        for name in ("portfolio_id", "portfolio_state_id", "account_id", "base_currency"):
            _require_text(getattr(self, name), "Portfolio", name)
        if self.base_currency != "USD":
            raise DomainInvariantError("Portfolio v1 base_currency must be USD")
        if self.revision <= 0 or self.currency_quantum <= 0:
            raise DomainInvariantError("Portfolio revision and currency_quantum must be positive")
        if any(position.account_id != self.account_id for position in self.positions):
            raise DomainInvariantError("Portfolio positions must use account_id")
        if any(position.instrument.currency != self.base_currency for position in self.positions):
            raise DomainInvariantError("Portfolio Position currency must use base_currency")
        identities = tuple(position.instrument.identity for position in self.positions)
        if len(identities) != len(set(identities)):
            raise DomainInvariantError("Portfolio positions must be unique by instrument")
        amounts = (
            self.cash_balance,
            self.buying_power,
            self.net_liquidation_value,
            self.gross_exposure,
            self.realized_pnl,
            self.unrealized_pnl,
        )
        if any(amount.currency != self.base_currency for amount in amounts):
            raise DomainInvariantError("Portfolio monetary values must use base_currency")
        if self.buying_power.amount < 0 or self.gross_exposure.amount < 0:
            raise DomainInvariantError("Portfolio buying power and exposure cannot be negative")
        if {policy.policy_type for policy in self.platform_risk_policies} != set(RiskPolicyType):
            raise DomainInvariantError("Portfolio requires the complete v1 Platform RiskPolicy set")
        if any(policy.scope is not RiskPolicyScope.PLATFORM for policy in self.platform_risk_policies):
            raise DomainInvariantError("Portfolio policies must be Platform scoped")
        expected_gross = sum((position.gross_exposure.amount for position in self.positions), Decimal("0"))
        expected_unrealized = sum((position.unrealized_pnl.amount for position in self.positions), Decimal("0"))
        long_value = sum((position.market_value.amount for position in self.positions if position.direction is PositionDirection.LONG), Decimal("0"))
        short_value = sum((position.market_value.amount for position in self.positions if position.direction is PositionDirection.SHORT), Decimal("0"))
        if self.gross_exposure.amount != expected_gross:
            raise DomainInvariantError("Portfolio gross exposure is incoherent")
        if self.unrealized_pnl.amount != expected_unrealized:
            raise DomainInvariantError("Portfolio unrealized P&L is incoherent")
        if self.net_liquidation_value.amount != self.cash_balance.amount + long_value - short_value:
            raise DomainInvariantError("Portfolio net liquidation value is incoherent")
        if not self.policy_activation_evidence:
            raise DomainInvariantError("Portfolio requires policies and activation evidence")


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    portfolio_snapshot_id: str
    portfolio: Portfolio
    instrument_valuations: tuple[InstrumentValuation, ...]
    observed_at: datetime
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        _require_text(self.portfolio_snapshot_id, "PortfolioSnapshot", "portfolio_snapshot_id")
        require_tz_aware(self.observed_at, "PortfolioSnapshot", "observed_at")
        identities = tuple(item.instrument.identity for item in self.instrument_valuations)
        if len(identities) != len(set(identities)):
            raise DomainInvariantError("PortfolioSnapshot valuations must be unique")
        if any(item.account_id != self.portfolio.account_id for item in self.instrument_valuations):
            raise DomainInvariantError("PortfolioSnapshot valuations must use Portfolio account")
        if not self.evidence:
            raise DomainInvariantError("PortfolioSnapshot.evidence cannot be empty")


@dataclass(frozen=True, slots=True)
class ProposedPosition:
    """Intelligence output describing desired allocation, never an order."""

    proposed_position_id: str
    opportunity_id: str
    ranking_result_id: str
    ranking_id: str
    proposal_algorithm_version: str
    instrument: Instrument
    target_allocation: Decimal
    evidence_confidence: Confidence
    expected_outcome_metrics: ExpectedOutcomeMetrics
    strategy_risk_policies: tuple[RiskPolicy, ...]
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
        ):
            _require_text(getattr(self, field_name), "ProposedPosition", field_name)
        require_finite_decimal(self.target_allocation, "ProposedPosition", "target_allocation")
        require_unit_interval(self.target_allocation, "ProposedPosition", "target_allocation")
        if self.target_allocation == 0:
            raise DomainInvariantError("ProposedPosition.target_allocation must be greater than zero")
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
        if any(policy.scope is not RiskPolicyScope.STRATEGY for policy in self.strategy_risk_policies):
            raise DomainInvariantError("ProposedPosition policies must be Strategy scoped")
        for key, value in self.effective_parameters:
            _require_text(key, "ProposedPosition", "effective_parameters key")
            require_finite_decimal(value, "ProposedPosition", "effective_parameters value")
        if not self.evidence:
            raise DomainInvariantError("ProposedPosition.evidence cannot be empty")


@dataclass(frozen=True, slots=True)
class PortfolioEvaluationRequest:
    """Portfolio-evaluation input envelope; proposal order preserves Ranking order."""

    decision_request_id: str
    ranking_result_id: str
    portfolio_snapshot: PortfolioSnapshot
    proposed_positions: tuple[ProposedPosition, ...]

    def __post_init__(self) -> None:
        _require_text(self.decision_request_id, "PortfolioEvaluationRequest", "decision_request_id")
        _require_text(self.ranking_result_id, "PortfolioEvaluationRequest", "ranking_result_id")
        proposal_ids = tuple(item.proposed_position_id for item in self.proposed_positions)
        if len(proposal_ids) != len(set(proposal_ids)):
            raise DomainInvariantError(
                "PortfolioEvaluationRequest contains duplicate proposed_position_id values"
            )
        if any(
            item.ranking_result_id != self.ranking_result_id
            for item in self.proposed_positions
        ):
            raise DomainInvariantError(
                "PortfolioEvaluationRequest proposals must reference ranking_result_id"
            )
