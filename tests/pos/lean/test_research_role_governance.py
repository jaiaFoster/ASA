"""ROLE-RESEARCH and Research Sprint Delegation regression suite (GOV-AMD-001 Amendment 017).

This is the versioned RES-002 §21 suite for ROLE-RESEARCH RoleSpec v1.0.0. Each
test's docstring records its scenario fields in this order:
- scenario and inputs;
- governance;
- expected action;
- expected escalation;
- prohibited behavior;
- expected output.

These are the A.17 table rows.
"""

from __future__ import annotations

import copy
import re
import shutil
from datetime import date
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
from tools.pos.lean.research_library import CANONICAL_SEMANTICS, validate_library

REPO_ROOT = Path(__file__).resolve().parents[3]
AMENDMENT = (REPO_ROOT / "governance/amendments/GOV-AMD-017.md").read_text()
BOUNDARIES = (REPO_ROOT / "roles/shared/AUTHORITY_BOUNDARIES.md").read_text()
TODAY = date(2026, 10, 1)

ACTIVE_SPRINT = {
    "sprint_id": "ASA-RES-SPRINT-TEST",
    "sprint_type": "research",
    "governance_amendment": "GOV-AMD-001-017",
    "founder_authorized": True,
    "status": "active",
    "expires_at": "2026-12-31",
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
    "expires": [
        "sprint_completes",
        "sprint_stops",
        "expires_at_passes",
        "Founder_revokes_delegation",
    ],
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


def _decide(activation, pull_request, **kwargs):  # type: ignore[no-untyped-def]
    return evaluate_merge(activation, pull_request, evaluated_on=kwargs.pop("on", TODAY), **kwargs)


# --- #1 DECIDE research status: positive -----------------------------------


def test_positive_authorized_research_sprint_merge_is_permitted() -> None:
    """#1 An eligible dossier, source and catalog PR under an active sprint | B.3 |
    delegated merge permitted | none | merge without gates | permitted=True."""
    assert validate_activation(ACTIVE_SPRINT) == []
    decision = _decide(ACTIVE_SPRINT, ELIGIBLE_PR, repository_root=REPO_ROOT)
    assert decision.permitted, decision.reasons


# --- #15 activation, expiry, revocation -------------------------------------


def test_negative_no_activation_no_research_merge_authority() -> None:
    """No activation record | B.1, B.7 | deny | Founder merge | delegated merge | denied."""
    for activation in (None, {}, "active", []):
        assert not _decide(activation, ELIGIBLE_PR).permitted


@pytest.mark.parametrize(
    "changes",
    [
        {"founder_authorized": False},
        {"status": "proposed"},
        {"governance_amendment": "GOV-AMD-001-013"},
        {"sprint_type": "implementation"},
        {"delegate": {"role": "ROLE-WORKER", "instance": "w"}},
        {"delegate": "ROLE-RESEARCH"},
        {"approved_tickets": []},
        {"approved_tickets": [None]},
        {"approved_tickets": [" "]},
        {"approved_tickets": [["RES-T1"]]},
        {"expires": ["sprint_completes"]},
        {"expires_at": None},
        {"expires_at": "soon"},
        {"required_validation": ["required_ci_checks"]},
        {"sprint_id": "../x"},
        {"sprint_id": ".."},
        {"sprint_id": "."},
        {"sprint_id": "a b"},
    ],
)
def test_negative_invalid_or_unauthorized_activation_denies(changes) -> None:  # type: ignore[no-untyped-def]
    """Invalid or unauthorized activation | B.1 | deny cleanly without raising | Founder |
    merge | denied."""
    assert not _decide(_sprint(**changes), ELIGIBLE_PR).permitted


@pytest.mark.parametrize("status", ["completed", "stopped", "revoked"])
def test_expiry_and_revocation_end_delegated_merge(status: str) -> None:
    """#15 Terminal status | B.6 | deny | none | post-expiry merge | M001."""
    decision = _decide(_sprint(status=status), ELIGIBLE_PR)
    assert not decision.permitted
    assert any(reason.startswith("M001") for reason in decision.reasons)


def test_expiry_is_mechanical_by_date() -> None:
    """#15 Evaluation after expires_at | B.6 | deny | none | post-expiry merge | M012."""
    assert _decide(ACTIVE_SPRINT, ELIGIBLE_PR, on=date(2026, 12, 31)).permitted
    decision = _decide(ACTIVE_SPRINT, ELIGIBLE_PR, on=date(2027, 1, 1))
    assert not decision.permitted
    assert any(reason.startswith("M012") for reason in decision.reasons)


def test_merged_closure_record_ends_the_delegation(tmp_path: Path) -> None:
    """#15 CLOSURE.md present on main | B.6, B.8 | deny | none | post-closure merge | M013."""
    closure = tmp_path / "research/sprints/ASA-RES-SPRINT-TEST/CLOSURE.md"
    assert _decide(ACTIVE_SPRINT, ELIGIBLE_PR, repository_root=tmp_path).permitted
    closure.parent.mkdir(parents=True)
    closure.write_text("closed")
    decision = _decide(ACTIVE_SPRINT, ELIGIBLE_PR, repository_root=tmp_path)
    assert not decision.permitted
    assert any(reason.startswith("M013") for reason in decision.reasons)


def test_merger_must_be_the_named_delegate() -> None:
    """A non-delegate merger | B.2 | deny | Founder | impersonation | M002."""
    for changes in ({"merged_by_role": "ROLE-WORKER"}, {"merged_by_instance": "someone-else"}):
        assert not _decide(ACTIVE_SPRINT, _pr(**changes)).permitted


# --- #8, #11, #12 scope -----------------------------------------------------


def test_negative_out_of_scope_research_pr_cannot_use_delegation() -> None:
    """#11 An unlisted or missing ticket; #8 a path outside allowed_paths | B.3 | deny |
    sprint scope / Founder | scope creep | M003 / M007."""
    for ticket in ("RES-T9", None, " ", ["RES-T1"]):
        assert not _decide(ACTIVE_SPRINT, _pr(ticket=ticket)).permitted
    template_edit = _decide(
        ACTIVE_SPRINT, _pr(changed_paths=["research/templates/strategy-dossier.md"])
    )
    assert not template_edit.permitted
    assert any(reason.startswith("M007") for reason in template_edit.reasons)


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
    """#7 A governance, role, sprint, contract or workflow path | B.4 | deny | Founder merge |
    delegated governance merge | denied."""
    assert not _decide(ACTIVE_SPRINT, _pr(changed_paths=[path])).permitted


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
        "research/sources/conftest.py",
        "research/strategies/run.sh",
        "research/strategies/notebook.ipynb",
    ],
)
def test_negative_production_code_cannot_use_research_delegation(path: str) -> None:
    """#7/#14 Production code or any executable file, even under research/ | B.3, B.4 |
    deny | Founder merge | delegated code merge | denied."""
    mixed = _pr(changed_paths=["research/strategies/ASA-RSCH-X.md", path])
    assert not _decide(_sprint(scope={"allowed_paths": ["research/"]}), mixed).permitted
    assert not _decide(ACTIVE_SPRINT, mixed).permitted


