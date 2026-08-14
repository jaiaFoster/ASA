"""Provider-free materialization of reusable cross-subject return facts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from analytics.derived_fact_materialization import materialize_derived_fact
from analytics.derived_facts import (
    CROSS_SECTIONAL_MOMENTUM,
    DERIVED_FACT_REGISTRY,
    SECTOR_RELATIVE_MOMENTUM,
    compute_cross_sectional_momentum,
    compute_sector_relative_momentum,
)
from analytics.features import DerivedFact, DerivedFactQualityStatus, DerivedFactSet
from domain import (
    CanonicalInstrumentIdentity,
    CanonicalReturnObservation,
    ComparisonUniverseReturns,
    EvidenceReference,
    SectorReferenceReturns,
)


@dataclass(frozen=True, slots=True)
class CrossSectionalFactInputs:
    """Explicit domain evidence selected by the policy-owning caller."""

    subject_return: CanonicalReturnObservation
    comparison_returns: ComparisonUniverseReturns | None
    sector_returns: SectorReferenceReturns | None
    comparison_unknown_reason: str | None = None
    sector_unknown_reason: str | None = None

    def __post_init__(self) -> None:
        if self.comparison_returns is None and self.comparison_unknown_reason is None:
            raise ValueError("missing comparison evidence requires a typed reason")
        if self.sector_returns is None and self.sector_unknown_reason is None:
            raise ValueError("missing sector evidence requires a typed reason")


@dataclass(frozen=True, slots=True)
class SubjectCrossSectionalFacts:
    """Facts and explicit gaps for one subject in one immutable cohort."""

    subject: CanonicalInstrumentIdentity
    derived_facts: DerivedFactSet
    comparison_peer_count: int
    comparison_unknown_reason: str | None = None
    sector_unknown_reason: str | None = None


def _instrument_key(instrument: CanonicalInstrumentIdentity) -> tuple[str, str]:
    return instrument.scheme, instrument.value


def _evidence(
    observations: tuple[CanonicalReturnObservation, ...],
) -> tuple[EvidenceReference, ...]:
    return tuple(
        sorted(
            {item for observation in observations for item in observation.evidence},
            key=lambda item: (item.kind.value, item.referenced_id, item.version or 0),
        )
    )


def _evidence_digest(
    feature_id: str,
    subject: CanonicalInstrumentIdentity,
    observations: tuple[CanonicalReturnObservation, ...],
) -> str:
    """Content identity for the exact ordered cross-subject evidence set."""

    payload = {
        "namespace": "asa.cross_sectional_evidence",
        "version": "v1",
        "feature_id": feature_id,
        "subject": _instrument_key(subject),
        "observations": [
            {
                "instrument": _instrument_key(item.instrument),
                "return": str(item.return_value),
                "period_start": item.period_start.isoformat(),
                "period_end": item.period_end.isoformat(),
                "effective_time": item.effective_time.isoformat(),
                "evidence": [
                    (reference.kind.value, reference.referenced_id, reference.version)
                    for reference in item.evidence
                ],
            }
            for item in sorted(observations, key=lambda value: _instrument_key(value.instrument))
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def materialize_cross_sectional_facts(
    inputs: tuple[CrossSectionalFactInputs, ...],
    *,
    effective_time: datetime,
    minimum_valid_members: int = 5,
) -> tuple[SubjectCrossSectionalFacts, ...]:
    """Materialize registered facts once from already-canonical returns.

    This function performs no acquisition and owns no strategy policy. Missing
    cohort or sector-reference evidence remains explicitly typed by reason.
    """

    by_instrument = {item.subject_return.instrument: item for item in inputs}
    if len(by_instrument) != len(inputs):
        raise ValueError("cross-sectional inputs must contain unique subjects")
    results: list[SubjectCrossSectionalFacts] = []
    for subject in sorted(by_instrument, key=_instrument_key):
        selected = by_instrument[subject]
        subject_return = selected.subject_return
        comparison = selected.comparison_returns
        facts: list[DerivedFact] = []
        comparison_reason = selected.comparison_unknown_reason
        comparison_peer_count = 0
        if comparison is not None:
            comparison_peer_count = len(comparison.returns)
            evidence_inputs = (subject_return, *comparison.returns)
            facts.append(
                materialize_derived_fact(
                    DERIVED_FACT_REGISTRY,
                    CROSS_SECTIONAL_MOMENTUM,
                    subject.value,
                    _evidence_digest(CROSS_SECTIONAL_MOMENTUM, subject, evidence_inputs),
                    value=compute_cross_sectional_momentum(subject_return.return_value, comparison),
                    unit="percentile",
                    effective_time=effective_time,
                    input_evidence=_evidence(evidence_inputs),
                    quality_status=DerivedFactQualityStatus.VALID,
                    parameters=(("minimum_valid_members", str(minimum_valid_members)),),
                )
            )

        sector_reference = selected.sector_returns
        sector_reason = selected.sector_unknown_reason
        if sector_reference is not None:
            evidence_inputs = (subject_return, *sector_reference.returns)
            facts.append(
                materialize_derived_fact(
                    DERIVED_FACT_REGISTRY,
                    SECTOR_RELATIVE_MOMENTUM,
                    subject.value,
                    _evidence_digest(SECTOR_RELATIVE_MOMENTUM, subject, evidence_inputs),
                    value=compute_sector_relative_momentum(
                        subject_return.return_value, sector_reference
                    ),
                    unit="decimal_return",
                    effective_time=effective_time,
                    input_evidence=_evidence(evidence_inputs),
                    quality_status=DerivedFactQualityStatus.VALID,
                    parameters=(("sector_id", sector_reference.sector_id),),
                )
            )
        results.append(
            SubjectCrossSectionalFacts(
                subject,
                DerivedFactSet(tuple(facts)),
                comparison_peer_count,
                comparison_reason,
                sector_reason,
            )
        )
    return tuple(results)
