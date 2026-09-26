"""ROLE-RESEARCH and Research Sprint Delegation regression suite (GOV-AMD-001 Amendment 017).

This is the versioned RES-002 §21 suite for ROLE-RESEARCH RoleSpec v1.0.0.
It holds both the positive and the negative authority cases that
GOV-RESEARCHER-001 requires.
"""

from __future__ import annotations

import copy
import re
import shutil
from pathlib import Path

import pytest
import yaml

from tools.pos.lean.research_delegation import (
    REQUIRED_GATES,
    evaluate_merge,
    validate_activation,
)
from tools.pos.lean.research_delegation import (
    main as delegation_main,
)
from tools.pos.lean.research_library import validate_library

REPO_ROOT = Path(__file__).resolve().parents[3]
AMENDMENT = (REPO_ROOT / "governance/amendments/GOV-AMD-017.md").read_text()
BOUNDARIES = (REPO_ROOT / "roles/shared/AUTHORITY_BOUNDARIES.md").read_text()

ACTIVE_SPRINT = {
    "sprint_id": "ASA-RES-SPRINT-TEST",
    "sprint_type": "research",
    "governance_amendment": "GOV-AMD-001-017",
    "founder_authorized": True,
    "status": "active",
    "delegate": {"role": "ROLE-RESEARCH", "instance": "researcher-1"},
    "approved_tickets": ["RES-T1", "RES-T2"],
    "scope": {
        "allowed_paths": [
            "research/strategies/",
            "research/sources/",
            "research/catalog.yaml",
            "research/sprints/ASA-RES-SPRINT-TEST/",
        ]
    },
    "out_of_scope": ["product_priority_or_strategy_selection"],
    "stop_conditions": ["a_non_delegable_decision_is_required"],
    "acceptance_criteria": ["dossier complete"],
    "required_validation": sorted(REQUIRED_GATES),
    "expires": ["sprint_completes", "sprint_stops", "Founder_revokes_delegation"],
}

ELIGIBLE_PR = {
    "ticket": "RES-T1",
    "changed_paths": [
        "research/strategies/ASA-RSCH-X.md",
        "research/sources/SRC-1.yaml",
        "research/catalog.yaml",
    ],
    "risk_class": "R1",
    "merged_by_role": "ROLE-RESEARCH",
    "merged_by_instance": "researcher-1",
    "self_review_recorded": True,
    "gates": {gate: "pass" for gate in REQUIRED_GATES},
}


def _pr(**changes):  # type: ignore[no-untyped-def]
    pull_request = copy.deepcopy(ELIGIBLE_PR)
    pull_request.update(changes)
    return pull_request


def _sprint(**changes):  # type: ignore[no-untyped-def]
    sprint = copy.deepcopy(ACTIVE_SPRINT)
    sprint.update(changes)
    return sprint


# --- positive -------------------------------------------------------------


def test_positive_authorized_research_sprint_merge_is_permitted() -> None:
    assert validate_activation(ACTIVE_SPRINT) == []
    decision = evaluate_merge(ACTIVE_SPRINT, ELIGIBLE_PR)
    assert decision.permitted, decision.reasons


# --- activation, expiry, revocation ----------------------------------------


def test_negative_no_activation_no_research_merge_authority() -> None:
    for activation in (None, {}, "active"):
        assert not evaluate_merge(activation, ELIGIBLE_PR).permitted


@pytest.mark.parametrize(
    "changes",
    [
        {"founder_authorized": False},
        {"status": "proposed"},
        {"governance_amendment": "GOV-AMD-001-013"},
        {"sprint_type": "implementation"},
        {"delegate": {"role": "ROLE-WORKER", "instance": "w"}},
        {"approved_tickets": []},
        {"expires": ["sprint_completes"]},
        {"required_validation": ["required_ci_checks"]},
    ],
)
def test_negative_invalid_or_unauthorized_activation_denies(changes) -> None:  # type: ignore[no-untyped-def]
    assert not evaluate_merge(_sprint(**changes), ELIGIBLE_PR).permitted


