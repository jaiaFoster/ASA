"""Reconciliation module (ASA-CORE-003).

Owns deterministic Observation-to-Canonical-Fact reconciliation: grouping,
value resolution, disagreement detection, confidence, and fact identity.
Pure — no repository access, no I/O, no randomness, no machine learning, no
provider weighting (see ``reconciliation/rules.py`` for the documented v1
policy). ``facts/`` owns storage/versioning orchestration and depends on
this module; this module never depends on ``facts/``.

Pipeline position (ADR-004, amended by ASA-CORE-003): sits between
``observation/`` and ``facts/`` — may depend on reconciliation, observation,
providers, and domain; nothing above may import this module except facts/
and layers already permitted to depend on facts/.
"""
from reconciliation.engine import reconcile
from reconciliation.errors import (
    EmptyObservationGroupError,
    InconsistentGroupError,
    ReconciliationError,
)
from reconciliation.rules import (
    FACT_IDENTITY_NAMESPACE,
    FACT_IDENTITY_VERSION,
    fact_identity,
    group_by_fact_identity,
)

__all__ = [
    "EmptyObservationGroupError",
    "FACT_IDENTITY_NAMESPACE",
    "FACT_IDENTITY_VERSION",
    "InconsistentGroupError",
    "ReconciliationError",
    "fact_identity",
    "group_by_fact_identity",
    "reconcile",
]
