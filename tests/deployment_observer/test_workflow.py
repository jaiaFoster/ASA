from pathlib import Path
from typing import Any, cast

import pytest
import yaml  # type: ignore[import-untyped]

WORKFLOW_PATH = (
    Path(__file__).parents[2] / ".github" / "workflows" / "railway-deployment-observer.yml"
)
FORBIDDEN_MUTATIONS = (
    "railway up",
    "redeploy",
    "restart",
    "rollback",
    "railway variable",
    "railway environment",
    "railway service",
    "graphql",
)


def workflow() -> dict[str, Any]:
    parsed: object = yaml.safe_load(WORKFLOW_PATH.read_text())
    assert isinstance(parsed, dict)
    return cast(dict[str, Any], parsed)


def test_workflow_has_minimum_comment_permissions() -> None:
    assert workflow()["permissions"] == {"contents": "read", "pull-requests": "write"}


def test_workflow_never_uses_pull_request_target() -> None:
    data = workflow()
    assert "pull_request_target" not in data.get("on", {})


def test_workflow_never_prints_secrets() -> None:
    text = WORKFLOW_PATH.read_text().lower()
    assert "echo $railway_token" not in text
    assert "printenv" not in text


def test_workflow_contains_no_railway_mutation() -> None:
    text = WORKFLOW_PATH.read_text().lower()
    for command in FORBIDDEN_MUTATIONS:
        assert command not in text


def test_workflow_uploads_only_observer_artifact_directory() -> None:
    steps = workflow()["jobs"]["observe"]["steps"]
    uploads = [step for step in steps if step.get("uses", "").startswith("actions/upload-artifact@")]
    assert len(uploads) == 1
    assert uploads[0]["if"] == "always()"
    assert uploads[0]["with"]["path"] == ".artifacts/railway-deployment"


def test_comment_publication_and_artifact_are_independent_channels() -> None:
    steps = workflow()["jobs"]["observe"]["steps"]
    publish = next(step for step in steps if step.get("id") == "publish")
    artifact = next(step for step in steps if step.get("id") == "artifact")
    outcome = next(step for step in steps if step.get("name") == "Report observer channel outcomes")
    assert publish["if"] == "always()"
    assert artifact["if"] == "always()"
    assert steps.index(publish) < steps.index(artifact)
    assert outcome["if"] == "always()"
    assert "steps.publish.outcome" in outcome["env"]["COMMENT_OUTCOME"]
    assert "steps.artifact.outcome" in outcome["env"]["ARTIFACT_OUTCOME"]


def test_workflow_cli_context_is_explicit_and_pinned() -> None:
    text = WORKFLOW_PATH.read_text()
    assert "@railway/cli@5.27.0" in text
    assert "RAILWAY_ENVIRONMENT: production" in text


@pytest.mark.parametrize(
    ("event_name", "deployment_environment"),
    [
        ("workflow_dispatch", None),
        ("deployment_status", "production"),
        ("deployment_status", "Production"),
        ("deployment_status", None),
    ],
)
def test_observe_job_has_no_external_metadata_gate(
    event_name: str,
    deployment_environment: str | None,
) -> None:
    assert event_name in {"workflow_dispatch", "deployment_status"}
    assert deployment_environment in {None, "production", "Production"}
    assert "if" not in workflow()["jobs"]["observe"]


def test_workflow_has_required_triggers_and_manual_inputs() -> None:
    text = WORKFLOW_PATH.read_text()
    assert "  deployment_status:" in text
    assert "  workflow_dispatch:" in text
    assert "      deployment_id:" in text
    assert "      include_runtime_logs:" in text
    assert "        default: true" in text


def test_workflow_does_not_serialize_complete_event_payload() -> None:
    text = WORKFLOW_PATH.read_text().lower()
    assert "tojson(github.event)" not in text
    assert "tojson(github)" not in text