def test_activation_cannot_widen_scope_beyond_research() -> None:
    """#12 An activation listing forbidden or root paths | B.1, B.4 | invalid | Founder |
    obeying the activation | A008."""
    for widened in (
        ["governance/"],
        ["research/", "asa/"],
        ["research/README.md"],
        ["/research/"],
        ["research/"],
    ):
        sprint = _sprint(scope={"allowed_paths": widened})
        assert any(error.startswith("A008") for error in validate_activation(sprint))
        assert not _decide(sprint, _pr(changed_paths=["asa/x.py"])).permitted


@pytest.mark.parametrize(
    "path",
    [
        "research/../governance/x.md",
        "/research/strategies/x.md",
        "research//x.md",
        "research/./README.md",
        "research/strategies/",
        "",
        None,
        7,
    ],
)
def test_untrusted_path_escape_attempts_are_denied(path) -> None:  # type: ignore[no-untyped-def]
    """#14 Untrusted path input | B.3 | deny | none | path traversal | M005."""
    assert not _decide(ACTIVE_SPRINT, _pr(changed_paths=[path])).permitted


@pytest.mark.parametrize("record", [None, [], "merge", {"changed_paths": "research/x.md"}])
def test_malformed_pull_request_records_fail_closed_without_raising(record) -> None:  # type: ignore[no-untyped-def]
    """#14 Malformed record | B.3 | deny cleanly | none | exception-driven bypass | denied."""
    assert not _decide(ACTIVE_SPRINT, record).permitted


