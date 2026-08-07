"""Canonical Fact projection from Market Data resolution (SPRINT-014
S14-PR-04).

ASA-ARCH-007's Observation Resolution layer (market_data/resolution.py)
already plays the same conceptual role reconciliation/engine.py's
reconcile() does for the older Observation/CanonicalFact pipeline -- select
one reported value, or remain unresolved -- but over MarketObservation, a
different (and newer, frozen) input type reconcile() does not accept. This
module is a direct bridge from that resolution's own output into
CanonicalFact, the one canonical fact type the whole system already shares
(domain/canonical_fact.py) -- not a second reconciliation engine, not a
parallel fact type.

Field-level FieldDisagreement records (market_data/resolution.py) do not
share ProviderDisagreement's shape (one reported value per contributing
provider, not per field), so a genuine disagreement's field paths are
recorded in Provenance.reconciliation_metadata instead of being force-fit
into a mismatched type -- that field already exists for exactly this kind
of extra reconciliation context.

The projected value is always whatever the caller's own ``value`` argument
supplies -- a specific normalized scalar already extracted from the
resolved observation (a spot price, an earnings date, an implied
volatility), never the raw MarketObservation object itself. Extracting
which scalar a fact represents from which observation type is a strategy-
or-consumer-level decision (ADR-001's own one-fact-per-data-point design);
this module owns only the generic CanonicalFact construction and the
UNRESOLVED -> None (explicit UNKNOWN) rule, not field extraction.
"""

from __future__ import annotations

from datetime import datetime

from domain.canonical_fact import CanonicalFact
from domain.provenance import Provenance
from domain.references import Confidence
from domain.values import DomainInvariantError, require_tz_aware
from market_data.resolution import ConfidenceClassification, ResolutionMethod, ResolutionResult

_CONFIDENCE_SCORE_BY_CLASSIFICATION = {
    ConfidenceClassification.EXACT_AGREEMENT: 1.0,
    ConfidenceClassification.SINGLE_SOURCE: 0.75,
    ConfidenceClassification.DISAGREEMENT: 0.5,
    ConfidenceClassification.INSUFFICIENT_QUALITY: 0.0,
}


def canonical_fact_id(fact_type: str, subject: str, snapshot_digest: str) -> str:
    """Deterministic identity for one projected canonical fact (SPRINT-014
    S14-PR-05A, Architect checkpoint: sixth review, "canonical fact IDs are
    strategy-owned" -- they are not; a fact's identity is a function of
    what it represents (fact_type), which subject it is about, and which
    sealed evidence it was projected from (snapshot_digest), never of
    which strategy happened to be the caller that projected it. Mirrors
    analytics.derived_fact_materialization.derived_fact_id()'s own exact
    shape and argument order -- the two identity schemes are siblings.

    Two different consumers projecting the same fact_type for the same
    subject from the same sealed snapshot always receive the same ID, so
    a later consumer can detect and reuse an already-projected fact
    instead of silently duplicating it under a strategy-scoped name.
    """
    return f"{fact_type}:{subject}:{snapshot_digest}"


def project_canonical_fact(
    resolution: ResolutionResult,
    *,
    value: object,
    fact_id: str,
    version: int,
    fact_type: str,
    created_time: datetime,
) -> CanonicalFact | None:
    """Project one resolved capability's ResolutionResult into a
    CanonicalFact carrying ``value``. Returns None when the resolution is
    UNRESOLVED -- an explicit UNKNOWN, never a fabricated fact for missing
    or insufficient-quality evidence.
    """
    require_tz_aware(created_time, "project_canonical_fact", "created_time")
    if resolution.method is ResolutionMethod.UNRESOLVED or resolution.selected_observation is None:
        return None
    if not resolution.consumed_observation_ids:
        raise DomainInvariantError("project_canonical_fact requires consumed observation evidence")
    selected = resolution.selected_observation
    field_disagreement_metadata = tuple(
        (
            f"field_disagreement:{item.field_path}",
            ",".join(f"{provider}={reported}" for provider, reported in item.values_by_provider),
        )
        for item in resolution.disagreements
    )
    metadata = tuple(
        sorted(
            (
                ("policy_version", resolution.policy_version),
                ("resolution_method", resolution.method.value),
                ("field_disagreement_count", str(len(resolution.disagreements))),
                *field_disagreement_metadata,
            )
        )
    )
    provenance = Provenance(
        contributing_observation_ids=resolution.consumed_observation_ids,
        contributing_provider_ids=resolution.contributors,
        selected_provider_id=selected.provenance.provider_id,
        disagreements=(),
        reconciled_at=created_time,
        reconciliation_metadata=metadata,
    )
    confidence_score = _CONFIDENCE_SCORE_BY_CLASSIFICATION[resolution.confidence.classification]
    confidence = Confidence(confidence_score)
    return CanonicalFact(
        fact_id=fact_id,
        version=version,
        fact_type=fact_type,
        value=value,
        confidence=confidence,
        provenance=provenance,
        effective_time=selected.effective_time,
        created_time=created_time,
    )
