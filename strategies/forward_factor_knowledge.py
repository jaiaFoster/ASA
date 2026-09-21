"""Forward Factor mapping from sealed evidence to immutable facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from analytics.derived_fact_materialization import derived_fact_id
from analytics.derived_facts import (
    FORWARD_FACTOR,
    IMPLIED_FORWARD_VOLATILITY,
    NO_CONFIRMED_EARNINGS_THROUGH_EXPIRATION,
    compute_forward_factor,
    compute_implied_forward_volatility,
    compute_no_confirmed_earnings_through_expiration,
)
from analytics.features import DerivedFactQualityStatus, DerivedFactRequest, DerivedFactSet
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
from strategies.knowledge_contracts import KnowledgeMapping

FACT_SPOT = "spot_price"
FACT_OPTION_IV = "option_implied_volatility"
FACT_EARNINGS_DATE = "earnings_date"
FACT_EARNINGS_CONFIRMED = "earnings_confirmed"
_FACT_VERSION = 1


class EarningsClearanceStatus(StrEnum):
    CONFIRMED_OUTSIDE_WINDOW = "confirmed_outside_window"
    CONFIRMED_INSIDE_WINDOW = "confirmed_inside_window"
    UNKNOWN_UNCONFIRMED = "unknown_unconfirmed"
    STALE_UNUSABLE = "stale_unusable"


def classify_earnings_clearance(
    event: EarningsEvent | None,
    *,
    as_of: date,
    back_expiration: date,
) -> EarningsClearanceStatus:
    if event is None or not event.confirmed:
        return EarningsClearanceStatus.UNKNOWN_UNCONFIRMED
    eligible = compute_no_confirmed_earnings_through_expiration(
        confirmed=True,
        earnings_date=event.earnings_date,
        as_of=as_of,
        back_expiration=back_expiration,
    )
    return (
        EarningsClearanceStatus.CONFIRMED_OUTSIDE_WINDOW
        if eligible
        else EarningsClearanceStatus.CONFIRMED_INSIDE_WINDOW
    )


@dataclass(frozen=True, slots=True)
class ForwardFactorPayload:
    chain: OptionChain
    front_cycle: ExpirationCycle
    back_cycle: ExpirationCycle
    front_strike: Decimal
    back_strike: Decimal
    front_implied_volatility: Decimal
    back_implied_volatility: Decimal
    as_of: date
    earnings_eligible: bool
    confirmed_earnings_date: date | None
    earnings_clearance_status: EarningsClearanceStatus
    front_iv_fact_id: str
    back_iv_fact_id: str
    implied_forward_fact_id: str
    forward_factor_fact_id: str


def build_forward_factor_knowledge_mapping(
    *,
    subject: str,
    snapshot_digest: str,
    quote_observation_id: str,
    chain_observation_id: str,
    earnings_observation_id: str | None,
    spot_price: Decimal,
    chain: OptionChain,
    front_cycle: ExpirationCycle,
    back_cycle: ExpirationCycle,
    front_strike: Decimal,
    back_strike: Decimal,
    front_iv: Decimal,
    back_iv: Decimal,
    event: EarningsEvent | None,
    as_of: date,
    earnings_clearance_status: EarningsClearanceStatus | None = None,
) -> KnowledgeMapping[ForwardFactorPayload]:
    front_subject = f"{subject}:{front_cycle.expiration_date.isoformat()}:{front_strike}:call"
    back_subject = f"{subject}:{back_cycle.expiration_date.isoformat()}:{back_strike}:call"
    requests = [
        CanonicalFactRequest(
            MarketCapability.REAL_TIME_QUOTE_V1,
            quote_observation_id,
            spot_price,
            subject,
            FACT_SPOT,
        ),
        CanonicalFactRequest(
            MarketCapability.OPTION_CHAIN_V1,
            chain_observation_id,
            front_iv,
            front_subject,
            FACT_OPTION_IV,
        ),
        CanonicalFactRequest(
            MarketCapability.OPTION_CHAIN_V1,
            chain_observation_id,
            back_iv,
            back_subject,
            FACT_OPTION_IV,
        ),
    ]
    if event is not None and earnings_observation_id is not None:
        requests.extend(
            (
                CanonicalFactRequest(
                    MarketCapability.EARNINGS_CALENDAR_V1,
                    earnings_observation_id,
                    event.earnings_date.isoformat(),
                    subject,
                    FACT_EARNINGS_DATE,
                ),
                CanonicalFactRequest(
                    MarketCapability.EARNINGS_CALENDAR_V1,
                    earnings_observation_id,
                    event.confirmed,
                    subject,
                    FACT_EARNINGS_CONFIRMED,
                ),
            )
        )

    front_fact_id = canonical_fact_id(FACT_OPTION_IV, front_subject, snapshot_digest)
    back_fact_id = canonical_fact_id(FACT_OPTION_IV, back_subject, snapshot_digest)
    selection_parameters = (
        ("front_expiration", front_cycle.expiration_date.isoformat()),
        ("back_expiration", back_cycle.expiration_date.isoformat()),
        ("front_strike", str(front_strike)),
        ("back_strike", str(back_strike)),
    )
    implied_id = derived_fact_id(
        IMPLIED_FORWARD_VOLATILITY,
        subject,
        snapshot_digest,
        parameters=selection_parameters,
    )
    factor_id = derived_fact_id(
        FORWARD_FACTOR, subject, snapshot_digest, parameters=selection_parameters
    )

    def _compute(
        facts: tuple[CanonicalFact, ...],
    ) -> tuple[DerivedFactRequest, ...] | UnknownReason:
        front_fact = next(item for item in facts if item.fact_id == front_fact_id)
        back_fact = next(item for item in facts if item.fact_id == back_fact_id)
        assert isinstance(front_fact.value, Decimal)
        assert isinstance(back_fact.value, Decimal)
        evidence = (
            EvidenceReference(EvidenceKind.CANONICAL_FACT, front_fact.fact_id, _FACT_VERSION),
            EvidenceReference(EvidenceKind.CANONICAL_FACT, back_fact.fact_id, _FACT_VERSION),
        )
        try:
            implied = compute_implied_forward_volatility(
                front_fact.value,
                back_fact.value,
                front_cycle.days_to_expiration,
                back_cycle.days_to_expiration,
            )
        except ValueError as exc:
            if str(exc) != "forward variance must be positive":
                raise
            return UnknownReason("non_positive_forward_variance")
        result = [
            DerivedFactRequest(
                IMPLIED_FORWARD_VOLATILITY,
                subject,
                implied,
                "decimal",
                evidence,
                DerivedFactQualityStatus.VALID,
                selection_parameters,
            ),
            DerivedFactRequest(
                FORWARD_FACTOR,
                subject,
                compute_forward_factor(front_fact.value, implied),
                "decimal",
                evidence,
                DerivedFactQualityStatus.VALID,
                selection_parameters,
            ),
        ]
        if event is not None:
            earnings_fact = next(item for item in facts if item.fact_type == FACT_EARNINGS_DATE)
            confirmed_fact = next(
                item for item in facts if item.fact_type == FACT_EARNINGS_CONFIRMED
            )
            earnings_evidence = (
                EvidenceReference(
                    EvidenceKind.CANONICAL_FACT, earnings_fact.fact_id, _FACT_VERSION
                ),
                EvidenceReference(
                    EvidenceKind.CANONICAL_FACT, confirmed_fact.fact_id, _FACT_VERSION
                ),
            )
            assert isinstance(earnings_fact.value, str)
            assert isinstance(confirmed_fact.value, bool)
            result.append(
                DerivedFactRequest(
                    NO_CONFIRMED_EARNINGS_THROUGH_EXPIRATION,
                    subject,
                    compute_no_confirmed_earnings_through_expiration(
                        confirmed=confirmed_fact.value,
                        earnings_date=date.fromisoformat(earnings_fact.value),
                        as_of=as_of,
                        back_expiration=back_cycle.expiration_date,
                    ),
                    "boolean",
                    earnings_evidence,
                    DerivedFactQualityStatus.VALID,
                    (("back_expiration", back_cycle.expiration_date.isoformat()),),
                )
            )
        return tuple(result)

    def _payload(facts: tuple[CanonicalFact, ...], derived: DerivedFactSet) -> ForwardFactorPayload:
        front_value = next(item for item in facts if item.fact_id == front_fact_id).value
        back_value = next(item for item in facts if item.fact_id == back_fact_id).value
        assert isinstance(front_value, Decimal)
        assert isinstance(back_value, Decimal)
        earnings_eligible = True
        if event is not None:
            eligibility_id = derived_fact_id(
                NO_CONFIRMED_EARNINGS_THROUGH_EXPIRATION,
                subject,
                snapshot_digest,
                parameters=(("back_expiration", back_cycle.expiration_date.isoformat()),),
            )
            value = derived.get(eligibility_id).value
            assert isinstance(value, bool)
            earnings_eligible = value
        clearance = earnings_clearance_status or classify_earnings_clearance(
            event,
            as_of=as_of,
            back_expiration=back_cycle.expiration_date,
        )
        return ForwardFactorPayload(
            chain=chain,
            front_cycle=front_cycle,
            back_cycle=back_cycle,
            front_strike=front_strike,
            back_strike=back_strike,
            front_implied_volatility=front_value,
            back_implied_volatility=back_value,
            as_of=as_of,
            earnings_eligible=earnings_eligible,
            confirmed_earnings_date=(
                event.earnings_date if event is not None and event.confirmed else None
            ),
            earnings_clearance_status=clearance,
            front_iv_fact_id=front_fact_id,
            back_iv_fact_id=back_fact_id,
            implied_forward_fact_id=implied_id,
            forward_factor_fact_id=factor_id,
        )

    return KnowledgeMapping(tuple(requests), _compute, _payload)
