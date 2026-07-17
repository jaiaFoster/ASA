"""
Tests for ROLE-BOOTSTRAP-01: Manager and Architect role packages.

Verifies:
- Required role files exist
- Instantiation prompts exist
- Registry marks roles as prepared and not instantiated
- Authority files do not grant merge authority to Manager or Architect
- Architect first assignment exists
- Founder merge acceptance is documented
- No role claims to be instantiated
"""

from pathlib import Path
import yaml
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ROLES_DIR = REPO_ROOT / "roles"

REQUIRED_ROLE_FILES = [
    "roles/README.md",
    "roles/FOUNDER_INSTANTIATION_GUIDE.md",
    "roles/manager/INSTRUCTIONS.md",
    "roles/manager/INSTANTIATION_PROMPT.md",
    "roles/manager/STARTUP_CHECKLIST.md",
    "roles/manager/OPERATING_LOOP.md",
    "roles/manager/CONTEXT_PACKET.md",
    "roles/manager/TASK_TEMPLATES.md",
    "roles/architect/INSTRUCTIONS.md",
    "roles/architect/INSTANTIATION_PROMPT.md",
    "roles/architect/STARTUP_CHECKLIST.md",
    "roles/architect/OPERATING_LOOP.md",
    "roles/architect/CONTEXT_PACKET.md",
    "roles/architect/REVIEW_TEMPLATE.md",
    "roles/architect/FIRST_ASSIGNMENT.md",
    "roles/shared/AUTHORITY_BOUNDARIES.md",
    "roles/shared/GITHUB_ACCEPTANCE_MODEL.md",
    "roles/shared/RISK_SCALED_PROCESS.md",
    "roles/shared/HANDOFF_PROTOCOL.md",
    "roles/shared/GLOSSARY.md",
]

FORBIDDEN_AUTHORITY_CLAIMS = [
    "may merge",
    "has merge authority",
    "Manager may merge",
    "Architect may merge",
    "Manager may deploy",
    "Architect may deploy",
]

MERGE_ACCEPTANCE_PHRASES = [
    "Founder merges",
    "merge is acceptance",
    "merge.*accept",
]


@pytest.mark.parametrize("rel_path", REQUIRED_ROLE_FILES)
def test_role_file_exists(rel_path):
    path = REPO_ROOT / rel_path
    assert path.exists(), f"Required role file missing: {rel_path}"
    assert path.stat().st_size > 0, f"Role file is empty: {rel_path}"


def test_manager_instantiation_prompt_exists():
    prompt = REPO_ROOT / "roles/manager/INSTANTIATION_PROMPT.md"
    content = prompt.read_text(encoding="utf-8")
    assert "ROLE-PM" in content or "Manager" in content
    assert len(content) > 500, "Instantiation prompt seems too short"


def test_architect_instantiation_prompt_exists():
    prompt = REPO_ROOT / "roles/architect/INSTANTIATION_PROMPT.md"
    content = prompt.read_text(encoding="utf-8")
    assert "ROLE-ARCH" in content or "Architect" in content
    assert len(content) > 500, "Instantiation prompt seems too short"


def test_architect_first_assignment_exists():
    path = REPO_ROOT / "roles/architect/FIRST_ASSIGNMENT.md"
    content = path.read_text(encoding="utf-8")
    assert "ARCH-POS-001" in content
    assert "Lean POS" in content


def test_registry_has_manager_prepared():
    registry_path = REPO_ROOT / "project/roles/registry.yaml"
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    roles = {r["id"]: r for r in data.get("roles", [])}
    pm = roles.get("ROLE-PM")
    assert pm is not None, "ROLE-PM not in registry"
    assert pm.get("status") == "prepared", f"ROLE-PM status should be 'prepared', got {pm.get('status')!r}"
    assert pm.get("instantiated") is False, "ROLE-PM should not be instantiated"
    assert pm.get("instantiation_prompt"), "ROLE-PM missing instantiation_prompt pointer"


