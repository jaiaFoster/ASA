"""Read-only Earnings Calendar snapshot -> strategy-owned evaluation
orchestration (SPRINT-014 S14-PR-05A, Architect checkpoint: sixth
review corrective refactor).

Looks up an already-sealed subject snapshot's own resolutions, verifies
the supplied phase-two evidence genuinely belongs to that snapshot (never
guesses which of possibly several same-capability observations is
"the" one), extracts plain domain values, and delegates every
Earnings-specific decision -- ATM selection, richness normalization,
manifest choice, execution-context construction, graph compilation and
execution -- to strategies.earnings_calendar_evaluation.
evaluate_earnings_calendar(). This module performs no financial
computation of its own (ADR-010: "screening must not normalize strategy
scores"); it only orchestrates and projects the strategy's own returned
scalars into CanonicalFacts through screening.subject_fact_projection,
the one narrow file in screening/ permitted to import facts/.

Never reads SubjectPlanResult.diagnostic_fulfillments -- only
snapshot.resolution_results/observations (already-sealed, resolved
evidence) and the phase-two evidence a strategy's own pure expansion
already selected and gated as usable. No acquisition, no production
wiring, no RuntimeContext, no composition-root change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from analytics.features import DerivedFactSet
from domain import (
    CanonicalFact,
    EarningsEvent,
    ExpirationCollection,
    MarketCapability,
    OHLCVSeries,
    OptionChain,
    Quote,
    UnknownReason,
)
from market_data.snapshot import MarketSnapshot
from screening.subject_fact_projection import project_scalar_canonical_fact, resolution_for
from strategies.earnings_calendar_evaluation import (
    FACT_TYPE_BACK_ATM_IMPLIED_VOLATILITY,
    FACT_TYPE_EARNINGS_CONFIRMED,
    FACT_TYPE_EARNINGS_DATE,
    FACT_TYPE_FRONT_ATM_IMPLIED_VOLATILITY,
    FACT_TYPE_SPOT_PRICE,
    evaluate_earnings_calendar,
)
from strategies.earnings_calendar_planning import EarningsCalendarPhaseTwoEvidence
from strategies.type_system import ComponentValues


class SealedEvidenceProvenanceError(ValueError):
    """The supplied phase-two evidence references an observation id the
    supplied sealed snapshot does not contain -- an invariant/provenance
    failure (Architect checkpoint item 6: "a mismatched evidence bundle
    is an invariant/provenance failure, not ordinary UNKNOWN"), never a
    typed UnknownReason.
    """


@dataclass(frozen=True, slots=True)
class EarningsCalendarComposition:
    """Everything the read-only Earnings Calendar path produces from one
    sealed snapshot: the canonical facts extracted from it, the derived
    facts analytics/ computed over them, and the existing manifest/graph's
    own execution output -- never a strategy verdict computed here, only
    what strategies.earnings_calendar_evaluation itself returned.
    """

    canonical_facts: tuple[CanonicalFact, ...]
    derived_facts: DerivedFactSet
    graph_outputs: ComponentValues


def _verify_evidence_belongs_to_snapshot(
    snapshot: MarketSnapshot, phase_two: EarningsCalendarPhaseTwoEvidence
) -> None:
    known_observation_ids = {item.observation_id for item in snapshot.observations}
    for evidence in (
        phase_two.spot_price_evidence,
        phase_two.earnings_evidence,
        phase_two.historical_bars_evidence,
        phase_two.expiration_discovery_evidence,
        phase_two.front_chain_evidence,
        phase_two.back_chain_evidence,
    ):
        missing = set(evidence.observation_ids) - known_observation_ids
        if missing:
            raise SealedEvidenceProvenanceError(
                f"phase-two evidence for demand {evidence.demand_id!r} references "
                f"observation id(s) {sorted(missing)} absent from the supplied sealed snapshot"
            )


def compose_earnings_calendar_evaluation(
    symbol: str,
    snapshot: MarketSnapshot,
    phase_two: EarningsCalendarPhaseTwoEvidence,
    selections: tuple[tuple[str, object], ...],
) -> EarningsCalendarComposition | UnknownReason:
    """Compose one Earnings Calendar evaluation entirely from an already-
    sealed snapshot -- no acquisition, no provider call, no production
    wiring. ``selections`` is ``DemandExpansion.selections``'s own
    immutable tuple-of-pairs, consumed directly (Architect checkpoint
    item 5) -- never widened back into a mutable dict at this boundary.

    Raises SealedEvidenceProvenanceError if ``phase_two`` references any
    observation id the supplied ``snapshot`` does not itself contain --
    a real defect, never a typed UnknownReason. Returns a typed
    UnknownReason (never raises otherwise) for every genuine, expected
    data gap, including the two this module still checks itself
    (unresolved capability / unexpected resolved-value shape) and the
    ones strategies.earnings_calendar_evaluation returns (missing spot
    price, no CALL contracts at a selected expiration, missing implied
    volatility, insufficient historical bars).
    """
    _verify_evidence_belongs_to_snapshot(snapshot, phase_two)

    selections_by_key = dict(selections)
    front_expiration_raw = selections_by_key.get("front_expiration")
    back_expiration_raw = selections_by_key.get("back_expiration")
    if not isinstance(front_expiration_raw, str) or not isinstance(back_expiration_raw, str):
        return UnknownReason("missing_expiration_pair_selection")
    front_expiration = date.fromisoformat(front_expiration_raw)
    back_expiration = date.fromisoformat(back_expiration_raw)

    discovery_value = phase_two.expiration_discovery_evidence.value
    if not isinstance(discovery_value, ExpirationCollection):
        return UnknownReason("unexpected_resolved_value_shape")
    front_cycle = next(
        (item for item in discovery_value.cycles if item.expiration_date == front_expiration), None
    )
    back_cycle = next(
        (item for item in discovery_value.cycles if item.expiration_date == back_expiration), None
    )
    if front_cycle is None or back_cycle is None:
        return UnknownReason("selected_expiration_not_in_discovery_collection")

    quote_resolution = resolution_for(snapshot, MarketCapability.REAL_TIME_QUOTE_V1)
    earnings_resolution = resolution_for(snapshot, MarketCapability.EARNINGS_CALENDAR_V1)
    bars_resolution = resolution_for(snapshot, MarketCapability.HISTORICAL_BARS_V1)
    chain_resolution = resolution_for(snapshot, MarketCapability.OPTION_CHAIN_V1)

    quote_observation = quote_resolution.selected_observation
    event_observation = earnings_resolution.selected_observation
    bars_observation = bars_resolution.selected_observation
    chain_observation = chain_resolution.selected_observation
    if (
        quote_observation is None
        or event_observation is None
        or bars_observation is None
        or chain_observation is None
    ):
        return UnknownReason("unresolved_earnings_calendar_capability")
    if (
        not isinstance(quote_observation.value, Quote)
        or not isinstance(event_observation.value, EarningsEvent)
        or not isinstance(bars_observation.value, OHLCVSeries)
        or not isinstance(chain_observation.value, OptionChain)
    ):
        return UnknownReason("unexpected_resolved_value_shape")

    evaluation = evaluate_earnings_calendar(
        quote=quote_observation.value,
        event=event_observation.value,
        chain=chain_observation.value,
        bars_closes=tuple(bar.close for bar in bars_observation.value.bars),
        bars_observation_id=bars_observation.observation_id,
        front_expiration=front_expiration,
        back_expiration=back_expiration,
        front_cycle=front_cycle,
        back_cycle=back_cycle,
        as_of=snapshot.as_of.date(),
        subject=symbol,
        snapshot_digest=snapshot.snapshot_digest,
        effective_time=snapshot.as_of,
    )
    if isinstance(evaluation, UnknownReason):
        return evaluation

    canonical_facts: list[CanonicalFact] = []
    for resolution, value, fact_type in (
        (quote_resolution, evaluation.spot_price, FACT_TYPE_SPOT_PRICE),
        (earnings_resolution, evaluation.earnings_date.isoformat(), FACT_TYPE_EARNINGS_DATE),
        (earnings_resolution, evaluation.earnings_confirmed, FACT_TYPE_EARNINGS_CONFIRMED),
        (
            chain_resolution,
            evaluation.front_atm_implied_volatility,
            FACT_TYPE_FRONT_ATM_IMPLIED_VOLATILITY,
        ),
        (
            chain_resolution,
            evaluation.back_atm_implied_volatility,
            FACT_TYPE_BACK_ATM_IMPLIED_VOLATILITY,
        ),
    ):
        fact = project_scalar_canonical_fact(
            resolution,
            value=value,
            subject=symbol,
            fact_type=fact_type,
            snapshot_digest=snapshot.snapshot_digest,
            effective_time=snapshot.as_of,
        )
        if fact is None:
            return UnknownReason("resolution_unresolved")
        canonical_facts.append(fact)

    return EarningsCalendarComposition(
        canonical_facts=tuple(canonical_facts),
        derived_facts=evaluation.derived_facts,
        graph_outputs=evaluation.graph_outputs,
    )
