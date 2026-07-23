from datetime import UTC, datetime

import pytest

from asa.contracts.runs import RunStatus, validate_status_transition


def test_run_status_transitions_are_explicit() -> None:
    validate_status_transition(RunStatus.REQUESTED, RunStatus.RUNNING)
    validate_status_transition(RunStatus.RUNNING, RunStatus.SUCCEEDED)
    with pytest.raises(ValueError):
        validate_status_transition(RunStatus.SUCCEEDED, RunStatus.RUNNING)


def test_run_terminal_timestamp_contract() -> None:
    now = datetime.now(UTC)
    assert now.tzinfo is UTC