@pytest.mark.parametrize("status", ["completed", "stopped", "revoked"])
def test_expiry_and_revocation_end_delegated_merge(status: str) -> None:
    decision = evaluate_merge(_sprint(status=status), ELIGIBLE_PR)
    assert not decision.permitted
    assert any(reason.startswith("M001") for reason in decision.reasons)


def test_merger_must_be_the_named_delegate() -> None:
    for changes in (
        {"merged_by_role": "ROLE-WORKER"},
        {"merged_by_instance": "someone-else"},
    ):
        assert not evaluate_merge(ACTIVE_SPRINT, _pr(**changes)).permitted


# --- scope ------------------------------------------------------------------


def test_negative_out_of_scope_research_pr_cannot_use_delegation() -> None:
    unlisted_ticket = evaluate_merge(ACTIVE_SPRINT, _pr(ticket="RES-T9"))
    assert not unlisted_ticket.permitted
    outside_allowed = evaluate_merge(
        ACTIVE_SPRINT, _pr(changed_paths=["research/templates/strategy-dossier.md"])
    )
    assert not outside_allowed.permitted
    assert any(reason.startswith("M007") for reason in outside_allowed.reasons)


@pytest.mark.parametrize(
    "path",
    [
        "governance/amendments/GOV-AMD-017.md",
        "governance/frozen/RISK-001",
        "roles/researcher/INSTRUCTIONS.md",
        "project/roles/registry.yaml",
        "docs/sprints/ASA-RES-SPRINT-001.yaml",
        "research/README.md",
        ".github/workflows/validate-pos.yml",
        "AGENTS.md",
    ],
)
def test_negative_governance_pr_cannot_use_research_delegation(path: str) -> None:
    assert not evaluate_merge(ACTIVE_SPRINT, _pr(changed_paths=[path])).permitted


@pytest.mark.parametrize(
    "path",
    [
        "asa/api/screening_routes.py",
        "strategies/put_credit_spread_manifest.py",
        "strategy_runtime/trade_proposal.py",
        "migrations/versions/0021_x.py",
        "tools/pos/lean/research_delegation.py",
        "tests/pos/lean/test_research_role_governance.py",
        "Dockerfile",
    ],
)
def test_negative_production_code_cannot_use_research_delegation(path: str) -> None:
    mixed = _pr(changed_paths=["research/strategies/ASA-RSCH-X.md", path])
    assert not evaluate_merge(ACTIVE_SPRINT, mixed).permitted


def test_activation_cannot_widen_scope_beyond_research() -> None:
    for widened in (["governance/"], ["research/", "asa/"], ["research/README.md"], ["/research/"]):
        sprint = _sprint(scope={"allowed_paths": widened})
        assert any(error.startswith("A008") for error in validate_activation(sprint))
        assert not evaluate_merge(sprint, _pr(changed_paths=["asa/x.py"])).permitted


@pytest.mark.parametrize(
    "path", ["research/../governance/x.md", "/research/strategies/x.md", "research//x.md", ""]
)
def test_untrusted_path_escape_attempts_are_denied(path: str) -> None:
    assert not evaluate_merge(ACTIVE_SPRINT, _pr(changed_paths=[path])).permitted


def test_empty_change_list_is_not_a_merge_basis() -> None:
    assert not evaluate_merge(ACTIVE_SPRINT, _pr(changed_paths=[])).permitted


# --- gates, risk, self-review ------------------------------------------------


@pytest.mark.parametrize("gate", sorted(REQUIRED_GATES))
@pytest.mark.parametrize("state", [None, "fail", "skipped", "unavailable", "pending"])
def test_missing_or_non_passing_gate_blocks_merge(gate: str, state) -> None:  # type: ignore[no-untyped-def]
    gates = dict(ELIGIBLE_PR["gates"])
    if state is None:
        gates.pop(gate)
    else:
        gates[gate] = state
    assert not evaluate_merge(ACTIVE_SPRINT, _pr(gates=gates)).permitted


@pytest.mark.parametrize("risk", ["R2", "R3", "R4", "R5", None, "high"])
def test_risk_above_r1_is_never_delegable(risk) -> None:  # type: ignore[no-untyped-def]
    assert not evaluate_merge(ACTIVE_SPRINT, _pr(risk_class=risk)).permitted