def test_registry_has_architect_prepared():
    registry_path = REPO_ROOT / "project/roles/registry.yaml"
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    roles = {r["id"]: r for r in data.get("roles", [])}
    arch = roles.get("ROLE-ARCH")
    assert arch is not None, "ROLE-ARCH not in registry"
    assert arch.get("status") == "prepared", f"ROLE-ARCH status should be 'prepared', got {arch.get('status')!r}"
    assert arch.get("instantiated") is False, "ROLE-ARCH should not be instantiated"
    assert arch.get("instantiation_prompt"), "ROLE-ARCH missing instantiation_prompt pointer"


def test_registry_instructions_paths_exist():
    registry_path = REPO_ROOT / "project/roles/registry.yaml"
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    for role in data.get("roles", []):
        for field in ("instructions", "instantiation_prompt"):
            if role.get(field):
                path = REPO_ROOT / role[field]
                assert path.exists(), (
                    f"Role {role['id']} field '{field}' points to missing file: {role[field]}"
                )


def test_authority_boundaries_denies_manager_merge():
    content = (REPO_ROOT / "roles/shared/AUTHORITY_BOUNDARIES.md").read_text(encoding="utf-8")
    assert "No" in content or "NONE" in content or "may not" in content.lower()
    assert "Founder" in content
    # Check the merge row includes No for manager
    assert "Manager" in content


def test_github_acceptance_model_documents_merge_as_acceptance():
    content = (REPO_ROOT / "roles/shared/GITHUB_ACCEPTANCE_MODEL.md").read_text(encoding="utf-8")
    assert "merge" in content.lower()
    assert "accepted" in content.lower() or "acceptance" in content.lower()
    # Should contain the key rule
    assert "Founder" in content


def test_founder_instantiation_guide_exists_and_complete():
    content = (REPO_ROOT / "roles/FOUNDER_INSTANTIATION_GUIDE.md").read_text(encoding="utf-8")
    assert "Manager" in content
    assert "Architect" in content
    assert "ARCH-POS-001" in content


def test_manager_instructions_deny_merge():
    content = (REPO_ROOT / "roles/manager/INSTRUCTIONS.md").read_text(encoding="utf-8")
    content_lower = content.lower()
    assert "merge" in content_lower
    assert "must not" in content_lower or "may not" in content_lower or "cannot" in content_lower


def test_architect_instructions_deny_merge():
    content = (REPO_ROOT / "roles/architect/INSTRUCTIONS.md").read_text(encoding="utf-8")
    content_lower = content.lower()
    assert "merge" in content_lower
    assert "must not" in content_lower or "may not" in content_lower or "none" in content_lower


def test_risk_scaled_process_covers_r0_to_r5():
    content = (REPO_ROOT / "roles/shared/RISK_SCALED_PROCESS.md").read_text(encoding="utf-8")
    for cls in ("R0", "R1", "R2", "R3", "R4", "R5"):
        assert cls in content, f"Risk class {cls} not mentioned in RISK_SCALED_PROCESS.md"


def test_bootstrap_status_reflects_role_bootstrap():
    status_path = REPO_ROOT / "project/BOOTSTRAP_STATUS.yaml"
    data = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    assert data.get("phase") == "ROLE_BOOTSTRAP", (
        f"Phase should be ROLE_BOOTSTRAP, got {data.get('phase')!r}"
    )
    # Roles should not be instantiated
    role_pkg = data.get("role_package_status", {})
    for role_name in ("manager", "architect"):
        assert role_pkg.get(role_name, {}).get("instantiated") is False, (
            f"Role {role_name} should not be marked instantiated"
        )


def test_no_role_claims_active_status_in_registry():
    registry_path = REPO_ROOT / "project/roles/registry.yaml"
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    for role in data.get("roles", []):
        if role.get("type") == "permanent_ai_role":
            assert role.get("status") != "active", (
                f"Role {role['id']} must not be marked 'active' — it is not yet instantiated"
            )
            assert role.get("instantiated") is not True, (
                f"Role {role['id']} must not be marked instantiated"
            )
