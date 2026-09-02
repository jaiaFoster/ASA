import json
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from asa.application.ports.portfolio_lifecycle import PortfolioLifecycleRepository
from asa.contracts.portfolio import PortfolioSnapshot
from asa.contracts.portfolio_lifecycle import (
    PositionAssociation,
    PositionLifecycleObservation,
    PositionLifecycleState,
    ReconciliationState,
    TrackedCandidate,
)
from strategy_runtime.persistence import LatestResultRepository, UniversalSignalRow


class CandidateNotFoundError(LookupError):
    pass


class TrackCandidateService:
    def __init__(
        self,
        results: LatestResultRepository,
        lifecycle: PortfolioLifecycleRepository,
    ) -> None:
        self._results = results
        self._lifecycle = lifecycle

    def track(
        self, strategy_id: str, symbol: str, observation_id: str, tracked_at: datetime
    ) -> TrackedCandidate:
        row = self._results.get_one(strategy_id, symbol.upper())
        if row is None or row.observation_id != observation_id:
            raise CandidateNotFoundError("originating screening observation is unavailable")
        proposal = self._lifecycle.execution_readiness(row.signal_id, row.symbol)
        candidate = _candidate_from_row(row, tracked_at)
        if proposal is not None and proposal.originating_observation_id == row.observation_id:
            payload = json.loads(proposal.canonical_json)
            proposal_symbols = tuple(
                sorted(
                    str(item["instrument_id_value"]).upper()
                    for item in payload.get("exact_legs", ())
                    if isinstance(item, dict)
                    and item.get("instrument_id_scheme") == "occ"
                )
            )
            candidate = TrackedCandidate(
                id=candidate.id,
                originating_observation_id=candidate.originating_observation_id,
                opportunity_id=candidate.opportunity_id,
                strategy_id=candidate.strategy_id,
                strategy_version=candidate.strategy_version,
                symbol=candidate.symbol,
                tracked_at=candidate.tracked_at,
                originating_observed_at=candidate.originating_observed_at,
                evidence_observed_at=candidate.evidence_observed_at,
                exact_option_symbols=proposal_symbols or candidate.exact_option_symbols,
                resolved_proposal_identity=proposal.assessment_identity,
                resolved_proposal_json=proposal.canonical_json,
            )
        return self._lifecycle.add_candidate(candidate)


class PortfolioReconciliationService:
    def reconcile_and_record(
        self,
        snapshot: PortfolioSnapshot,
        repository: PortfolioLifecycleRepository,
    ) -> tuple[PositionAssociation, ...]:
        associations = self.reconcile(snapshot, repository.candidates())
        for association in associations:
            repository.append_association(association)
        matched = {
            item.tracked_candidate_id: item
            for item in associations
            if item.state is ReconciliationState.MATCHED
        }
        for candidate in repository.candidates():
            matched_association = matched.get(candidate.id)
            prior = repository.lifecycle_observations(candidate.id)
            previously_open = any(item.state is PositionLifecycleState.OPEN for item in prior)
            state = (
                PositionLifecycleState.OPEN
                if matched_association is not None
                else PositionLifecycleState.CLOSED
                if previously_open
                else PositionLifecycleState.TRACKED
            )
            repository.append_lifecycle_observation(
                PositionLifecycleObservation(
                    tracked_candidate_id=candidate.id,
                    state=state,
                    broker_position_key=(
                        None
                        if matched_association is None
                        else matched_association.broker_position_key
                    ),
                    broker_observed_at=snapshot.observed_at,
                    strategy_result_observed_at=candidate.originating_observed_at,
                    evidence_observed_at=candidate.evidence_observed_at,
                )
            )
        return associations

    def reconcile(
        self,
        snapshot: PortfolioSnapshot,
        candidates: tuple[TrackedCandidate, ...],
    ) -> tuple[PositionAssociation, ...]:
        observed_at = snapshot.observed_at
        by_symbol: dict[str, list[TrackedCandidate]] = {}
        for candidate in candidates:
            if candidate.exact_option_symbols:
                key = "|".join(sorted(candidate.exact_option_symbols))
                by_symbol.setdefault(key, []).append(candidate)
        held_by_account: dict[UUID, set[str]] = {}
        for leg in snapshot.option_legs:
            held_by_account.setdefault(leg.account_id, set()).add(leg.option_symbol)
        associations: list[PositionAssociation] = []
        for account_id, held in held_by_account.items():
            for instrument_key, eligible in by_symbol.items():
                required = set(instrument_key.split("|"))
                if not required.issubset(held):
                    continue
                state = (
                    ReconciliationState.MATCHED
                    if len(eligible) == 1
                    else ReconciliationState.AMBIGUOUS
                )
                for candidate in eligible:
                    associations.append(
                        PositionAssociation(
                            tracked_candidate_id=candidate.id,
                            broker_position_key=f"{account_id}:{instrument_key}",
                            state=state,
                            observed_at=observed_at,
                        )
                    )
        return tuple(associations)


def _candidate_from_row(row: UniversalSignalRow, tracked_at: datetime) -> TrackedCandidate:
    option_symbols = row.metrics.get("decision.option_symbols")
    native = None if option_symbols is None else option_symbols.native()
    exact_symbols = (
        tuple(sorted(str(item).upper() for item in native)) if isinstance(native, list) else ()
    )
    return TrackedCandidate(
        id=uuid5(NAMESPACE_URL, f"asa:tracked:{row.observation_id}"),
        originating_observation_id=row.observation_id,
        opportunity_id=row.opportunity_id,
        strategy_id=row.signal_id,
        strategy_version=row.signal_version,
        symbol=row.symbol,
        tracked_at=tracked_at.astimezone(UTC),
        originating_observed_at=row.observed_at.astimezone(UTC),
        evidence_observed_at=(
            row.temporal.observed_at.astimezone(UTC)
            if row.temporal is not None
            else row.observed_at.astimezone(UTC)
        ),
        exact_option_symbols=exact_symbols,
    )