def test_false_completion_claim_without_self_review_is_denied() -> None:
    assert not evaluate_merge(ACTIVE_SPRINT, _pr(self_review_recorded=False)).permitted


# --- authority matrix ----------------------------------------------------------


def _registry_role(role_id: str) -> dict:  # type: ignore[type-arg]
    registry = yaml.safe_load((REPO_ROOT / "project/roles/registry.yaml").read_text())
    return next(role for role in registry["roles"] if role["id"] == role_id)


def test_negative_role_research_cannot_select_product_priority() -> None:
    classes = _registry_role("ROLE-RESEARCH")["authority_classes"]
    forbidden = {
        "product_priority",
        "roadmap_priority",
        "strategy_selection_policy",
        "production_approval",
        "architecture",
        "production_implementation",
        "deployment",
        "governance",
    }
    assert forbidden <= set(classes["none"])
    assert not forbidden & (set(classes["decide"]) | set(classes["recommend"]))
    assert "strategy_selection" in classes["consult"]


def _matrix_rows() -> list[list[str]]:
    table = BOUNDARIES.split("## Authority Matrix", 1)[1].split("\n## ", 1)[0]
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in table.splitlines()
        if line.startswith("|") and not line.startswith("|---")
    ]
    return rows


def test_no_decide_collision_with_existing_permanent_roles() -> None:
    header, *rows = _matrix_rows()
    assert header == ["Action", "Founder", "Manager", "Architect", "Researcher", "Worker"]
    researcher_decides = 0
    for row in rows:
        decide_columns = [header[i] for i, cell in enumerate(row) if "DECIDE" in cell]
        assert len(decide_columns) <= 1, row
        researcher_decides += decide_columns == ["Researcher"]
    assert researcher_decides == 4
    technical = next(row for row in rows if row[0].startswith("Research question framing"))
    assert "DECIDE" in technical[3] and technical[4] == "Recommend"


def test_default_merge_authority_and_amendment_013_remain_unchanged() -> None:
    assert "Founder-only merge authority remains the default" in BOUNDARIES
    assert "ROLE-RESEARCH has no standing merge authority" in BOUNDARIES
    register = (REPO_ROOT / "governance/amendments/GOV-AMD-001.md").read_text()
    amendment_013 = register.split("# Amendment 013", 1)[1].split("# Amendment 014", 1)[0]
    assert "one identified implementation sprint" in amendment_013
    assert "Founder remains the sole merge authority" in amendment_013
    assert "Amendment 013 remains unchanged" in AMENDMENT


# --- amendment and qualification semantics ----------------------------------


def test_amendment_is_r5_reviewed_and_never_self_delegable() -> None:
    assert "R5" in AMENDMENT and "Constitutional Review" in AMENDMENT
    assert "no standing merge authority" in AMENDMENT
    assert "never merged under any delegation" in AMENDMENT
    assert "not eligible for any delegation" in AMENDMENT
    register = (REPO_ROOT / "governance/amendments/GOV-AMD-001.md").read_text()
    assert "# Amendment 017" in register
    manifest = yaml.safe_load((REPO_ROOT / "governance/manifest.yaml").read_text())
    assert any(doc["id"] == "GOV-AMD-017" for doc in manifest["documents"])


def test_qualification_is_evidence_state_not_implementation_approval() -> None:
    block = AMENDMENT.split("### A.4 Qualification semantics", 1)[1].split("### A.5", 1)[0]
    for phrase in (
        "ASA validated the strategy",
        "ASA should implement it",
        "outranks another strategy",
        "approved for production",
        "generate future profits",
    ):
        assert phrase in block
    catalog = yaml.safe_load((REPO_ROOT / "research/catalog.yaml").read_text())
    assert (
        "ASA_should_implement_the_strategy"
        in catalog["status_semantics"]["qualification_does_not_mean"]
    )


