"""Immutable canonical/derived knowledge mapping for Heston SP-05D."""

from datetime import date, datetime
from decimal import Decimal

from analytics.calendar_facts import TradingCalendarView, monthly_expiration_day, new_york_time
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
    UnknownReason,
)
from facts.canonical_projection import CanonicalFactRequest, canonical_fact_id
from strategies.heston_portfolio import HestonSubjectCandidate
from strategies.heston_selection import select_heston_pair
from strategies.knowledge_contracts import KnowledgeMapping

FACT_PANEL = "historical_option_panel_identity"
FACT_CHAIN = "option_chain_identity"


def _local_date(value: datetime) -> date:
    return new_york_time(value).date()


def _is_monthly_expiration(calendar: TradingCalendarView, day: date) -> bool:
    return monthly_expiration_day(calendar, day.year, day.month) == day


def _month_distance(later: date, earlier: date) -> int:
    return (later.year - earlier.year) * 12 + later.month - earlier.month


def formation_from_panel(
    panel: HistoricalOptionPanel, calendar: TradingCalendarView, formation_date: date
) -> Decimal | UnknownReason:
    """A17 over A08: straddle returns keyed by exact monthly-expiration anchors.

    Each monthly return is held from one monthly expiration (DF-MONTHLY-
    EXPIRATION-DAY, holiday-adjusted) to the next, in the pair expiring at the
    exit date. Weekly expirations are never held. Lag 1 is skipped; lags 2-12
    must all be present or the formation is UNKNOWN. Lags are anchored to the
    current `formation_date`; a panel that ends on an earlier expiration is
    stale and typed UNKNOWN, never re-labelled as lags 2-12.
    """
    monthly: dict[int, MonthlyOptionReturn] = {}
    snapshots = panel.snapshots
    formation_anchor = _local_date(panel.as_of)
    if formation_anchor != formation_date:
        return UnknownReason("stale_straddle_formation_history")
    if (
        not snapshots
        or _local_date(snapshots[-1].observed_at) != formation_anchor
        or not _is_monthly_expiration(calendar, formation_anchor)
    ):
        return UnknownReason("invalid_straddle_formation_calendar")
    for entry, exit_snapshot in zip(snapshots, snapshots[1:], strict=False):
        entry_day = _local_date(entry.observed_at)
        exit_day = _local_date(exit_snapshot.observed_at)
        if (
            not _is_monthly_expiration(calendar, entry_day)
            or not _is_monthly_expiration(calendar, exit_day)
            or _month_distance(exit_day, entry_day) != 1
        ):
            return UnknownReason("invalid_straddle_formation_calendar")
        pair = select_heston_pair(
            entry.contracts,
            expiration=exit_day,
            require_open_interest=False,
            apply_spread_screen=False,
        )
        if isinstance(pair, UnknownReason):
            continue
        call, put = pair.call, pair.put
        if call.expiration != exit_day or put.expiration != exit_day:
            return UnknownReason("invalid_straddle_holding_period")
        exit_by_identity = {contract.identity: contract for contract in exit_snapshot.contracts}
        exit_call = exit_by_identity.get(call.identity)
        exit_put = exit_by_identity.get(put.identity)
        call_mid, put_mid = pair.call_mid, pair.put_mid
        exit_call_mid = option_mid(
            None if exit_call is None else exit_call.bid,
            None if exit_call is None else exit_call.ask,
        )
        exit_put_mid = option_mid(
            None if exit_put is None else exit_put.bid,
            None if exit_put is None else exit_put.ask,
        )
        if isinstance(exit_call_mid, UnknownReason) or isinstance(exit_put_mid, UnknownReason):
            continue
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
    calendar: TradingCalendarView,
    formation_date: date,
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
        value = formation_from_panel(panel, calendar, formation_date)
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