# --- #13 gates, risk, self-review ------------------------------------------


@pytest.mark.parametrize("gate", sorted(REQUIRED_GATES))
@pytest.mark.parametrize("state", [None, "fail", "skipped", "unavailable", "pending"])
def test_missing_or_non_passing_gate_blocks_merge(gate: str, state) -> None:  # type: ignore[no-untyped-def]
    """#13 A missing, failing, skipped or unavailable gate | B.3 | deny | restore the gate |
    false completion | M010."""
    gates = dict(ELIGIBLE_PR["gates"])
    if state is None:
        gates.pop(gate)
    else:
        gates[gate] = state
    assert not _decide(ACTIVE_SPRINT, _pr(gates=gates)).permitted


@pytest.mark.parametrize("risk", ["R2", "R3", "R4", "R5", None, "high"])
def test_risk_above_r1_is_never_delegable(risk) -> None:  # type: ignore[no-untyped-def]
    """Risk above R1 | B.3, B.5 | deny | Founder | floor bypass | M008."""
    assert not _decide(ACTIVE_SPRINT, _pr(risk_class=risk)).permitted


def test_false_completion_claim_without_self_review_is_denied() -> None:
    """#13 No self-review | B.3 | deny | none | false completion | M009."""
    assert not _decide(ACTIVE_SPRINT, _pr(self_review_recorded=False)).permitted


# --- #5, #6 authority -------------------------------------------------------


def _registry() -> dict:  # type: ignore[type-arg]
    return yaml.safe_load((REPO_ROOT / "project/roles/registry.yaml").read_text())


def _registry_role(role_id: str) -> dict:  # type: ignore[type-arg]
    return next(role for role in _registry()["roles"] if role["id"] == role_id)


def test_negative_role_research_cannot_select_product_priority() -> None:
    """#5 RECOMMEND-only boundary | A.3 | NONE on selection and priority | Founder |
    selecting strategies | registry classes."""
    classes = _registry_role("ROLE-RESEARCH")["authority_classes"]
    forbidden = {
        "product_priority",
        "roadmap_priority",
        "strategy_selection",
        "strategy_selection_policy",
        "production_approval",
        "architecture",
        "production_implementation",
        "deployment",
        "governance",
    }
    assert forbidden <= set(classes["none"])
    assert not forbidden & (set(classes["decide"]) | set(classes["recommend"]))
    assert "strategy_selection_input" in classes["recommend"]


def test_research_holds_no_consult_class_and_imposes_no_obligation() -> None:
    """#6 No consultation obligation | A.3 | RECOMMEND only | none | blocking a Founder or PM
    decision | consult list empty; matrix shows no Consult for the Researcher."""
    assert _registry_role("ROLE-RESEARCH")["authority_classes"]["consult"] == []
    header, *rows = _matrix_rows()
    researcher = header.index("Researcher")
    assert not any("Consult" in row[researcher] for row in rows)
    assert "holds no CONSULT class" in AMENDMENT
    assert "creates no consultation obligation" in AMENDMENT


def _matrix_rows() -> list[list[str]]:
    table = BOUNDARIES.split("## Authority Matrix", 1)[1].split("\n## ", 1)[0]
    return [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in table.splitlines()
        if line.startswith("|") and not line.startswith("|---")
    ]


def test_no_decide_collision_with_existing_permanent_roles() -> None:
    """No DECIDE collision | RES-002 §8.3 | ≤1 DECIDE per row | Founder | overlapping DECIDE |
    4 Researcher-only DECIDE rows; ROLE-ARCH keeps technical framing."""
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
    method = next(row for row in rows if row[0].startswith("External strategy research method"))
    assert method[3] == "No"


