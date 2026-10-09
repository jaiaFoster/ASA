"""Deterministic fail-closed checks for GOV-AMD-018 role hydration packets."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

REQUIRED_PACKET_FIELDS = frozenset(
    {
        "assignment_id",
        "requested_role",
        "purpose",
        "question",
        "repository_ref",
        "work_reference",
        "risk_class",
        "acceptance_criteria",
        "canonical_artifacts",
        "permitted_actions",
        "prohibited_actions",
        "expected_output",
        "termination_condition",
    }
)

GATEWAY_DISPOSITIONS = frozenset(
    {
        "NOT_A_FOUNDER_BLOCKER",
        "LOCAL_BLOCKER",
        "CONFIRMED_FOUNDER_BLOCKER",
    }
)

PROHIBITED_HYDRATED_ACTIONS = frozenset(
    {"merge", "deploy", "set_product_direction", "modify_governance", "live_broker_mutation"}
)

ROLE_ACTIONS = {
    "ROLE-PM": frozenset(
        {"read", "consult", "classify", "sequence_work", "assign_work", "record_disposition"}
    ),
    "ROLE-ARCH": frozenset(
        {
            "read",
            "consult",
            "classify",
            "define_architecture",
            "review_architecture",
            "set_acceptance_criteria",
            "record_disposition",
        }
    ),
    "ROLE-RESEARCH": frozenset(
        {
            "read",
            "consult",
            "research",
            "characterize_evidence",
            "manage_research_taxonomy",
            "record_disposition",
        }
    ),
}

CONFIRMED_BLOCKER_FIELDS = frozenset(
    {
        "blocked_action",
        "decision_class",
        "founder_only_reason",
        "verified_evidence",
        "attempted_resolutions",
        "alternatives",
        "safe_default",
        "smallest_founder_decision",
    }
)


def _roles_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    roles = registry.get("roles") if isinstance(registry, dict) else None
    if not isinstance(roles, list):
        return {}
    return {
        role["id"]: role
        for role in roles
        if isinstance(role, dict) and isinstance(role.get("id"), str)
    }


def validate_hydration_packet(
    packet: object,
    registry: dict[str, Any],
    *,
    evaluated_on: date,
    amendment_effective: bool,
    reconciliation_complete: bool,
    repo_root: Path,
    current_head_sha: str | None = None,
    program_open: bool = True,
    founder_revoked: bool = False,
) -> list[str]:
    """Return stable error codes. Empty means packet may be executed."""
    if not isinstance(packet, dict):
        return ["H001_INVALID_PACKET"]

    errors: list[str] = []
    missing = sorted(
        field
        for field in REQUIRED_PACKET_FIELDS
        if field not in packet or packet[field] in (None, "", [], {})
    )
    if missing:
        errors.append(f"H002_MISSING_FIELDS:{','.join(missing)}")

    if not amendment_effective or not reconciliation_complete:
        errors.append("H003_AMENDMENT_NOT_EFFECTIVE")

    permitted = set(packet.get("permitted_actions") or [])
    if permitted & PROHIBITED_HYDRATED_ACTIONS:
        errors.append("H015_AUTHORITY_EXPANSION")
    purpose = str(packet.get("purpose", "")).lower()
    if "reprioritize" in purpose or "manage permanent role" in purpose:
        errors.append("H016_NOT_BOUNDED_CONSULTATION")

    target = packet.get("requested_role")
    if target == "ROLE-FOUNDER":
        errors.append("H004_FOUNDER_NOT_HYDRATABLE")
        return errors

    if target == "INDEPENDENT-REVIEWER-v1":
        exact_head = packet.get("exact_head_sha")
        if not isinstance(exact_head, str) or re.fullmatch(r"[0-9a-f]{40}", exact_head) is None:
            errors.append("H005_EXACT_HEAD_REQUIRED")
        elif current_head_sha is None or exact_head != current_head_sha:
            errors.append("H017_STALE_EXACT_HEAD")
        if not packet.get("independence_statement"):
            errors.append("H006_INDEPENDENCE_REQUIRED")
        forbidden = set(packet.get("prohibited_actions") or [])
        if not {"edit", "commit", "push", "merge", "deploy"} <= forbidden:
            errors.append("H007_REVIEWER_PROHIBITIONS_REQUIRED")
        profile = repo_root / "governance/execution-profiles/INDEPENDENT-REVIEWER-v1.md"
        if not profile.is_file() or "| `status` | Accepted" not in profile.read_text():
            errors.append("H018_REVIEW_PROFILE_UNAVAILABLE")
        return errors

    role = _roles_by_id(registry).get(target)
    if role is None:
        errors.append("H008_UNKNOWN_ROLE_OR_PROFILE")
        return errors

    for field in ("specification", "instructions", "instantiation_prompt"):
        value = role.get(field)
        if not isinstance(value, str) or not (repo_root / value).is_file():
            errors.append(f"H019_REHYDRATION_ARTIFACT_MISSING:{field}")

    allowed_actions = ROLE_ACTIONS.get(str(target), frozenset())
    if not permitted <= allowed_actions:
        errors.append("H020_ACTION_OUTSIDE_ROLE_AUTHORITY")

    for artifact in packet.get("canonical_artifacts") or []:
        if (
            not isinstance(artifact, str)
            or artifact.startswith("/")
            or not (repo_root / artifact).is_file()
        ):
            errors.append("H021_CANONICAL_ARTIFACT_MISSING")

    if founder_revoked:
        errors.append("H009_TRIAL_REVOKED")

    if target in {"ROLE-PM", "ROLE-ARCH"}:
        trial = role.get("hydration_trial")
        if not isinstance(trial, dict) or trial.get("authorized_by") != "GOV-AMD-018":
            errors.append("H010_TRIAL_NOT_AUTHORIZED")
        else:
            try:
                expires = date.fromisoformat(str(trial.get("expires_at")))
            except ValueError:
                errors.append("H011_INVALID_TRIAL_EXPIRY")
            else:
                if evaluated_on > expires or not program_open:
                    errors.append("H012_TRIAL_EXPIRED")
    elif target == "ROLE-RESEARCH":
        if role.get("status") != "trial" or "GOV-AMD-017" not in str(
            role.get("lifecycle_authority", "")
        ):
            errors.append("H013_LIFECYCLE_CONFLICT")
    elif role.get("status") != "active":
        errors.append("H014_ROLE_NOT_HYDRATABLE")

    return errors


def validate_gateway_disposition(record: object) -> list[str]:
    """Validate a durable GOV-AMD-018 gatekeeper disposition."""
    if not isinstance(record, dict):
        return ["G001_INVALID_GATEWAY_RECORD"]
    required = {
        "gatekeeper",
        "candidate_id",
        "disposition",
        "canonical_authority",
        "affected_path_state",
        "unaffected_work_state",
    }
    missing = sorted(k for k in required if record.get(k) in (None, "", [], {}))
    errors = [f"G002_MISSING_FIELDS:{','.join(missing)}"] if missing else []
    if record.get("gatekeeper") not in {"ROLE-PM", "ROLE-ARCH"}:
        errors.append("G003_INVALID_GATEKEEPER")
    if record.get("disposition") not in GATEWAY_DISPOSITIONS:
        errors.append("G004_INVALID_DISPOSITION")
    if record.get("disposition") == "CONFIRMED_FOUNDER_BLOCKER":
        missing_confirmed = sorted(
            field for field in CONFIRMED_BLOCKER_FIELDS if record.get(field) in (None, "", [], {})
        )
        if missing_confirmed:
            errors.append(f"G010_INCOMPLETE_CONFIRMED_PACKET:{','.join(missing_confirmed)}")
        if record.get("affected_path_state") != "stopped":
            errors.append("G011_PROTECTED_PATH_NOT_STOPPED")
    if record.get("disposition") in {"NOT_A_FOUNDER_BLOCKER", "LOCAL_BLOCKER"} and not record.get(
        "continuation_guidance"
    ):
        errors.append("G012_CONTINUATION_GUIDANCE_REQUIRED")
    if record.get("gatekeeper_conflicted") and not record.get("routed_to_other_gatekeeper"):
        errors.append("G005_CONFLICTED_GATEKEEPER")
    if record.get("gatekeepers_disagree") and (
        record.get("affected_path_state") != "stopped"
        or not record.get("narrow_conflict_forwarded")
    ):
        errors.append("G006_DISAGREEMENT_FAILSAFE_REQUIRED")
    if record.get("gateway_available") is False and (
        record.get("gateway_state") != "FOUNDER_GATEWAY_UNAVAILABLE"
        or record.get("affected_path_state") != "stopped"
    ):
        errors.append("G007_UNAVAILABLE_FAILSAFE_REQUIRED")
    if int(record.get("challenge_count", 0)) > 1 and not record.get("new_canonical_evidence"):
        errors.append("G008_REPEAT_CHALLENGE_DENIED")
    if record.get("both_gatekeepers_conflicted") and not record.get("narrow_conflict_forwarded"):
        errors.append("G009_BOTH_CONFLICTED_FORWARD_ONLY")
    return errors
