"""Immutable S001 target decision over an already-composed selection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Callable  # noqa: UP035

from analytics.cross_sectional_ranking import EligibilityState
from domain import CanonicalInstrumentIdentity
from strategies.tgsm_composition import S001Selection

S001_VERSION = "1.0.0"
SLEEVE_WEIGHT = (1, 3)
THREE_MONTH_TREASURY_TOTAL_RETURN = CanonicalInstrumentIdentity(
    "research_asset", "us_3_month_treasury_total_return"
)


@dataclass(frozen=True, slots=True)
class DefensiveAssetEvidence:
    instrument: CanonicalInstrumentIdentity
    total_return_fact_id: str
    effective_time: datetime

    def __post_init__(self) -> None:
        if self.instrument != THREE_MONTH_TREASURY_TOTAL_RETURN:
            raise ValueError("S001 defensive evidence must use the canonical research asset")
        if (
            not self.total_return_fact_id
            or self.total_return_fact_id != self.total_return_fact_id.strip()
        ):
            raise ValueError("defensive total-return fact identity is required")
        if self.effective_time.tzinfo is None or self.effective_time.utcoffset() is None:
            raise ValueError("defensive evidence effective time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class TargetSleeve:
    source_subject: CanonicalInstrumentIdentity
    target: CanonicalInstrumentIdentity
    weight: tuple[int, int]
    trend_state: EligibilityState
    evidence_fact_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class S001TargetDecision:
    decision_id: str
    strategy_id: str
    strategy_version: str
    decision_time: datetime
    effective_time: datetime
    ranking_id: str
    eligible_subjects: tuple[CanonicalInstrumentIdentity, ...]
    sleeves: tuple[TargetSleeve, ...]


def _decision_identity(decision: S001TargetDecision) -> str:
    payload = {
        "namespace": "asa.s001_target_decision",
        "version": "v1",
        "strategy_version": decision.strategy_version,
        "decision_time": decision.decision_time.isoformat(),
        "effective_time": decision.effective_time.isoformat(),
        "ranking_id": decision.ranking_id,
        "eligible": [(item.scheme, item.value) for item in decision.eligible_subjects],
        "sleeves": [
            {
                "source": (item.source_subject.scheme, item.source_subject.value),
                "target": (item.target.scheme, item.target.value),
                "weight": item.weight,
                "trend": item.trend_state.value,
                "evidence": item.evidence_fact_ids,
            }
            for item in decision.sleeves
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def serialize_s001_target_decision(decision: S001TargetDecision) -> str:
    """Canonical durable representation for provider-free replay."""
    payload = {
        "schema_version": "asa.s001_target_decision/v1",
        "decision_id": decision.decision_id,
        "strategy_id": decision.strategy_id,
        "strategy_version": decision.strategy_version,
        "decision_time": decision.decision_time.isoformat(),
        "effective_time": decision.effective_time.isoformat(),
        "ranking_id": decision.ranking_id,
        "eligible_subjects": [[item.scheme, item.value] for item in decision.eligible_subjects],
        "sleeves": [
            {
                "source": [item.source_subject.scheme, item.source_subject.value],
                "target": [item.target.scheme, item.target.value],
                "weight": list(item.weight),
                "trend_state": item.trend_state.value,
                "evidence_fact_ids": list(item.evidence_fact_ids),
            }
            for item in decision.sleeves
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def deserialize_s001_target_decision(payload: str) -> S001TargetDecision:
    """Restore and verify one immutable decision without provider access."""
    item = json.loads(payload)
    if item.get("schema_version") != "asa.s001_target_decision/v1":
        raise ValueError("unsupported S001 target decision schema")
    decision = S001TargetDecision(
        item["decision_id"],
        item["strategy_id"],
        item["strategy_version"],
        datetime.fromisoformat(item["decision_time"]),
        datetime.fromisoformat(item["effective_time"]),
        item["ranking_id"],
        tuple(CanonicalInstrumentIdentity(*value) for value in item["eligible_subjects"]),
        tuple(
            TargetSleeve(
                CanonicalInstrumentIdentity(*value["source"]),
                CanonicalInstrumentIdentity(*value["target"]),
                (int(value["weight"][0]), int(value["weight"][1])),
                EligibilityState(value["trend_state"]),
                tuple(value["evidence_fact_ids"]),
            )
            for value in item["sleeves"]
        ),
    )
    if _decision_identity(decision) != decision.decision_id:
        raise ValueError("S001 target decision identity does not match its contents")
    if serialize_s001_target_decision(decision) != payload:
        raise ValueError("S001 target decision serialization is not canonical")
    return decision


def build_s001_target_decision(
    selection: S001Selection,
    *,
    defensive_evidence: DefensiveAssetEvidence | None,
    next_eligible_session: Callable[[datetime], datetime],
) -> S001TargetDecision:
    """Create three fixed sleeves or fail closed on unavailable evidence."""
    if selection.unknown_reason is not None or selection.ranking is None:
        raise ValueError("S001 target decision requires a complete selection")
    if len(selection.selected) != 3:
        raise ValueError("S001 target decision requires exactly three selected sectors")
    if any(item.trend.state is EligibilityState.UNKNOWN for item in selection.selected):
        raise ValueError("S001 cannot allocate a sleeve with unknown trend evidence")
    if (
        any(item.trend.state is EligibilityState.FAIL for item in selection.selected)
        and defensive_evidence is None
    ):
        raise ValueError("failed S001 sleeves require canonical defensive evidence")
    if (
        defensive_evidence is not None
        and defensive_evidence.effective_time > selection.decision_time
    ):
        raise ValueError("defensive evidence cannot be known after the decision time")
    effective_time = next_eligible_session(selection.decision_time)
    if effective_time.tzinfo is None or effective_time.utcoffset() is None:
        raise ValueError("effective time must be timezone-aware")
    if effective_time <= selection.decision_time:
        raise ValueError("S001 decision must become effective after its evidence time")
    sleeves = tuple(
        TargetSleeve(
            source_subject=item.subject,
            target=(
                item.subject
                if item.trend.state is EligibilityState.PASS
                else THREE_MONTH_TREASURY_TOTAL_RETURN
            ),
            weight=SLEEVE_WEIGHT,
            trend_state=item.trend.state,
            evidence_fact_ids=tuple(
                fact_id
                for fact_id in (
                    item.return_fact_id,
                    item.trend.observation_fact_id,
                    item.trend.sma_fact_id,
                    defensive_evidence.total_return_fact_id
                    if item.trend.state is EligibilityState.FAIL and defensive_evidence is not None
                    else None,
                )
                if fact_id is not None
            ),
        )
        for item in selection.selected
    )
    provisional = S001TargetDecision(
        "pending",
        "S001",
        S001_VERSION,
        selection.decision_time,
        effective_time,
        selection.ranking.ranking_id,
        selection.eligible_subjects,
        sleeves,
    )
    return S001TargetDecision(
        _decision_identity(provisional),
        provisional.strategy_id,
        provisional.strategy_version,
        provisional.decision_time,
        provisional.effective_time,
        provisional.ranking_id,
        provisional.eligible_subjects,
        provisional.sleeves,
    )
