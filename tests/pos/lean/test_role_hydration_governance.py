"""GOV-AMD-018 hydration, reviewer, lifecycle, and gateway regressions."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest
import yaml

from tools.pos.lean import role_hydration
from tools.pos.lean.role_hydration import (
    validate_gateway_disposition,
    validate_hydration_packet,
)

REAL_AMENDMENT_IS_EFFECTIVE = role_hydration._amendment_is_effective
REAL_TRUSTED_TARGET_HEAD = role_hydration._trusted_target_head
REAL_GIT = role_hydration._git

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = yaml.safe_load((ROOT / "project/roles/registry.yaml").read_text())
TODAY = date(2026, 10, 9)

PACKET = {
    "assignment_id": "PT-00",
    "requested_role": "ROLE-PM",
    "purpose": "bounded consultation",
    "question": "classify dependency",
    "repository_ref": "main@abc",
    "work_reference": "issue-547",
    "risk_class": "R2",
    "acceptance_criteria": ["durable disposition"],
    "canonical_artifacts": ["docs/sprints/PRODUCTION-TRUST-001.yaml"],
    "permitted_actions": ["read", "consult"],
    "prohibited_actions": ["edit", "merge", "deploy"],
    "expected_output": "GitHub issue comment",
    "termination_condition": "after durable response",
}


def committed_fixture_repo(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "governance", tmp_path / "governance")
    shutil.copytree(ROOT / "project/roles", tmp_path / "project/roles")
    shutil.copytree(ROOT / "roles", tmp_path / "roles")
    sprint = tmp_path / "docs/sprints/PRODUCTION-TRUST-001.yaml"
    sprint.parent.mkdir(parents=True)
    sprint.write_text((ROOT / "docs/sprints/PRODUCTION-TRUST-001.yaml").read_text())
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=tmp_path, check=True)
    return tmp_path


def check(packet=PACKET, registry=REGISTRY, **kwargs):  # type: ignore[no-untyped-def]
    return validate_hydration_packet(
        packet,
        registry,
        evaluated_on=kwargs.pop("evaluated_on", TODAY),
        repo_root=kwargs.pop("repo_root", ROOT),
        **kwargs,
    )


@pytest.fixture(autouse=True)
def trusted_repository_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(role_hydration, "_amendment_is_effective", lambda _root: True)
    monkeypatch.setattr(
        role_hydration,
        "_trusted_target_head",
        lambda _root, ref: str(ref).rsplit("@", maxsplit=1)[-1] if "@" in str(ref) else None,
    )


def test_pm_and_arch_bounded_trials_are_hydratable() -> None:
    assert check() == []
    assert check({**PACKET, "requested_role": "ROLE-ARCH"}) == []


def test_research_governing_trial_is_hydratable() -> None:
    assert check({**PACKET, "requested_role": "ROLE-RESEARCH"}) == []


def test_amendment_and_reconciliation_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(role_hydration, "_amendment_is_effective", lambda _root: False)
    assert "H003_AMENDMENT_NOT_EFFECTIVE" in check()


def test_founder_unknown_and_future_prepared_roles_are_denied() -> None:
    assert "H004_FOUNDER_NOT_HYDRATABLE" in check({**PACKET, "requested_role": "ROLE-FOUNDER"})
    assert "H008_UNKNOWN_ROLE_OR_PROFILE" in check({**PACKET, "requested_role": "ROLE-INVENTED"})
    registry = copy.deepcopy(REGISTRY)
    registry["roles"].append({"id": "ROLE-FUTURE", "status": "prepared"})
    assert "H024_NONCANONICAL_REGISTRY" in check(
        {**PACKET, "requested_role": "ROLE-FUTURE"}, registry
    )


def test_missing_packet_fields_fail_closed() -> None:
    for field in list(PACKET):
        packet = dict(PACKET)
        packet.pop(field)
        assert any(e.startswith("H002_MISSING_FIELDS") for e in check(packet))


def test_trial_expiry_program_closure_and_revocation_deny() -> None:
    assert "H012_TRIAL_EXPIRED" in check(evaluated_on=date(2027, 2, 1))
    assert "H012_TRIAL_EXPIRED" in check(program_open=False)
    assert "H009_TRIAL_REVOKED" in check(founder_revoked=True)


def test_registry_lifecycle_conflict_denies_research() -> None:
    registry = copy.deepcopy(REGISTRY)
    next(r for r in registry["roles"] if r["id"] == "ROLE-RESEARCH")["status"] = "prepared"
    assert "H024_NONCANONICAL_REGISTRY" in check(
        {**PACKET, "requested_role": "ROLE-RESEARCH"}, registry
    )


def test_only_approved_exact_head_independent_profile_is_allowed() -> None:
    review = {
        **PACKET,
        "requested_role": "INDEPENDENT-REVIEWER-v1",
        "repository_ref": f"pr/560@{'a' * 40}",
        "exact_head_sha": "a" * 40,
        "independence_statement": "fresh instance; not author or assigner",
        "prohibited_actions": ["edit", "commit", "push", "merge", "deploy"],
    }
    assert check(review) == []
    assert "H005_EXACT_HEAD_REQUIRED" in check(
        {k: v for k, v in review.items() if k != "exact_head_sha"}
    )
    assert "H006_INDEPENDENCE_REQUIRED" in check(
        {k: v for k, v in review.items() if k != "independence_statement"}
    )
    bad = {**review, "prohibited_actions": ["merge", "deploy"]}
    assert "H007_REVIEWER_PROHIBITIONS_REQUIRED" in check(bad)


def test_hydration_never_grants_merge_deploy_product_governance_or_broker_authority() -> None:
    for action in (
        "merge",
        "deploy",
        "set_product_direction",
        "modify_governance",
        "live_broker_mutation",
    ):
        packet = {**PACKET, "permitted_actions": ["read", action]}
        assert "H015_AUTHORITY_EXPANSION" in check(packet)


def test_hydration_cannot_manage_or_reprioritize_permanent_role() -> None:
    for purpose in ("reprioritize roadmap", "manage permanent role"):
        assert "H016_NOT_BOUNDED_CONSULTATION" in check({**PACKET, "purpose": purpose})


def test_new_sha_requires_new_independent_review_packet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = {
        **PACKET,
        "requested_role": "INDEPENDENT-REVIEWER-v1",
        "repository_ref": f"pr/560@{'a' * 40}",
        "exact_head_sha": "a" * 40,
        "independence_statement": "distinct instance",
        "prohibited_actions": ["edit", "commit", "push", "merge", "deploy"],
    }
    second = {**first, "exact_head_sha": "b" * 40, "repository_ref": f"pr/560@{'b' * 40}"}
    assert check(first) == []
    monkeypatch.setattr(role_hydration, "_trusted_target_head", lambda _root, _ref: "b" * 40)
    assert "H017_STALE_EXACT_HEAD" in check(first)
    assert check(second) == []


def test_missing_rehydration_and_canonical_artifacts_fail_closed(tmp_path: Path) -> None:
    root = committed_fixture_repo(tmp_path)
    (root / "roles/manager/INSTRUCTIONS.md").unlink()
    subprocess.run(["git", "add", "-u"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "remove artifact"], cwd=root, check=True)
    assert any(
        error.startswith("H019_REHYDRATION_ARTIFACT_MISSING") for error in check(repo_root=root)
    )
    packet = {**PACKET, "canonical_artifacts": ["does/not/exist.md"]}
    assert "H021_CANONICAL_ARTIFACT_MISSING" in check(packet)


def test_repository_paths_cannot_escape_by_traversal_or_symlink(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-role-artifact.md"
    outside.write_text("outside")
    packet = {**PACKET, "canonical_artifacts": [f"../{outside.name}"]}
    assert "H021_CANONICAL_ARTIFACT_MISSING" in check(packet, repo_root=tmp_path)
    root = tmp_path / "repo"
    root.mkdir()
    (root / "escape").symlink_to(outside)
    assert "H021_CANONICAL_ARTIFACT_MISSING" in check(
        {**PACKET, "canonical_artifacts": ["escape"]}, repo_root=root
    )


def test_cross_role_authority_requests_are_denied() -> None:
    cases = (
        ("ROLE-PM", "define_architecture"),
        ("ROLE-ARCH", "sequence_work"),
        ("ROLE-RESEARCH", "set_roadmap_priority"),
    )
    for role, action in cases:
        packet = {**PACKET, "requested_role": role, "permitted_actions": ["read", action]}
        assert "H020_ACTION_OUTSIDE_ROLE_AUTHORITY" in check(packet)


def test_caller_cannot_expand_canonical_registry_authority() -> None:
    registry = copy.deepcopy(REGISTRY)
    pm = next(r for r in registry["roles"] if r["id"] == "ROLE-PM")
    pm["hydration_actions"].append("define_architecture")
    errors = check(
        {**PACKET, "permitted_actions": ["read", "define_architecture"]}, registry
    )
    assert "H024_NONCANONICAL_REGISTRY" in errors
    assert "H020_ACTION_OUTSIDE_ROLE_AUTHORITY" in errors


def test_nonexistent_lifecycle_anchor_is_denied(tmp_path: Path) -> None:
    root = committed_fixture_repo(tmp_path)
    registry_path = root / "project/roles/registry.yaml"
    registry = yaml.safe_load(registry_path.read_text())
    pm = next(r for r in registry["roles"] if r["id"] == "ROLE-PM")
    pm["lifecycle_authority"] = "governance/amendments/GOV-AMD-018.md#nonexistent"
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False))
    subprocess.run(["git", "add", str(registry_path)], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "bad anchor"], cwd=root, check=True)
    errors = check(PACKET, registry, repo_root=root)
    assert "H023_LIFECYCLE_AUTHORITY_MISSING" in errors
    assert "H025_LIFECYCLE_AUTHORITY_CONFLICT" in errors


def test_uncommitted_authority_mutation_cannot_expand_actions(tmp_path: Path) -> None:
    root = committed_fixture_repo(tmp_path)
    registry = yaml.safe_load((root / "project/roles/registry.yaml").read_text())
    authority_path = root / "governance/role-hydration-authority.yaml"
    authority = yaml.safe_load(authority_path.read_text())
    pm = next(r for r in authority["roles"] if r["id"] == "ROLE-PM")
    pm["allowed_actions"].append("define_architecture")
    authority_path.write_text(yaml.safe_dump(authority, sort_keys=False))
    errors = check(
        {**PACKET, "permitted_actions": ["read", "define_architecture"]},
        registry,
        repo_root=root,
    )
    assert "H020_ACTION_OUTSIDE_ROLE_AUTHORITY" in errors


def test_trusted_target_rejects_nonexistent_or_wrong_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(role_hydration, "_git", lambda *_args: None)
    assert REAL_TRUSTED_TARGET_HEAD(ROOT, f"pr/999@{'a' * 40}") is None
    assert REAL_TRUSTED_TARGET_HEAD(ROOT, f"branch/x@{'a' * 40}") is None


def test_effectiveness_requires_default_branch_containment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def not_merged(_root: Path, *args: str) -> str | None:
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("rev-parse", "refs/remotes/origin/main"):
            return "b" * 40
        return None

    monkeypatch.setattr(role_hydration, "_git", not_merged)
    assert not REAL_AMENDMENT_IS_EFFECTIVE(ROOT)

    def merged(_root: Path, *args: str) -> str | None:
        if args[0] == "rev-parse":
            return "a" * 40
        if args[:2] == ("merge-base", "--is-ancestor"):
            return ""
        if args[0] == "log":
            return "c" * 40
        if args[:3] == ("remote", "get-url", "origin"):
            return "https://github.com/jaiaFoster/ASA.git"
        return REAL_GIT(_root, *args)

    monkeypatch.setattr(role_hydration, "_git", merged)
    reviewed_head = "d" * 40

    def review_comment(
        lens: str,
        reviewer: str,
        comment_id: int,
        *,
        disposition: str = "PASS",
        created_at: str = "2026-10-09T23:00:00Z",
    ) -> dict[str, object]:
        record: dict[str, object] = {
            "schema": "asa.r5.review.v1",
            "lens": lens,
            "disposition": disposition,
            "exact_head_sha": reviewed_head,
            "reviewer_instance": reviewer,
        }
        if lens == "independent":
            record.update(
                {
                    "profile": "INDEPENDENT-REVIEWER-v1",
                    "independence_statement": "distinct from author and assigner",
                    "author_instance": "/root",
                    "assigner_instance": "/root",
                }
            )
        return {
            "id": comment_id,
            "created_at": created_at,
            "body": (
                f"{role_hydration.R5_REVIEW_MARKER}\n```json\n"
                f"{json.dumps(record, sort_keys=True)}\n```"
            ),
        }

    pass_comments = [
        review_comment("independent", "/root/reviewer-i", 1),
        review_comment("structural", "/root/reviewer-s", 2),
        review_comment("constitutional", "/root/reviewer-c", 3),
    ]
    monkeypatch.setattr(
        role_hydration,
        "_github_json",
        lambda _root, endpoint: (
            [{
                "number": 564,
                "merged_at": "2026-10-10T00:00:00Z",
                "merged_by": {"login": "jaiaFoster"},
                "head": {"sha": reviewed_head},
            }]
            if endpoint.endswith("/pulls")
            else pass_comments
        ),
    )
    assert REAL_AMENDMENT_IS_EFFECTIVE(ROOT)

    quoted = {
        "id": 4,
        "created_at": "2026-10-09T23:30:00Z",
        "body": "HOLD quoting Independent R5: PASS and other desired text",
    }
    monkeypatch.setattr(
        role_hydration,
        "_github_json",
        lambda _root, endpoint: (
            [{
                "number": 564,
                "merged_at": "2026-10-10T00:00:00Z",
                "merged_by": {"login": "jaiaFoster"},
                "head": {"sha": reviewed_head},
            }]
            if endpoint.endswith("/pulls")
            else [quoted]
        ),
    )
    assert not REAL_AMENDMENT_IS_EFFECTIVE(ROOT)

    superseding_hold = review_comment(
        "structural",
        "/root/reviewer-s",
        5,
        disposition="HOLD",
        created_at="2026-10-09T23:45:00Z",
    )
    monkeypatch.setattr(
        role_hydration,
        "_github_json",
        lambda _root, endpoint: (
            [{
                "number": 564,
                "merged_at": "2026-10-10T00:00:00Z",
                "merged_by": {"login": "jaiaFoster"},
                "head": {"sha": reviewed_head},
            }]
            if endpoint.endswith("/pulls")
            else [*pass_comments, superseding_hold]
        ),
    )
    assert not REAL_AMENDMENT_IS_EFFECTIVE(ROOT)

    post_merge = [
        review_comment(
            lens,
            f"/root/post-{lens}",
            10 + index,
            created_at="2026-10-10T00:01:00Z",
        )
        for index, lens in enumerate(("independent", "structural", "constitutional"))
    ]
    monkeypatch.setattr(
        role_hydration,
        "_github_json",
        lambda _root, endpoint: (
            [{
                "number": 564,
                "merged_at": "2026-10-10T00:00:00Z",
                "merged_by": {"login": "jaiaFoster"},
                "head": {"sha": reviewed_head},
            }]
            if endpoint.endswith("/pulls")
            else post_merge
        ),
    )
    assert not REAL_AMENDMENT_IS_EFFECTIVE(ROOT)


def test_independent_profile_must_exist_and_sha_must_be_well_formed(tmp_path: Path) -> None:
    review = {
        **PACKET,
        "requested_role": "INDEPENDENT-REVIEWER-v1",
        "repository_ref": "pr/560@x",
        "exact_head_sha": "x",
        "independence_statement": "distinct instance",
        "prohibited_actions": ["edit", "commit", "push", "merge", "deploy"],
    }
    assert "H005_EXACT_HEAD_REQUIRED" in check(review, repo_root=tmp_path)
    review["exact_head_sha"] = "a" * 40
    review["repository_ref"] = f"pr/560@{'a' * 40}"
    errors = check(review, repo_root=tmp_path)
    assert "H018_REVIEW_PROFILE_UNAVAILABLE" in errors


def test_gateway_requires_pm_or_arch_and_fixed_disposition() -> None:
    record = {
        "gatekeeper": "ROLE-PM",
        "candidate_id": "CB-1",
        "candidate_class": "implementation_defect",
        "disposition": "LOCAL_BLOCKER",
        "canonical_authority": "GOV-AMD-018 §5",
        "affected_path_state": "stopped",
        "unaffected_work_state": "continuing",
        "continuation_guidance": "correct locally",
    }
    assert validate_gateway_disposition(record) == []
    assert "G003_INVALID_GATEKEEPER" in validate_gateway_disposition(
        {**record, "gatekeeper": "ROLE-WORKER"}
    )
    assert "G004_INVALID_DISPOSITION" in validate_gateway_disposition(
        {**record, "disposition": "MAYBE"}
    )


def test_gateway_rejects_routine_failure_as_unconfirmed() -> None:
    record = {
        "gatekeeper": "ROLE-ARCH",
        "candidate_id": "test-failure",
        "candidate_class": "test_failure",
        "disposition": "NOT_A_FOUNDER_BLOCKER",
        "canonical_authority": "GOV-AMD-018 §5.5",
        "affected_path_state": "correction",
        "unaffected_work_state": "continuing",
        "continuation_guidance": "fix test and continue",
    }
    assert validate_gateway_disposition(record) == []


def test_paid_vendor_or_protected_contract_can_be_confirmed_by_correct_gatekeeper() -> None:
    for gatekeeper, candidate in (("ROLE-PM", "paid-vendor"), ("ROLE-ARCH", "breaking-contract")):
        record = {
            "gatekeeper": gatekeeper,
            "candidate_id": candidate,
            "candidate_class": "paid_vendor_or_legal_commitment"
            if gatekeeper == "ROLE-PM"
            else "governance_or_constitutional_change",
            "disposition": "CONFIRMED_FOUNDER_BLOCKER",
            "canonical_authority": "GOV-AMD-018 §5.5",
            "affected_path_state": "stopped",
            "unaffected_work_state": "continuing",
            "blocked_action": candidate,
            "decision_class": candidate,
            "founder_only_reason": "explicit Founder-only class",
            "verified_evidence": ["issue"],
            "attempted_resolutions": ["none available"],
            "alternatives": ["defer"],
            "safe_default": "do not proceed",
            "smallest_founder_decision": "approve or decline",
        }
        assert validate_gateway_disposition(record) == []


def test_incomplete_confirmed_blocker_and_unstopped_path_fail_closed() -> None:
    record = {
        "gatekeeper": "ROLE-PM",
        "candidate_id": "paid-vendor",
        "candidate_class": "paid_vendor_or_legal_commitment",
        "disposition": "CONFIRMED_FOUNDER_BLOCKER",
        "canonical_authority": "GOV-AMD-018 §5.5",
        "affected_path_state": "continuing",
        "unaffected_work_state": "continuing",
    }
    errors = validate_gateway_disposition(record)
    assert any(error.startswith("G010_INCOMPLETE_CONFIRMED_PACKET") for error in errors)
    assert "G011_PROTECTED_PATH_NOT_STOPPED" in errors


def test_local_or_not_founder_disposition_requires_continuation_guidance() -> None:
    record = {
        "gatekeeper": "ROLE-ARCH",
        "candidate_id": "ordinary-failure",
        "candidate_class": "test_failure",
        "disposition": "NOT_A_FOUNDER_BLOCKER",
        "canonical_authority": "GOV-AMD-018 §5.5",
        "affected_path_state": "correction",
        "unaffected_work_state": "continuing",
    }
    assert "G012_CONTINUATION_GUIDANCE_REQUIRED" in validate_gateway_disposition(record)


def test_routine_failure_cannot_be_confirmed_as_founder_blocker() -> None:
    record = {
        "gatekeeper": "ROLE-PM",
        "candidate_id": "ci",
        "candidate_class": "test_failure",
        "disposition": "CONFIRMED_FOUNDER_BLOCKER",
        "canonical_authority": "GOV-AMD-018 §5.5",
        "affected_path_state": "stopped",
        "unaffected_work_state": "continuing",
        "blocked_action": "merge",
        "decision_class": "test_failure",
        "founder_only_reason": "claimed",
        "verified_evidence": ["ci"],
        "attempted_resolutions": ["rerun"],
        "alternatives": ["fix"],
        "safe_default": "stop",
        "smallest_founder_decision": "waive",
    }
    errors = validate_gateway_disposition(record)
    assert "G013_ROUTINE_FAILURE_CANNOT_BE_CONFIRMED" in errors
    assert "G014_UNKNOWN_FOUNDER_ONLY_CLASS" in errors


def test_founder_only_class_cannot_be_dismissed_by_arbitrary_citation() -> None:
    record = {
        "gatekeeper": "ROLE-PM",
        "candidate_id": "vendor",
        "candidate_class": "paid_vendor_or_legal_commitment",
        "disposition": "NOT_A_FOUNDER_BLOCKER",
        "canonical_authority": "arbitrary",
        "affected_path_state": "stopped",
        "unaffected_work_state": "continuing",
        "continuation_guidance": "buy it",
    }
    assert "G015_FOUNDER_ONLY_CLASS_CANNOT_BE_DISMISSED" in validate_gateway_disposition(record)


def test_conflicted_gatekeeper_routes_to_other() -> None:
    base = {
        "gatekeeper": "ROLE-PM",
        "candidate_id": "c",
        "candidate_class": "implementation_defect",
        "disposition": "LOCAL_BLOCKER",
        "canonical_authority": "GOV-AMD-018 §5.4.1",
        "affected_path_state": "stopped",
        "unaffected_work_state": "continuing",
        "gatekeeper_conflicted": True,
        "continuation_guidance": "route to other gatekeeper",
    }
    assert "G005_CONFLICTED_GATEKEEPER" in validate_gateway_disposition(base)
    assert validate_gateway_disposition({**base, "routed_to_other_gatekeeper": True}) == []


def test_disagreement_stops_path_and_forwards_narrow_conflict() -> None:
    record = {
        "gatekeeper": "ROLE-ARCH",
        "candidate_id": "d",
        "candidate_class": "implementation_defect",
        "disposition": "LOCAL_BLOCKER",
        "canonical_authority": "GOV-AMD-018 §5.4.1",
        "affected_path_state": "stopped",
        "unaffected_work_state": "continuing",
        "gatekeepers_disagree": True,
        "continuation_guidance": "keep protected path stopped",
    }
    assert "G006_DISAGREEMENT_FAILSAFE_REQUIRED" in validate_gateway_disposition(record)
    assert validate_gateway_disposition({**record, "narrow_conflict_forwarded": True}) == []


def test_gateway_unavailable_is_durable_and_fail_closed() -> None:
    record = {
        "gatekeeper": "ROLE-PM",
        "candidate_id": "u",
        "candidate_class": "implementation_defect",
        "disposition": "LOCAL_BLOCKER",
        "canonical_authority": "GOV-AMD-018 §5.4.1",
        "affected_path_state": "stopped",
        "unaffected_work_state": "continuing",
        "gateway_available": False,
        "gateway_state": "FOUNDER_GATEWAY_UNAVAILABLE",
        "continuation_guidance": "record unavailable state",
    }
    assert validate_gateway_disposition(record) == []


def test_repeat_challenge_needs_new_canonical_evidence() -> None:
    record = {
        "gatekeeper": "ROLE-ARCH",
        "candidate_id": "r",
        "candidate_class": "implementation_defect",
        "disposition": "LOCAL_BLOCKER",
        "canonical_authority": "GOV-AMD-018 §5.4.1",
        "affected_path_state": "stopped",
        "unaffected_work_state": "continuing",
        "challenge_count": 2,
        "continuation_guidance": "deny repeat challenge",
    }
    assert "G008_REPEAT_CHALLENGE_DENIED" in validate_gateway_disposition(record)
    assert validate_gateway_disposition({**record, "new_canonical_evidence": True}) == []


def test_both_conflicted_gatekeepers_forward_only_narrow_conflict() -> None:
    record = {
        "gatekeeper": "ROLE-PM",
        "candidate_id": "bc",
        "candidate_class": "implementation_defect",
        "disposition": "LOCAL_BLOCKER",
        "canonical_authority": "GOV-AMD-018 §5.4.1",
        "affected_path_state": "stopped",
        "unaffected_work_state": "continuing",
        "both_gatekeepers_conflicted": True,
        "continuation_guidance": "forward narrow conflict only",
    }
    assert "G009_BOTH_CONFLICTED_FORWARD_ONLY" in validate_gateway_disposition(record)
    assert validate_gateway_disposition({**record, "narrow_conflict_forwarded": True}) == []


def test_canonical_compilations_preserve_gateway_and_review_separation() -> None:
    boundaries = (ROOT / "roles/shared/AUTHORITY_BOUNDARIES.md").read_text()
    handoff = (ROOT / "roles/shared/HANDOFF_PROTOCOL.md").read_text()
    risk = (ROOT / "roles/shared/RISK_SCALED_PROCESS.md").read_text()
    assert "Only those gatekeepers may" in boundaries
    assert "Candidate Founder Blocker" in handoff
    assert "Architect review\ndoes not substitute" in risk


def test_registry_has_unique_ids_and_resolving_role_pointers() -> None:
    roles = REGISTRY["roles"]
    assert len({r["id"] for r in roles}) == len(roles)
    for role in roles:
        for key in ("specification", "instructions", "instantiation_prompt"):
            if role.get(key):
                assert (ROOT / role[key]).exists()
