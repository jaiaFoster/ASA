"""Immutable canonical/derived knowledge mapping for Heston SP-05D."""

from datetime import date, timedelta
from decimal import Decimal

from analytics.derived_facts import STRADDLE_MOMENTUM_FORMATION
from analytics.features import DerivedFactQualityStatus, DerivedFactRequest, DerivedFactSet
from analytics.option_facts import option_mid
from analytics.option_return_history import MonthlyOptionReturn, straddle_momentum_formation
from analytics.option_returns import straddle_return, zero_delta_straddle_weights
from domain import (
    CanonicalFact,
    EvidenceKind,
    EvidenceReference,
    HistoricalOptionPanel,
    MarketCapability,
    OptionChain,
    OptionContract,
    OptionType,
    UnknownReason,
)
from facts.canonical_projection import CanonicalFactRequest, canonical_fact_id
from strategies.heston_manifest import heston_parameter
from strategies.heston_portfolio import HestonSubjectCandidate
from strategies.knowledge_contracts import KnowledgeMapping

FACT_PANEL = "historical_option_panel_identity"
FACT_CHAIN = "option_chain_identity"


def _relative_spread(contract: OptionContract) -> Decimal | UnknownReason:
    mid = option_mid(contract.bid, contract.ask)
    if isinstance(mid, UnknownReason) or contract.bid is None or contract.ask is None or mid <= 0:
        return UnknownReason("missing_option_market")
    return (contract.ask - contract.bid) / mid


def _select_pair(
    contracts: tuple[OptionContract, ...],
    *,
    require_open_interest: bool,
    after_date: date | None = None,
) -> tuple[OptionContract, OptionContract] | UnknownReason:
    future_expirations = tuple(
        sorted(
            {
                contract.expiration
                for contract in contracts
                if after_date is None or contract.expiration > after_date
            }
        )
    )
    selected_expiration = future_expirations[0] if future_expirations else None
    grouped: dict[tuple[object, Decimal], dict[OptionType, OptionContract]] = {}
    for contract in contracts:
        if contract.delta is None or (
            selected_expiration is not None and contract.expiration != selected_expiration
        ):
            continue
        grouped.setdefault((contract.expiration, contract.strike), {})[contract.option_type] = (
            contract
        )
    candidates: list[tuple[Decimal, OptionContract, OptionContract]] = []
    incomplete_open_interest = False
    lower = Decimal(str(heston_parameter("minimum_call_delta")))
    upper = Decimal(str(heston_parameter("maximum_call_delta")))
    spread_max = Decimal(str(heston_parameter("maximum_leg_relative_spread")))
    for sides in grouped.values():
        call = sides.get(OptionType.CALL)
        put = sides.get(OptionType.PUT)
        if call is None or put is None or call.delta is None or not lower <= call.delta <= upper:
            continue
        if require_open_interest and (
            call.open_interest is None
            or put.open_interest is None
            or call.open_interest <= 0
            or put.open_interest <= 0
        ):
            incomplete_open_interest = incomplete_open_interest or (
                call.open_interest is None or put.open_interest is None
            )
            continue
        candidates.append((abs(call.delta - Decimal("0.5")), call, put))
    if not candidates:
        return UnknownReason(
            "G_HES_LOWCOST_PAIR_UNKNOWN"
            if incomplete_open_interest
            else "G_HES_LOWCOST_PAIR_FAIL"
        )
    minimum = min(item[0] for item in candidates)
    nearest = tuple(item for item in candidates if item[0] == minimum)
    if len(nearest) != 1:
        return UnknownReason("AMBIGUOUS_SELECTION")
    call, put = nearest[0][1], nearest[0][2]
    spreads = (_relative_spread(call), _relative_spread(put))
    if any(isinstance(item, UnknownReason) for item in spreads) or any(
        item > spread_max for item in spreads if isinstance(item, Decimal)
    ):
        if any(isinstance(item, UnknownReason) for item in spreads):
            return UnknownReason("G_HES_LOWCOST_PAIR_UNKNOWN")
        return UnknownReason("G_HES_LOWCOST_PAIR_FAIL")
    return call, put


def _third_friday(year: int, month: int) -> date:
    first = date(year, month, 1)
    first_friday = first + timedelta(days=(4 - first.weekday()) % 7)
    return first_friday + timedelta(days=14)


def _month_distance(later: date, earlier: date) -> int:
    return (later.year - earlier.year) * 12 + later.month - earlier.month


