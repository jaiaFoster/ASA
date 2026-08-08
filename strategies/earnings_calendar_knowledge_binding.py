"""Earnings Calendar's own strategy-specific integration binding
(SPRINT-014 S14-PR-05A, Architect checkpoint: ninth/tenth review -- "a
strategy-specific integration binding may know how Earnings' selected
structural inputs map onto generic facts and registered analytics, but
the orchestrator that invokes bindings must be generic").

Owns exactly the mapping from EarningsCalendarStructuralSelection onto
generic facts.canonical_projection.CanonicalFactRequest/
analytics.features.DerivedFactRequest data -- including the actual
compute_realized_volatility()/compute_iv_term_structure_spread()/
compute_atm_iv_vs_realized_volatility() calls (Architect checkpoint,
ninth review, item 3: a binding "may know how ... structural inputs map
onto ... registered analytics"). Never calls materialize_derived_fact()
or project_canonical_fact() itself -- those generic mechanics stay owned
by strategy_runtime.knowledge_composition, which this binding's own
output only supplies data to.

Tenth-review correction: the actual analytics calls now happen inside
``compute_derived_fact_requests``, a callback the generic orchestrator
invokes *after* it has projected this binding's own canonical facts --
extracting the front/back implied volatilities it needs from the
projected CanonicalFact objects the orchestrator hands back, never from
this module's own private ``structural`` values directly. That is the
literal difference between "analytics runs after canonical projection"
and "analytics runs on the same raw inputs canonical projection also
happened to receive" -- restoring Sprint 14's target order, not merely
its target import graph.

The returned KnowledgeMapping's ``build_payload`` closure records the
exact parameterized derived-fact IDs for IV_TERM_STRUCTURE_SPREAD and
ATM_IV_VS_REALIZED (Architect checkpoint, ninth review, item 5) --
computed here via the same derived_fact_id() the orchestrator's own
materialize_derived_fact() call will independently reproduce from
identical inputs, so evaluation retrieves the exact same records by ID
rather than rediscovering or recomputing them.
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
from analytics.features import DerivedFactQualityStatus, DerivedFactRequest, DerivedFactSet
from analytics.realized_volatility import (
    InsufficientPriceHistoryError,
    compute_realized_volatility,
)
from domain import (
    CanonicalFact,
    EarningsEvent,
    EvidenceKind,
    EvidenceReference,
    ExpirationCycle,
    MarketCapability,
    OptionChain,
    UnknownReason,
)
from facts.canonical_projection import CanonicalFactRequest, canonical_fact_id
from strategies.earnings_calendar_structure import EarningsCalendarStructuralSelection
from strategies.knowledge_contracts import KnowledgeMapping

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
) -> KnowledgeMapping[EarningsCalendarPayload]:
    """Map one EarningsCalendarStructuralSelection onto the generic
    canonical-fact requests and derived-fact computation callback
    strategy_runtime.knowledge_composition.compose_strategy_knowledge
    needs. Always succeeds structurally -- the one genuine data gap this
    binding can produce (fewer than two historical daily closes) is only
    reachable once the returned callback actually runs the realized-
    volatility computation, which happens after canonical projection, so
    it surfaces as a typed UnknownReason from that callback, not from
    this function.
    """
    front_iv_fact_id = canonical_fact_id(
        FACT_TYPE_OPTION_IMPLIED_VOLATILITY, structural.front_contract_identity, snapshot_digest
    )
    back_iv_fact_id = canonical_fact_id(
        FACT_TYPE_OPTION_IMPLIED_VOLATILITY, structural.back_contract_identity, snapshot_digest
    )

    canonical_fact_requests = (
        CanonicalFactRequest(
            MarketCapability.REAL_TIME_QUOTE_V1,
            structural.quote_observation_id,
            structural.spot_price,
            subject,
            FACT_TYPE_SPOT_PRICE,
        ),
        CanonicalFactRequest(
            MarketCapability.EARNINGS_CALENDAR_V1,
            structural.earnings_observation_id,
            structural.event.earnings_date.isoformat(),
            subject,
            FACT_TYPE_EARNINGS_DATE,
        ),
        CanonicalFactRequest(
            MarketCapability.EARNINGS_CALENDAR_V1,
            structural.earnings_observation_id,
            structural.event.confirmed,
            subject,
            FACT_TYPE_EARNINGS_CONFIRMED,
        ),
        CanonicalFactRequest(
            MarketCapability.OPTION_CHAIN_V1,
            structural.chain_observation_id,
            structural.front_implied_volatility,
            structural.front_contract_identity,
            FACT_TYPE_OPTION_IMPLIED_VOLATILITY,
        ),
        CanonicalFactRequest(
            MarketCapability.OPTION_CHAIN_V1,
            structural.chain_observation_id,
            structural.back_implied_volatility,
            structural.back_contract_identity,
            FACT_TYPE_OPTION_IMPLIED_VOLATILITY,
        ),
    )

    # I-07 parameter identity: both features' own values depend on
    # exactly which front/back contracts were selected, so their
    # derived_fact_ids must depend on them too -- purely structural, so
    # (unlike the analytics values themselves) safe to fix before the
    # canonical facts those values will be read back off even exist.
    term_structure_parameters = (
        ("front_contract_id", structural.front_contract_identity),
        ("back_contract_id", structural.back_contract_identity),
    )
    iv_realized_parameters = (
        ("front_contract_id", structural.front_contract_identity),
        ("historical_bars_observation_id", structural.bars_observation_id),
    )
    term_structure_fact_id = derived_fact_id(
        IV_TERM_STRUCTURE_SPREAD, subject, snapshot_digest, parameters=term_structure_parameters
    )
    atm_iv_vs_realized_fact_id = derived_fact_id(
        ATM_IV_VS_REALIZED, subject, snapshot_digest, parameters=iv_realized_parameters
    )

    def _compute_derived_fact_requests(
        canonical_facts: tuple[CanonicalFact, ...],
    ) -> tuple[DerivedFactRequest, ...] | UnknownReason:
        """Runs only once the generic orchestrator has already projected
        this binding's own canonical facts (Architect checkpoint, tenth
        review, item 2) -- reads the front/back implied volatilities back
        off those *projected* facts, never off ``structural`` directly, so
        this computation's own input is what the generic seam actually
        produced, not a private bypass of it.
        """
        front_iv_fact = next(
            fact for fact in canonical_facts if fact.fact_id == front_iv_fact_id
        )
        back_iv_fact = next(fact for fact in canonical_facts if fact.fact_id == back_iv_fact_id)
        front_iv = front_iv_fact.value
        back_iv = back_iv_fact.value
        assert isinstance(front_iv, Decimal)
        assert isinstance(back_iv, Decimal)

        try:
            realized_volatility = compute_realized_volatility(structural.bars_closes)
        except InsufficientPriceHistoryError:
            return UnknownReason(
                "insufficient_historical_bars",
                demand_ids=(structural.historical_bars_demand_id,),
            )

        front_iv_evidence = EvidenceReference(
            EvidenceKind.CANONICAL_FACT, front_iv_fact.fact_id, _CANONICAL_FACT_VERSION
        )
        back_iv_evidence = EvidenceReference(
            EvidenceKind.CANONICAL_FACT, back_iv_fact.fact_id, _CANONICAL_FACT_VERSION
        )
        bars_evidence = (
            EvidenceReference(EvidenceKind.OBSERVATION, structural.bars_observation_id),
        )

        term_structure_spread = compute_iv_term_structure_spread(front_iv, back_iv)
        # Owns its own realized-volatility computation end to end
        # (compute_atm_iv_vs_realized_volatility) rather than reusing the
        # REALIZED_VOLATILITY value computed above for reuse elsewhere --
        # ATM_IV_VS_REALIZED's own registered formula_version must own
        # the entire computation, never silently depend on a separately-
        # versioned intermediate.
        iv_realized_spread = compute_atm_iv_vs_realized_volatility(
            front_iv, structural.bars_closes
        )

        return (
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
        compute_derived_fact_requests=_compute_derived_fact_requests,
        build_payload=_build_payload,
    )