def test_default_merge_authority_and_amendment_013_remain_unchanged() -> None:
    """Non-regression | Amendment 013, B.7 | unchanged | — | silent authority change | text."""
    assert "Founder-only merge authority remains the default" in BOUNDARIES
    assert "ROLE-RESEARCH has no standing merge authority" in BOUNDARIES
    register = (REPO_ROOT / "governance/amendments/GOV-AMD-001.md").read_text()
    amendment_013 = register.split("# Amendment 013", 1)[1].split("# Amendment 014", 1)[0]
    assert "one identified implementation sprint" in amendment_013
    assert "Founder remains the sole merge authority" in amendment_013
    assert "Amendment 013 remains unchanged" in AMENDMENT


def test_lower_tier_acceptance_and_process_models_recognize_part_b() -> None:
    """Lower-tier conflicts | RISK-001 §11.4 | both delegations recognized | — | a research merge
    not counting as acceptance | text."""
    acceptance = (REPO_ROOT / "roles/shared/GITHUB_ACCEPTANCE_MODEL.md").read_text()
    process = (REPO_ROOT / "roles/shared/RISK_SCALED_PROCESS.md").read_text()
    assert "Amendment 017 Part B" in acceptance and "Amendment 013" in acceptance
    assert "Amendment 017 Part B research-sprint delegation" in process


def test_activation_requires_personal_founder_merge() -> None:
    """Activation provenance | B.1 | the Founder's personal merge only | — | activation by
    delegate or commit author | registry login and checklist."""
    assert _registry_role("ROLE-FOUNDER")["github_login"]
    assert "Founder personally merged it" in AMENDMENT
    checklist = (REPO_ROOT / "roles/researcher/STARTUP_CHECKLIST.md").read_text()
    assert "merged_by" in checklist and "github_login" in checklist


# --- amendment, qualification, structure ------------------------------------


def test_amendment_is_r5_reviewed_and_never_self_delegable() -> None:
    """R5 floor | RISK-001 §10.1, GOV-AMD-001 §0.3 | Founder merge | — | self-delegated
    governance merge | text and manifest."""
    assert "R5" in AMENDMENT and "Constitutional Review" in AMENDMENT
    assert "no standing merge authority" in AMENDMENT
    assert "never merged under any delegation" in AMENDMENT
    assert "not eligible for any delegation" in AMENDMENT
    assert "changes no RISK-001 §10.1 cell" in AMENDMENT
    register = (REPO_ROOT / "governance/amendments/GOV-AMD-001.md").read_text()
    assert "# Amendment 017" in register
    manifest = yaml.safe_load((REPO_ROOT / "governance/manifest.yaml").read_text())
    assert any(doc["id"] == "GOV-AMD-017" for doc in manifest["documents"])


def test_qualification_is_evidence_state_with_one_canonical_home() -> None:
    """Qualification semantics | A.4 | a single canonical statement | — | a restated or
    delegable definition | A.4 text; catalog pinned to it."""
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
    assert catalog["status_semantics"] == CANONICAL_SEMANTICS
    assert "A.4 controls" in (REPO_ROOT / "research/README.md").read_text()


def test_rolespec_has_every_res002_section_and_trial_status() -> None:
    """Structure | RES-002 §6, §7; RES-001 §14.2 | all sections; trial; no auto-promotion |
    — | missing section | headings."""
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
    assert "| `status` | `trial`" in AMENDMENT
    assert "no automatic promotion" in AMENDMENT
    assert "## Changelog" in AMENDMENT
    assert "Research Result Packet" in AMENDMENT


# --- #9, #10, #14 rehydration and untrusted content --------------------------


def test_role_package_is_complete_and_rehydratable_from_repository() -> None:
    """#9 Rehydration from zero memory | A.10 | package complete; precedence order | — |
    relying on chat | files and order."""
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
            "Explicit Founder instruction",
            "GOV-AMD-001.md",
            "governance/frozen/RISK-001",
            "GOV-AMD-017.md",
            "roles/shared/AUTHORITY_BOUNDARIES.md",
            "research/catalog.yaml",
            "docs/sprints/",
            "External content",
        )
    ]
    assert order == sorted(order)
    role = _registry_role("ROLE-RESEARCH")
    for field in ("specification", "instructions", "instantiation_prompt"):
        assert (REPO_ROOT / role[field]).is_file()


