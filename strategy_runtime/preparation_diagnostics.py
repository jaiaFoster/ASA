"""Secret-free operational classification for subject preparation failures."""

from __future__ import annotations

import logging

from domain import UnknownReason

_LOGGER = logging.getLogger(__name__)


def classify_subject_preparation_exception(exc: BaseException) -> str:
    message = str(exc).lower()
    if "capability_reducer" in message or "demands resolved to" in message:
        return "capability_reduction_failure"
    if "resolution policy" in message or "priority policy" in message:
        return "resolution_policy_construction_failure"
    if "snapshot" in message or "seal" in message:
        return "snapshot_sealing_failure"
    if "provenance" in message:
        return "provenance_mismatch"
    if "fact" in message and ("identity" in message or "version" in message):
        return "fact_identity_version_failure"
    if "demand" in message:
        return "demand_construction_failure"
    if "provider" in message and ("config" in message or "enabled" in message):
        return "provider_config_construction_failure"
    return "unexpected_runtime_exception"


def record_strategy_knowledge_failure(
    strategy_id: str, subject: str
) -> UnknownReason:
    _LOGGER.exception(
        "strategy_knowledge_construction_failed",
        extra={
            "failure_class": "strategy_knowledge_construction_failure",
            "strategy_id": strategy_id,
            "subject": subject,
        },
    )
    return UnknownReason("strategy_knowledge_construction_failed")