def formation_from_panel(panel: HistoricalOptionPanel) -> Decimal | UnknownReason:
    monthly: dict[int, MonthlyOptionReturn] = {}
    snapshots = panel.snapshots
    formation_anchor = panel.as_of.date()
    if (
        not snapshots
        or snapshots[-1].observed_at.date() != formation_anchor
        or formation_anchor != _third_friday(formation_anchor.year, formation_anchor.month)
    ):
        return UnknownReason("invalid_straddle_formation_calendar")
    for entry, exit_snapshot in zip(snapshots, snapshots[1:], strict=False):
        entry_day = entry.observed_at.date()
        exit_day = exit_snapshot.observed_at.date()
        if (
            entry_day != _third_friday(entry_day.year, entry_day.month)
            or exit_day != _third_friday(exit_day.year, exit_day.month)
            or _month_distance(exit_day, entry_day) != 1
        ):
            return UnknownReason("invalid_straddle_formation_calendar")
        pair = _select_pair(
            entry.contracts,
            require_open_interest=False,
            after_date=entry.observed_at.date(),
        )
        if isinstance(pair, UnknownReason):
            continue
        call, put = pair
        if call.expiration != exit_day or put.expiration != exit_day:
            return UnknownReason("invalid_straddle_holding_period")
        exit_by_identity = {contract.identity: contract for contract in exit_snapshot.contracts}
        exit_call = exit_by_identity.get(call.identity)
        exit_put = exit_by_identity.get(put.identity)
        call_mid = option_mid(call.bid, call.ask)
        put_mid = option_mid(put.bid, put.ask)
        exit_call_mid = option_mid(
            None if exit_call is None else exit_call.bid,
            None if exit_call is None else exit_call.ask,
        )
        exit_put_mid = option_mid(
            None if exit_put is None else exit_put.bid,
            None if exit_put is None else exit_put.ask,
        )
        if any(
            isinstance(item, UnknownReason)
            for item in (call_mid, put_mid, exit_call_mid, exit_put_mid)
        ):
            continue
        assert isinstance(call_mid, Decimal)
        assert isinstance(put_mid, Decimal)
        assert isinstance(exit_call_mid, Decimal)
        assert isinstance(exit_put_mid, Decimal)
        weights = zero_delta_straddle_weights(call_mid, put_mid, call.delta, put.delta)
        value = straddle_return(
            weights,
            (exit_call_mid - call_mid) / call_mid,
            (exit_put_mid - put_mid) / put_mid,
        )
        if isinstance(value, UnknownReason):
            continue
        lag = _month_distance(formation_anchor, entry_day)
        if 2 <= lag <= 12:
            monthly[lag] = MonthlyOptionReturn(
                entry_day.replace(day=1),
                value,
                panel.identity,
                f"{call.identity}|{put.identity}",
            )
    return straddle_momentum_formation(monthly)


def build_heston_knowledge_mapping(
    *,
    subject: str,
    snapshot_digest: str,
    panel_observation_id: str,
    panel: HistoricalOptionPanel,
    chain_observation_id: str,
    chain: OptionChain,
    selected_expiration: date,
    formation_date_state: str,
) -> KnowledgeMapping[HestonSubjectCandidate]:
    panel_fact_id = canonical_fact_id(FACT_PANEL, subject, snapshot_digest)
    requests = (
        CanonicalFactRequest(
            MarketCapability.HISTORICAL_OPTION_PANEL_V1,
            panel_observation_id,
            panel.identity,
            subject,
            FACT_PANEL,
        ),
        CanonicalFactRequest(
            MarketCapability.OPTION_CHAIN_V1,
            chain_observation_id,
            chain.identity,
            subject,
            FACT_CHAIN,
        ),
    )

    def _compute(facts: tuple[CanonicalFact, ...]) -> tuple[DerivedFactRequest, ...]:
        value = formation_from_panel(panel)
        if isinstance(value, UnknownReason):
            return ()
        return (
            DerivedFactRequest(
                STRADDLE_MOMENTUM_FORMATION,
                subject,
                value,
                "decimal",
                (EvidenceReference(EvidenceKind.CANONICAL_FACT, panel_fact_id, 1),),
                DerivedFactQualityStatus.VALID,
                (("formation_lags", "2-12"),),
            ),
        )

    def _payload(
        facts: tuple[CanonicalFact, ...], derived: DerivedFactSet
    ) -> HestonSubjectCandidate:
        by_type = {fact.fact_type: fact for fact in facts}
        formation = next(
            (
                item.value
                for item in derived.facts
                if item.derived_fact_id.startswith(f"{STRADDLE_MOMENTUM_FORMATION}:")
            ),
            UnknownReason("insufficient_straddle_return_history"),
        )
        if not isinstance(formation, (Decimal, UnknownReason)):
            raise TypeError("Heston formation fact must be decimal or unknown")
        return HestonSubjectCandidate(
            subject,
            by_type[FACT_PANEL].effective_time,
            "|".join(f"{fact.fact_id}@{fact.version}" for fact in facts),
            chain.contracts,
            selected_expiration,
            formation,
            formation_date_state,
        )

    return KnowledgeMapping(requests, _compute, _payload)
