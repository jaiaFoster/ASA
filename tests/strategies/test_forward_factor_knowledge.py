from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

from domain import (
    CanonicalFact,
    Confidence,
    EvidenceKind,
    EvidenceReference,
    ExpirationCycle,
    OptionChain,
    Provenance,
    UnknownReason,
)
from facts.canonical_projection import canonical_fact_id
from strategies.forward_factor_knowledge import build_forward_factor_knowledge_mapping

NOW = datetime(2026, 8, 18, 17, 0, tzinfo=UTC)
AS_OF = NOW.date()
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "option-chain-observation"),)


def _cycle(days: int) -> ExpirationCycle:
    return ExpirationCycle(
        date.fromordinal(AS_OF.toordinal() + days), days, monthly=True, weekly=False,
        as_of=AS_OF, evidence=EVIDENCE,
    )


def _fact(fact_id: str, fact_type: str, value: object) -> CanonicalFact:
    return CanonicalFact(
        fact_id,
        1,
        fact_type,
        value,
        Confidence(1.0),
        Provenance(("observation",), ("provider",), "provider", (), NOW),
        NOW,
        NOW,
    )


def test_non_positive_forward_variance_becomes_specific_typed_unknown() -> None:
    digest = "snapshot-digest"
    mapping = build_forward_factor_knowledge_mapping(
        subject="UDR",
        snapshot_digest=digest,
        quote_observation_id="quote-observation",
        chain_observation_id="option-chain-observation",
        earnings_observation_id=None,
        spot_price=Decimal("40"),
        chain=cast(OptionChain, object()),
        front_cycle=_cycle(30),
        back_cycle=_cycle(60),
        front_strike=Decimal("40"),
        back_strike=Decimal("40"),
        front_iv=Decimal("0.50"),
        back_iv=Decimal("0.20"),
        event=None,
        as_of=AS_OF,
    )
    facts = tuple(
        _fact(
            canonical_fact_id(request.fact_type, request.subject, digest),
            request.fact_type,
            request.value,
        )
        for request in mapping.canonical_fact_requests
    )

    result = mapping.compute_derived_fact_requests(facts)

    assert result == UnknownReason("non_positive_forward_variance")
