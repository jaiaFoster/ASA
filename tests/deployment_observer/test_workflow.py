from pathlib import Path

import yaml

WORKFLOW_PATH = Path(".github/workflows/railway-deployment-observer.yml")
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


def workflow() -> dict[object, object]:
    return yaml.safe_load(WORKFLOW_PATH.read_text())


def test_workflow_has_contents_read_only() -> None:
    assert workflow()["permissions"] == {"contents": "read"}


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
    assert uploads[0]["with"]["path"] == ".artifacts/railway-deployment"


def test_workflow_is_production_only_and_cli_is_pinned() -> None:
    text = WORKFLOW_PATH.read_text()
    assert "github.event.deployment.environment == 'production'" in text
    assert "@railway/cli@5.27.0" in text
    assert "RAILWAY_ENVIRONMENT: production" in text


def test_workflow_has_required_triggers_and_manual_inputs() -> None:
    text = WORKFLOW_PATH.read_text()
    assert "  deployment_status:" in text
    assert "  workflow_dispatch:" in text
    assert "      deployment_id:" in text
    assert "      include_runtime_logs:" in text
    assert "        default: true" in text
