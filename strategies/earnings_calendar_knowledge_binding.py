"""Earnings Calendar's own strategy-specific integration binding
(SPRINT-014 S14-PR-05A, Architect checkpoint: ninth review -- "a
strategy-specific integration binding may know how Earnings' selected
structural inputs map onto generic facts and registered analytics, but
the orchestrator that invokes bindings must be generic").

Owns exactly the mapping from EarningsCalendarStructuralSelection onto
generic domain.CanonicalFactRequest/analytics.features.DerivedFactRequest
data -- including the actual compute_realized_volatility()/
compute_iv_term_structure_spread()/compute_atm_iv_vs_realized_volatility()
calls (Architect checkpoint item 3: a binding "may know how ... structural
inputs map onto ... registered analytics"). Never calls
materialize_derived_fact() or project_canonical_fact() itself -- those
generic mechanics stay owned by strategy_runtime.knowledge_composition,
which this binding's own output only supplies data to.

The returned KnowledgeMapping's ``build_payload`` closure records the
exact parameterized derived-fact IDs for IV_TERM_STRUCTURE_SPREAD and
ATM_IV_VS_REALIZED (Architect checkpoint item 5) -- computed here via the
same derived_fact_id() the orchestrator's own materialize_derived_fact()
call will independently reproduce from identical inputs, so evaluation
retrieves the exact same records by ID rather than rediscovering or
recomputing them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from analytics.derived_fact_materialization import derived_fact_id
from analytics.derived_facts import (
    ATM_IV_VS_REALIZED,
    IV_TERM_STRUCTURE_SPREAD,
    REALIZED_VOLATILITY,
    compute_atm_iv_vs_realized_volatility,
    compute_iv_term_structure_spread,
)
from analytics.features import (
    DerivedFactQualityStatus,
    DerivedFactRequest,
    DerivedFactSet,
    KnowledgeMapping,
)
from analytics.realized_volatility import (
    InsufficientPriceHistoryError,
    compute_realized_volatility,
)
from domain import (
    CanonicalFact,
    CanonicalFactRequest,
    EarningsEvent,
    EvidenceKind,
    EvidenceReference,
    ExpirationCycle,
    MarketCapability,
    OptionChain,
    UnknownReason,
)
from facts.canonical_projection import canonical_fact_id
from strategies.earnings_calendar_structure import EarningsCalendarStructuralSelection

_CANONICAL_FACT_VERSION = 1

# The single source of truth for every canonical fact_type this binding
# requests -- strategies/earnings_calendar_evaluation.py no longer needs
# these (it consumes finished facts by ID, never by fact_type), but tests
# proving canonical-fact-identity genericity still import them from here.
FACT_TYPE_SPOT_PRICE = "spot_price"
FACT_TYPE_EARNINGS_DATE = "earnings_date"
FACT_TYPE_EARNINGS_CONFIRMED = "earnings_confirmed"
# Architect checkpoint (seventh review), item 2: an implied volatility is
# generic canonical knowledge about the exact option contract it was
# observed on, never a "front"/"back" strategy role. One fact_type is
# used for both sides; each fact's own subject is that contract's own
# stable, structural OptionContract.identity, never the earnings
# subject/ticker.
FACT_TYPE_OPTION_IMPLIED_VOLATILITY = "option_implied_volatility"


@dataclass(frozen=True, slots=True)
class EarningsCalendarPayload:
    """The strategy-owned payload strategies/earnings_calendar_evaluation.py
    receives inside its ReadOnlyStrategyInput -- structural values needed
    to build the manifest's own execution context, plus the exact
    parameterized derived-fact IDs evaluation must look up rather than
    recompute.
    """

    event: EarningsEvent
    chain: OptionChain
    front_cycle: ExpirationCycle
    back_cycle: ExpirationCycle
    as_of: date
    target_strike: Decimal
    term_structure_fact_id: str
    atm_iv_vs_realized_fact_id: str


def build_earnings_calendar_knowledge_mapping(
    structural: EarningsCalendarStructuralSelection,
    *,
    subject: str,
    snapshot_digest: str,
) -> KnowledgeMapping[EarningsCalendarPayload] | UnknownReason:
    """Map one EarningsCalendarStructuralSelection onto the generic
    canonical-fact/derived-fact requests strategy_runtime.
    knowledge_composition.compose_strategy_knowledge needs. Returns a
    typed UnknownReason (never raises) for fewer than two historical
    daily closes -- the one genuine data gap only reachable once this
    binding actually attempts the realized-volatility computation
    structural selection deliberately never performs.
    """
    try:
        realized_volatility = compute_realized_volatility(structural.bars_closes)
    except InsufficientPriceHistoryError:
        return UnknownReason(
            "insufficient_historical_bars", demand_ids=(structural.historical_bars_demand_id,)
        )

    front_iv_fact_id = canonical_fact_id(
        FACT_TYPE_OPTION_IMPLIED_VOLATILITY, structural.front_contract_identity, snapshot_digest
    )
    back_iv_fact_id = canonical_fact_id(
        FACT_TYPE_OPTION_IMPLIED_VOLATILITY, structural.back_contract_identity, snapshot_digest
    )
    front_iv_evidence = EvidenceReference(
        EvidenceKind.CANONICAL_FACT, front_iv_fact_id, _CANONICAL_FACT_VERSION
    )
    back_iv_evidence = EvidenceReference(
        EvidenceKind.CANONICAL_FACT, back_iv_fact_id, _CANONICAL_FACT_VERSION
    )
    bars_evidence = (
        EvidenceReference(EvidenceKind.OBSERVATION, structural.bars_observation_id),
    )

    canonical_fact_requests = (
        CanonicalFactRequest(
            MarketCapability.REAL_TIME_QUOTE_V1,
            structural.spot_price,
            subject,
            FACT_TYPE_SPOT_PRICE,
        ),
        CanonicalFactRequest(
            MarketCapability.EARNINGS_CALENDAR_V1,
            structural.event.earnings_date.isoformat(),
            subject,
            FACT_TYPE_EARNINGS_DATE,
        ),
        CanonicalFactRequest(
            MarketCapability.EARNINGS_CALENDAR_V1,
            structural.event.confirmed,
            subject,
            FACT_TYPE_EARNINGS_CONFIRMED,
        ),
        CanonicalFactRequest(
            MarketCapability.OPTION_CHAIN_V1,
            structural.front_implied_volatility,
            structural.front_contract_identity,
            FACT_TYPE_OPTION_IMPLIED_VOLATILITY,
        ),
        CanonicalFactRequest(
            MarketCapability.OPTION_CHAIN_V1,
            structural.back_implied_volatility,
            structural.back_contract_identity,
            FACT_TYPE_OPTION_IMPLIED_VOLATILITY,
        ),
    )

    term_structure_spread = compute_iv_term_structure_spread(
        structural.front_implied_volatility, structural.back_implied_volatility
    )
    # I-07 parameter identity: this feature's own value depends on
    # exactly which front/back contracts were selected, so its
    # derived_fact_id must depend on them too.
    term_structure_parameters = (
        ("front_contract_id", structural.front_contract_identity),
        ("back_contract_id", structural.back_contract_identity),
    )
    # Owns its own realized-volatility computation end to end
    # (compute_atm_iv_vs_realized_volatility) rather than reusing the
    # REALIZED_VOLATILITY value computed above for reuse elsewhere --
    # ATM_IV_VS_REALIZED's own registered formula_version must own the
    # entire computation, never silently depend on a separately-
    # versioned intermediate.
    iv_realized_spread = compute_atm_iv_vs_realized_volatility(
        structural.front_implied_volatility, structural.bars_closes
    )
    iv_realized_parameters = (
        ("front_contract_id", structural.front_contract_identity),
        ("historical_bars_observation_id", structural.bars_observation_id),
    )

    derived_fact_requests = (
        DerivedFactRequest(
            REALIZED_VOLATILITY,
            subject,
            realized_volatility,
            "annualized_stdev",
            bars_evidence,
            DerivedFactQualityStatus.VALID,
        ),
        DerivedFactRequest(
            IV_TERM_STRUCTURE_SPREAD,
            subject,
            term_structure_spread,
            "implied_volatility_points",
            (front_iv_evidence, back_iv_evidence),
            DerivedFactQualityStatus.VALID,
            term_structure_parameters,
        ),
        DerivedFactRequest(
            ATM_IV_VS_REALIZED,
            subject,
            iv_realized_spread,
            "implied_volatility_points",
            (front_iv_evidence, *bars_evidence),
            DerivedFactQualityStatus.VALID,
            iv_realized_parameters,
        ),
    )

    term_structure_fact_id = derived_fact_id(
        IV_TERM_STRUCTURE_SPREAD, subject, snapshot_digest, parameters=term_structure_parameters
    )
    atm_iv_vs_realized_fact_id = derived_fact_id(
        ATM_IV_VS_REALIZED, subject, snapshot_digest, parameters=iv_realized_parameters
    )

    def _build_payload(
        _canonical_facts: tuple[CanonicalFact, ...], _derived_facts: DerivedFactSet
    ) -> EarningsCalendarPayload:
        return EarningsCalendarPayload(
            event=structural.event,
            chain=structural.chain,
            front_cycle=structural.front_cycle,
            back_cycle=structural.back_cycle,
            as_of=structural.as_of,
            target_strike=structural.target_strike,
            term_structure_fact_id=term_structure_fact_id,
            atm_iv_vs_realized_fact_id=atm_iv_vs_realized_fact_id,
        )

    return KnowledgeMapping(
        canonical_fact_requests=canonical_fact_requests,
        derived_fact_requests=derived_fact_requests,
        build_payload=_build_payload,
    )