def test_rolespec_has_every_res002_section() -> None:
    for heading in (
        "A.1 Metadata",
        "A.2 Mission",
        "A.3 Authority Definition",
        "A.5 Responsibilities",
        "A.6 Non-Responsibilities",
        "A.7 Artifact Interaction",
        "A.8 Interaction Requirements",
        "A.9 Assignment and Acceptance",
        "A.10 Session Rehydration",
        "A.11 Context Requirements",
        "A.12 Escalation",
        "A.13 Failure Behavior",
        "A.14 Maintenance",
        "A.15 Versioning",
        "A.16 Review",
        "A.17 Regression Testing",
        "A.18 Evolution and Retirement",
    ):
        assert f"### {heading}" in AMENDMENT, heading


# --- role package and rehydration -------------------------------------------


def test_role_package_is_complete_and_rehydratable_from_repository() -> None:
    package = REPO_ROOT / "roles/researcher"
    for name in (
        "INSTANTIATION_PROMPT.md",
        "INSTRUCTIONS.md",
        "STARTUP_CHECKLIST.md",
        "OPERATING_LOOP.md",
        "REVIEW_TEMPLATE.md",
        "CONTEXT_PACKET.md",
    ):
        assert (package / name).stat().st_size > 0, name
    assert not (package / "FIRST_ASSIGNMENT.md").exists()
    prompt = (package / "INSTANTIATION_PROMPT.md").read_text()
    assert "Chat is disposable. GitHub is durable research memory." in prompt
    assert "never need a predecessor's chat" in prompt
    order = [
        prompt.index(ref)
        for ref in (
            "GOV-AMD-017.md",
            "governance/frozen/RISK-001",
            "AUTHORITY_BOUNDARIES.md",
            "roles/researcher/INSTRUCTIONS.md",
            "research/catalog.yaml",
        )
    ]
    assert order == sorted(order)
    role = _registry_role("ROLE-RESEARCH")
    for field in ("specification", "instructions", "instantiation_prompt"):
        assert (REPO_ROOT / role[field]).is_file()


def test_every_role_package_reference_resolves() -> None:
    for path in (REPO_ROOT / "roles/researcher").glob("*.md"):
        for ref in re.findall(
            r"`((?:research|roles|governance|docs|tools|project)/[^`* <]+)`", path.read_text()
        ):
            target = ref.rstrip("/")
            if "<" in target or "*" in target:
                continue
            assert (REPO_ROOT / target).exists(), f"{path.name}: {ref}"


def test_template_activation_grants_nothing() -> None:
    template = REPO_ROOT / "docs/sprints/RESEARCH-SPRINT-TEMPLATE.yaml"
    activation = yaml.safe_load(template.read_text())["activation"]
    assert activation["status"] == "proposed"
    assert not evaluate_merge(activation, ELIGIBLE_PR).permitted
    assert delegation_main([str(template)]) == 1


# --- research library validation (rehydration integrity) --------------------


def test_research_library_is_consistent_on_main() -> None:
    assert validate_library(REPO_ROOT) == []


def _library_copy(tmp_path: Path) -> Path:
    shutil.copytree(REPO_ROOT / "research", tmp_path / "research")
    for record in yaml.safe_load((REPO_ROOT / "research/catalog.yaml").read_text())["records"]:
        for prior in record.get("prior_ASA_research") or []:
            target = tmp_path / prior
            target.parent.mkdir(parents=True, exist_ok=True)
            if prior.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.write_text("x")
    return tmp_path


def test_incomplete_or_inconsistent_library_fails_the_gate(tmp_path: Path) -> None:
    root = _library_copy(tmp_path)
    assert validate_library(root) == []
    (root / "research/strategies/ASA-RSCH-ORPHAN.md").write_text("- **Research status:** TRIAGE\n")
    dossier = root / "research/strategies/ASA-RSCH-SPY-PCS-001.md"
    dossier.write_text(
        dossier.read_text().replace("**Research status:** TRIAGE", "**Research status:** QUALIFIED")
    )
    (root / "research/sources/OA-SPY-PCS-2021.yaml").unlink()
    codes = {error.split()[0] for error in validate_library(root)}
    assert {"R005", "R006", "R009"} <= codes
