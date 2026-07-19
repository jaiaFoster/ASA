from datetime import datetime
from typing import Protocol
from uuid import UUID

from asa.domain.runs import PublicationRecord, RunRecord, RunStepName


class RunPublicationRepository(Protocol):
    def create_run(
        self,
        requested_at: datetime,
        release_sha: str,
        effective_config_hash: str,
    ) -> RunRecord: ...

    def start_run(self, run_id: UUID, started_at: datetime) -> None: ...

    def start_step(self, run_id: UUID, step: RunStepName, started_at: datetime) -> None: ...

    def complete_step(self, run_id: UUID, step: RunStepName, completed_at: datetime) -> None: ...

    def fail_run(
        self,
        run_id: UUID,
        failed_step: RunStepName,
        completed_at: datetime,
        failure_code: str,
        failure_detail: str,
    ) -> None: ...

    def get_run(self, run_id: UUID) -> RunRecord | None: ...

    def latest_run(self) -> RunRecord | None: ...

    def current_publication(self) -> PublicationRecord | None: ...

    def publish_snapshot(
        self,
        run_id: UUID,
        observed_at: datetime,
        provider: str,
        provider_request_id: str,
        published_at: datetime,
    ) -> PublicationRecord: ...
