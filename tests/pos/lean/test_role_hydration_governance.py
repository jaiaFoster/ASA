"""GOV-AMD-018 hydration, reviewer, lifecycle, and gateway regressions."""

from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

import yaml

from tools.pos.lean.role_hydration import (
    validate_gateway_disposition,
    validate_hydration_packet,
)

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


def check(packet=PACKET, registry=REGISTRY, **kwargs):  # type: ignore[no-untyped-def]
    return validate_hydration_packet(
        packet,
        registry,
        evaluated_on=kwargs.pop("evaluated_on", TODAY),
        amendment_effective=kwargs.pop("amendment_effective", True),
        reconciliation_complete=kwargs.pop("reconciliation_complete", True),
        repo_root=kwargs.pop("repo_root", ROOT),
        current_head_sha=kwargs.pop("current_head_sha", None),
        **kwargs,
    )


def test_pm_and_arch_bounded_trials_are_hydratable() -> None:
    assert check() == []
    assert check({**PACKET, "requested_role": "ROLE-ARCH"}) == []


def test_research_governing_trial_is_hydratable() -> None:
    assert check({**PACKET, "requested_role": "ROLE-RESEARCH"}) == []


def test_amendment_and_reconciliation_fail_closed() -> None:
    assert "H003_AMENDMENT_NOT_EFFECTIVE" in check(amendment_effective=False)
    assert "H003_AMENDMENT_NOT_EFFECTIVE" in check(reconciliation_complete=False)


def test_founder_unknown_and_future_prepared_roles_are_denied() -> None:
    assert "H004_FOUNDER_NOT_HYDRATABLE" in check({**PACKET, "requested_role": "ROLE-FOUNDER"})
    assert "H008_UNKNOWN_ROLE_OR_PROFILE" in check({**PACKET, "requested_role": "ROLE-INVENTED"})
    registry = copy.deepcopy(REGISTRY)
    registry["roles"].append({"id": "ROLE-FUTURE", "status": "prepared"})
    assert "H014_ROLE_NOT_HYDRATABLE" in check(
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
    assert "H013_LIFECYCLE_CONFLICT" in check(
        {**PACKET, "requested_role": "ROLE-RESEARCH"}, registry
    )


def test_only_approved_exact_head_independent_profile_is_allowed() -> None:
    review = {
        **PACKET,
        "requested_role": "INDEPENDENT-REVIEWER-v1",
        "exact_head_sha": "a" * 40,
        "independence_statement": "fresh instance; not author or assigner",
        "prohibited_actions": ["edit", "commit", "push", "merge", "deploy"],
    }
    assert check(review, current_head_sha="a" * 40) == []
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


def test_new_sha_requires_new_independent_review_packet() -> None:
    first = {
        **PACKET,
        "requested_role": "INDEPENDENT-REVIEWER-v1",
        "exact_head_sha": "a" * 40,
        "independence_statement": "distinct instance",
        "prohibited_actions": ["edit", "commit", "push", "merge", "deploy"],
    }
    second = {**first, "exact_head_sha": "b" * 40}
    assert check(first, current_head_sha="a" * 40) == []
    assert "H017_STALE_EXACT_HEAD" in check(first, current_head_sha="b" * 40)
    assert check(second, current_head_sha="b" * 40) == []


def test_missing_rehydration_and_canonical_artifacts_fail_closed(tmp_path: Path) -> None:
    assert any(
        error.startswith("H019_REHYDRATION_ARTIFACT_MISSING") for error in check(repo_root=tmp_path)
    )
    packet = {**PACKET, "canonical_artifacts": ["does/not/exist.md"]}
    assert "H021_CANONICAL_ARTIFACT_MISSING" in check(packet)


def test_cross_role_authority_requests_are_denied() -> None:
    cases = (
        ("ROLE-PM", "define_architecture"),
        ("ROLE-ARCH", "sequence_work"),
        ("ROLE-RESEARCH", "set_roadmap_priority"),
    )
    for role, action in cases:
        packet = {**PACKET, "requested_role": role, "permitted_actions": ["read", action]}
        assert "H020_ACTION_OUTSIDE_ROLE_AUTHORITY" in check(packet)


def test_independent_profile_must_exist_and_sha_must_be_well_formed(tmp_path: Path) -> None:
    review = {
        **PACKET,
        "requested_role": "INDEPENDENT-REVIEWER-v1",
        "exact_head_sha": "x",
        "independence_statement": "distinct instance",
        "prohibited_actions": ["edit", "commit", "push", "merge", "deploy"],
    }
    assert "H005_EXACT_HEAD_REQUIRED" in check(review, repo_root=tmp_path, current_head_sha="x")
    review["exact_head_sha"] = "a" * 40
    errors = check(review, repo_root=tmp_path, current_head_sha="a" * 40)
    assert "H018_REVIEW_PROFILE_UNAVAILABLE" in errors


def test_gateway_requires_pm_or_arch_and_fixed_disposition() -> None:
    record = {
        "gatekeeper": "ROLE-PM",
        "candidate_id": "CB-1",
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
        "disposition": "NOT_A_FOUNDER_BLOCKER",
        "canonical_authority": "GOV-AMD-018 §5.5",
        "affected_path_state": "correction",
        "unaffected_work_state": "continuing",
    }
    assert "G012_CONTINUATION_GUIDANCE_REQUIRED" in validate_gateway_disposition(record)


def test_conflicted_gatekeeper_routes_to_other() -> None:
    base = {
        "gatekeeper": "ROLE-PM",
        "candidate_id": "c",
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