def test_external_content_is_data_never_instructions() -> None:
    """#14 Embedded instructions in a source | A.7 | treat as data; record a finding | none |
    following them | text in the RoleSpec and package."""
    assert "embedded instructions are never followed" in AMENDMENT.lower()
    for name in ("INSTANTIATION_PROMPT.md", "INSTRUCTIONS.md", "OPERATING_LOOP.md"):
        text = (REPO_ROOT / "roles/researcher" / name).read_text().lower()
        assert "instructions" in text and ("never follow" in text or "never act" in text), name


def test_every_role_package_reference_resolves() -> None:
    """#9 Reference integrity | A.10 | every cited path exists | — | dangling rehydration
    pointers | paths."""
    for path in (REPO_ROOT / "roles/researcher").glob("*.md"):
        for ref in re.findall(
            r"`((?:research|roles|governance|docs|tools|project)/[^`* <]+)`", path.read_text()
        ):
            target = ref.rstrip("/")
            if "<" in target or "*" in target:
                continue
            assert (REPO_ROOT / target).exists(), f"{path.name}: {ref}"


def test_template_activation_grants_nothing() -> None:
    """Template | B.1 | not an activation | — | activation without Founder merge | invalid."""
    template = REPO_ROOT / "docs/sprints/RESEARCH-SPRINT-TEMPLATE.yaml"
    activation = yaml.safe_load(template.read_text())["activation"]
    assert activation["status"] == "proposed"
    assert not _decide(activation, ELIGIBLE_PR).permitted
    assert delegation_main([str(template)]) == 1


# --- #2, #3, #4, #10 research library validation -----------------------------


def test_research_library_is_consistent_on_main() -> None:
    """Library gate on main | A.14 | OK | — | — | no errors."""
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
    """#10 Incomplete rehydration | A.10 | gate fails | repair first | delegated merge |
    R005 / R006 / R009."""
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


def test_decide_classes_are_bounded_by_the_library_gate(tmp_path: Path) -> None:
    """#2 Evidence characterization (invalid source class); #4 taxonomy and status (a status
    outside the lifecycle); qualification semantics restated in the catalog | A.3, A.4 | gate
    fails | fix before merge | invented classes or statuses | R007 / R003 / R010."""
    root = _library_copy(tmp_path)
    source = root / "research/sources/OA-SPY-PCS-2021.yaml"
    source.write_text(
        source.read_text().replace("source_class: EXTERNAL_SECONDARY", "source_class: HEARSAY")
    )
    catalog_path = root / "research/catalog.yaml"
    catalog = catalog_path.read_text().replace("research_status: TRIAGE", "research_status: HOT", 1)
    catalog = catalog.replace(
        f"status_semantics: {CANONICAL_SEMANTICS}",
        "status_semantics:\n  qualification_means: ASA should build it",
    )
    catalog_path.write_text(catalog)
    codes = {error.split()[0] for error in validate_library(root)}
    assert {"R003", "R007", "R010"} <= codes


def test_cli_checks_closure_against_the_repository_not_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#15 CLI run from another directory | B.6 | deny once closure is merged | — |
    closure check silently skipped | M013 / DENIED."""
    import tools.pos.lean.research_delegation as delegation

    repository = tmp_path / "repo"
    closure = repository / "research/sprints/ASA-RES-SPRINT-TEST/CLOSURE.md"
    closure.parent.mkdir(parents=True)
    closure.write_text("closed")
    sprint_file = tmp_path / "sprint.yaml"
    sprint_file.write_text(yaml.safe_dump({"activation": ACTIVE_SPRINT}))
    pr_file = tmp_path / "pr.yaml"
    pr_file.write_text(yaml.safe_dump(ELIGIBLE_PR))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(delegation, "REPO_ROOT", repository)
    args = [str(sprint_file), "--pr", str(pr_file), "--on", "2026-10-01"]
    assert delegation.main(args) == 1
    closure.unlink()
    assert delegation.main(args) == 0
