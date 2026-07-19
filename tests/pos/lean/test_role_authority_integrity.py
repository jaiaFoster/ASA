"""
Tests for durable role authority assertions.

CUTOVER-05 (LEAN-POS-10) deleted tests/pos/test_role_bootstrap.py.
This file restores the unique durable coverage: role file existence,
authority boundary enforcement, and Founder merge acceptance — assertions
that are independent of any POS runtime and must hold permanently.

Bootstrap-specific assertions (registry status, instantiation state) are
not restored here as they were bound to a temporary migration state.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
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


# ---------------------------------------------------------------------------
# Role file existence
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rel_path", REQUIRED_ROLE_FILES)
def test_role_file_exists(rel_path):
    path = REPO_ROOT / rel_path
    assert path.exists(), f"Required role file missing: {rel_path}"
    assert path.stat().st_size > 0, f"Role file is empty: {rel_path}"


# ---------------------------------------------------------------------------
# Architect first assignment
# ---------------------------------------------------------------------------

def test_architect_first_assignment_references_lean_pos():
    content = (REPO_ROOT / "roles/architect/FIRST_ASSIGNMENT.md").read_text()
    assert "Lean POS" in content or "ARCH-POS" in content


# ---------------------------------------------------------------------------
# Role file pointers resolve
# ---------------------------------------------------------------------------

def test_registry_role_file_pointers_resolve():
    registry_path = REPO_ROOT / "project/roles/registry.yaml"
    if not registry_path.exists():
        pytest.skip("project/roles/registry.yaml not present")
    data = yaml.safe_load(registry_path.read_text())
    for role in data.get("roles", []):
        for field in ("instructions", "instantiation_prompt"):
            if role.get(field):
                path = REPO_ROOT / role[field]
                assert path.exists(), (
                    f"Role {role['id']} field '{field}' points to missing file: {role[field]}"
                )


# ---------------------------------------------------------------------------
# Authority boundaries — Manager and Architect must not have merge authority
# ---------------------------------------------------------------------------

def test_authority_boundaries_denies_manager_merge():
    content = (REPO_ROOT / "roles/shared/AUTHORITY_BOUNDARIES.md").read_text()
    assert "Founder" in content
    assert "Manager" in content
    content_lower = content.lower()
    assert "no" in content_lower or "may not" in content_lower or "none" in content_lower


def test_github_acceptance_model_documents_founder_merge():
    content = (REPO_ROOT / "roles/shared/GITHUB_ACCEPTANCE_MODEL.md").read_text()
    assert "Founder" in content
    assert "merge" in content.lower()
    assert "accept" in content.lower()


def test_manager_instructions_deny_merge():
    content = (REPO_ROOT / "roles/manager/INSTRUCTIONS.md").read_text()
    content_lower = content.lower()
    assert "merge" in content_lower
    assert "must not" in content_lower or "may not" in content_lower or "cannot" in content_lower


def test_architect_instructions_deny_merge():
    content = (REPO_ROOT / "roles/architect/INSTRUCTIONS.md").read_text()
    content_lower = content.lower()
    assert "merge" in content_lower
    assert "must not" in content_lower or "may not" in content_lower or "none" in content_lower


def test_founder_instantiation_guide_references_roles():
    content = (REPO_ROOT / "roles/FOUNDER_INSTANTIATION_GUIDE.md").read_text()
    assert "Manager" in content
    assert "Architect" in content


# ---------------------------------------------------------------------------
# Risk classes R0–R5 are documented
# ---------------------------------------------------------------------------

def test_risk_scaled_process_covers_r0_to_r5():
    content = (REPO_ROOT / "roles/shared/RISK_SCALED_PROCESS.md").read_text()
    for cls in ("R0", "R1", "R2", "R3", "R4", "R5"):
        assert cls in content, f"Risk class {cls} not in RISK_SCALED_PROCESS.md"
