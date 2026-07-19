from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class RunStatus(StrEnum):
    REQUESTED = "requested"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RunStepName(StrEnum):
    ACQUIRE_PORTFOLIO = "acquire_portfolio"
    NORMALIZE_PORTFOLIO = "normalize_portfolio"
    VALIDATE_PUBLICATION = "validate_publication"
    PUBLISH = "publish"


class RunStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RunStep:
    name: RunStepName
    status: RunStepStatus
    started_at: datetime | None
    completed_at: datetime | None
    failure_detail: str | None


@dataclass(frozen=True, slots=True)
class RunRecord:
    id: UUID
    status: RunStatus
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    release_sha: str
    effective_config_hash: str
    failure_code: str | None
    failure_detail: str | None
    steps: tuple[RunStep, ...]


@dataclass(frozen=True, slots=True)
class PublicationRecord:
    id: UUID
    run_id: UUID
    snapshot_id: UUID
    published_at: datetime


def validate_status_transition(current: RunStatus, target: RunStatus) -> None:
    allowed = {
        RunStatus.REQUESTED: {RunStatus.RUNNING, RunStatus.FAILED},
        RunStatus.RUNNING: {RunStatus.SUCCEEDED, RunStatus.FAILED},
        RunStatus.SUCCEEDED: set(),
        RunStatus.FAILED: set(),
    }
    if target not in allowed[current]:
        raise ValueError(f"invalid run status transition: {current} -> {target}")
