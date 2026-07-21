"""Shared domain module (ADR-004 `domain/`).

Cross-cutting, immutable value types referenced by multiple layers —
defined once here, referenced everywhere (Constitution Law 3). Structural
definitions only; no business logic lives in this package (ASA-CORE-001).

Depends on nothing but itself and the standard library.
"""

from domain.canonical_fact import CanonicalFact
from domain.execution import (
    BrokerRequest,
    BrokerRequestSide,
    ExecutionContext,
    ExecutionPlan,
    OrderType,
    PortfolioDecision,
    PortfolioDecisionState,
    TimeInForce,
)
from domain.financial import (
    FINANCIAL_CONTRACT_VERSION,
    AnnouncementTime,
    EarningsCalendar,
    EarningsEvent,
    EarningsHistoryEntry,
    ExpirationCollection,
    ExpirationCycle,
    FinancialContractSerializationError,
    OptionChain,
    OptionCollection,
    OptionContract,
    OptionLeg,
    OptionLegPosition,
    OptionStructure,
    OptionStructureType,
    OptionType,
    Security,
    SecurityAssetType,
    SecurityCollection,
    VolatilityEvidence,
    deserialize_financial_contract,
    financial_contract_to_data,
    serialize_financial_contract,
)
from domain.guardrail import GuardrailOutcome
from domain.indicator import Indicator
from domain.observation import Observation
from domain.opportunity import Opportunity, RecommendationState
from domain.operational import (
    CanonicalInstrumentIdentity,
    Holding,
    Instrument,
    InstrumentKind,
    MonetaryAmount,
    PortfolioDecisionRequest,
    PortfolioSnapshot,
    PositionDirection,
    ProposedPosition,
    SectorClassification,
)
from domain.outcome_metrics import ExpectedOutcomeMetrics
from domain.provenance import Provenance, ProviderDisagreement
from domain.provider import Provider
from domain.references import Confidence, EvidenceKind, EvidenceReference
from domain.values import DomainInvariantError, is_normalized_value

__all__ = [
    "BrokerRequest",
    "BrokerRequestSide",
    "CanonicalFact",
    "CanonicalInstrumentIdentity",
    "Confidence",
    "DomainInvariantError",
    "is_normalized_value",
    "EvidenceKind",
    "EvidenceReference",
    "ExpectedOutcomeMetrics",
    "ExecutionContext",
    "ExecutionPlan",
    "FINANCIAL_CONTRACT_VERSION",
    "FinancialContractSerializationError",
    "GuardrailOutcome",
    "AnnouncementTime",
    "EarningsCalendar",
    "EarningsEvent",
    "EarningsHistoryEntry",
    "ExpirationCollection",
    "ExpirationCycle",
    "Holding",
    "Indicator",
    "Instrument",
    "InstrumentKind",
    "MonetaryAmount",
    "Observation",
    "OptionChain",
    "OptionCollection",
    "OptionContract",
    "OptionLeg",
    "OptionLegPosition",
    "OptionStructure",
    "OptionStructureType",
    "OptionType",
    "Opportunity",
    "OrderType",
    "PortfolioDecision",
    "PortfolioDecisionState",
    "PortfolioDecisionRequest",
    "PortfolioSnapshot",
    "PositionDirection",
    "Provenance",
    "Provider",
    "ProviderDisagreement",
    "ProposedPosition",
    "RecommendationState",
    "Security",
    "SecurityAssetType",
    "SecurityCollection",
    "SectorClassification",
    "TimeInForce",
    "VolatilityEvidence",
    "deserialize_financial_contract",
    "financial_contract_to_data",
    "serialize_financial_contract",
]
