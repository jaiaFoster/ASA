"""Deterministic fail-closed checks for GOV-AMD-018 role hydration packets."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import yaml

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
    {"NOT_A_FOUNDER_BLOCKER", "LOCAL_BLOCKER", "CONFIRMED_FOUNDER_BLOCKER"}
)
PROHIBITED_HYDRATED_ACTIONS = frozenset(
    {"merge", "deploy", "set_product_direction", "modify_governance", "live_broker_mutation"}
)
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
FOUNDER_ONLY_CLASSES = frozenset(
    {
        "paid_vendor_or_legal_commitment",
        "live_broker_authority_expansion",
        "founder_only_deployment",
        "destructive_irreversible_action",
        "governance_or_constitutional_change",
        "material_scope_expansion",
        "irreconcilable_authority_conflict",
    }
)
ROUTINE_CLASSES = frozenset(
    {
        "implementation_defect",
        "test_failure",
        "ci_failure",
        "required_review",
        "provider_or_data_unknown",
        "observation_wait",
    }
)
R5_REVIEW_MARKER = "<!-- asa-r5-review:v1 -->"


def _roles_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    roles = registry.get("roles") if isinstance(registry, dict) else None
    if not isinstance(roles, list):
        return {}
    return {
        role["id"]: role
        for role in roles
        if isinstance(role, dict) and isinstance(role.get("id"), str)
    }


def _git_file(repo_root: Path, relative_path: object) -> str | None:
    if not isinstance(relative_path, str) or not relative_path or relative_path.startswith("/"):
        return None
    path = relative_path.split("#", maxsplit=1)[0]
    if ".." in Path(path).parts:
        return None
    tree = _git(repo_root, "ls-tree", "HEAD", "--", path)
    if not tree or not tree.split(maxsplit=1)[0].startswith("100"):
        return None
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{path}"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout


def _load_yaml(repo_root: Path, relative_path: str) -> dict[str, Any] | None:
    text = _git_file(repo_root, relative_path)
    if text is None:
        return None
    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    return value if isinstance(value, dict) else None


def _git(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=repo_root, check=True, capture_output=True, text=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _github_json(repo_root: Path, endpoint: str) -> object | None:
    try:
        result = subprocess.run(
            ["gh", "api", endpoint],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def _anchor_exists(text: str, reference: str) -> bool:
    if "#" not in reference:
        return False
    anchor = reference.split("#", maxsplit=1)[1]
    headings = re.findall(r"^#{1,6}\s+(.+?)\s*$", text, flags=re.MULTILINE)
    slugs = {
        re.sub(r"[^a-z0-9 -]", "", heading.lower()).replace(" ", "-")
        for heading in headings
    }
    return anchor in slugs


def _canonical_roles(repo_root: Path) -> dict[str, dict[str, Any]]:
    registry = _load_yaml(repo_root, "project/roles/registry.yaml")
    return _roles_by_id(registry or {})


def _authority_by_role(repo_root: Path) -> dict[str, dict[str, Any]]:
    authority = _load_yaml(repo_root, "governance/role-hydration-authority.yaml")
    roles = authority.get("roles") if authority else None
    if not isinstance(roles, list):
        return {}
    return {
        item["id"]: item
        for item in roles
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def _amendment_is_effective(repo_root: Path) -> bool:
    state = _load_yaml(repo_root, "governance/effectiveness/GOV-AMD-018.yaml")
    if not state or state.get("status") != "effective_on_founder_merge":
        return False
    head = _git(repo_root, "rev-parse", "HEAD")
    default_head = _git(repo_root, "rev-parse", "refs/remotes/origin/main")
    if not head or not default_head:
        return False
    if _git(repo_root, "merge-base", "--is-ancestor", head, default_head) != "":
        return False
    activation_commit = _git(
        repo_root,
        "log",
        "-1",
        "--format=%H",
        "--diff-filter=A",
        "--",
        "governance/effectiveness/GOV-AMD-018.yaml",
    )
    remote = _git(repo_root, "remote", "get-url", "origin") or ""
    match = re.search(r"github\.com[/:]([^/]+)/([^/.]+)(?:\.git)?$", remote)
    if not activation_commit or match is None:
        return False
    owner, repository = match.groups()
    pulls = _github_json(repo_root, f"repos/{owner}/{repository}/commits/{activation_commit}/pulls")
    if not isinstance(pulls, list):
        return False
    founder = _canonical_roles(repo_root).get("ROLE-FOUNDER", {}).get("github_login")
    pull = next(
        (
            item
            for item in pulls
            if isinstance(item, dict)
            and item.get("merged_at")
            and isinstance(item.get("merged_by"), dict)
            and item["merged_by"].get("login") == founder
        ),
        None,
    )
    if not isinstance(pull, dict) or not isinstance(pull.get("number"), int):
        return False
    merged_at = pull.get("merged_at")
    if not isinstance(merged_at, str):
        return False
    pull_head = pull.get("head")
    reviewed_head = pull_head.get("sha") if isinstance(pull_head, dict) else None
    if not isinstance(reviewed_head, str):
        return False
    comments = _github_json(
        repo_root, f"repos/{owner}/{repository}/issues/{pull['number']}/comments?per_page=100"
    )
    if not isinstance(comments, list):
        return False
    latest: dict[str, tuple[tuple[str, int], dict[str, Any]]] = {}
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        body = comment.get("body")
        created_at = comment.get("created_at")
        comment_id = comment.get("id")
        if (
            not isinstance(body, str)
            or not body.startswith(f"{R5_REVIEW_MARKER}\n")
            or not isinstance(created_at, str)
            or created_at > merged_at
            or not isinstance(comment_id, int)
        ):
            continue
        match_record = re.fullmatch(
            rf"{re.escape(R5_REVIEW_MARKER)}\n```json\n(.+?)\n```\s*", body, flags=re.DOTALL
        )
        if match_record is None:
            continue
        try:
            record = json.loads(match_record.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        lens = record.get("lens")
        if (
            record.get("schema") != "asa.r5.review.v1"
            or lens not in {"independent", "structural", "constitutional"}
            or record.get("exact_head_sha") != reviewed_head
            or record.get("disposition") not in {"PASS", "HOLD"}
            or not isinstance(record.get("reviewer_instance"), str)
        ):
            continue
        key = (created_at, comment_id)
        if lens not in latest or key > latest[lens][0]:
            latest[lens] = (key, record)
    if set(latest) != {"independent", "structural", "constitutional"}:
        return False
    records = {lens: value[1] for lens, value in latest.items()}
    if any(record.get("disposition") != "PASS" for record in records.values()):
        return False
    instances = {str(record["reviewer_instance"]) for record in records.values()}
    if len(instances) != 3:
        return False
    independent = records["independent"]
    return (
        independent.get("profile") == "INDEPENDENT-REVIEWER-v1"
        and isinstance(independent.get("independence_statement"), str)
        and bool(independent["independence_statement"].strip())
        and independent.get("reviewer_instance") != independent.get("author_instance")
        and independent.get("reviewer_instance") != independent.get("assigner_instance")
    )


def _trusted_target_head(repo_root: Path, repository_ref: object) -> str | None:
    if not isinstance(repository_ref, str) or "@" not in repository_ref:
        return None
    target, claimed = repository_ref.rsplit("@", maxsplit=1)
    if re.fullmatch(r"[0-9a-f]{40}", claimed) is None:
        return None
    if target == "main":
        actual = _git(repo_root, "rev-parse", "refs/remotes/origin/main")
    elif re.fullmatch(r"pr/[1-9][0-9]*", target):
        number = target.split("/", maxsplit=1)[1]
        output = _git(repo_root, "ls-remote", "origin", f"refs/pull/{number}/head")
        actual = output.split()[0] if output else None
    else:
        actual = None
    return actual if actual == claimed else None


def _profile_is_active(repo_root: Path) -> bool:
    profile_rel = "governance/execution-profiles/INDEPENDENT-REVIEWER-v1.md"
    profile = _git_file(repo_root, profile_rel)
    manifest = _load_yaml(repo_root, "governance/manifest.yaml")
    if profile is None or manifest is None:
        return False
    try:
        documents = manifest["documents"]
    except (KeyError, TypeError):
        return False
    entry = next(
        (
            item
            for item in documents
            if isinstance(item, dict) and item.get("id") == "INDEPENDENT-REVIEWER-v1"
        ),
        None,
    )
    if not isinstance(entry, dict):
        return False
    return (
        entry.get("status") == "active"
        and entry.get("filename") == profile_rel
        and entry.get("sha256") == hashlib.sha256(profile.encode()).hexdigest()
        and "| `status` | Accepted" in profile
    )


def validate_hydration_packet(
    packet: object,
    registry: dict[str, Any],
    *,
    evaluated_on: date,
    repo_root: Path,
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
    canonical_roles = _canonical_roles(repo_root)
    supplied_roles = _roles_by_id(registry)
    if supplied_roles != canonical_roles:
        errors.append("H024_NONCANONICAL_REGISTRY")
    if not _amendment_is_effective(repo_root):
        errors.append("H003_AMENDMENT_NOT_EFFECTIVE")
    permitted = set(packet.get("permitted_actions") or [])
    if permitted & PROHIBITED_HYDRATED_ACTIONS:
        errors.append("H015_AUTHORITY_EXPANSION")
    purpose = str(packet.get("purpose", "")).lower()
    if "reprioritize" in purpose or "manage permanent role" in purpose:
        errors.append("H016_NOT_BOUNDED_CONSULTATION")
    if any(
        _git_file(repo_root, artifact) is None
        for artifact in packet.get("canonical_artifacts") or []
    ):
        errors.append("H021_CANONICAL_ARTIFACT_MISSING")

    target = packet.get("requested_role")
    if target == "ROLE-FOUNDER":
        errors.append("H004_FOUNDER_NOT_HYDRATABLE")
        return errors
    if target == "INDEPENDENT-REVIEWER-v1":
        exact_head = packet.get("exact_head_sha")
        if not isinstance(exact_head, str) or re.fullmatch(r"[0-9a-f]{40}", exact_head) is None:
            errors.append("H005_EXACT_HEAD_REQUIRED")
        elif _trusted_target_head(repo_root, packet.get("repository_ref")) != exact_head:
            errors.append("H017_STALE_EXACT_HEAD")
        if exact_head != str(packet.get("repository_ref", "")).rsplit("@", maxsplit=1)[-1]:
            errors.append("H022_REF_HEAD_MISMATCH")
        if not packet.get("independence_statement"):
            errors.append("H006_INDEPENDENCE_REQUIRED")
        if not {"edit", "commit", "push", "merge", "deploy"} <= set(
            packet.get("prohibited_actions") or []
        ):
            errors.append("H007_REVIEWER_PROHIBITIONS_REQUIRED")
        if not _profile_is_active(repo_root):
            errors.append("H018_REVIEW_PROFILE_UNAVAILABLE")
        return errors

    role = canonical_roles.get(target)
    if role is None:
        errors.append("H008_UNKNOWN_ROLE_OR_PROFILE")
        return errors
    if founder_revoked:
        errors.append("H009_TRIAL_REVOKED")
    for field in ("specification", "instructions", "instantiation_prompt"):
        if _git_file(repo_root, role.get(field)) is None:
            errors.append(f"H019_REHYDRATION_ARTIFACT_MISSING:{field}")
    lifecycle_text = _git_file(repo_root, role.get("lifecycle_authority"))
    if lifecycle_text is None or not _anchor_exists(
        lifecycle_text, str(role.get("lifecycle_authority", ""))
    ):
        errors.append("H023_LIFECYCLE_AUTHORITY_MISSING")
    authority = _authority_by_role(repo_root).get(str(target), {})
    if (
        authority.get("lifecycle_authority") != role.get("lifecycle_authority")
        or authority.get("required_registry_status") != role.get("status")
    ):
        errors.append("H025_LIFECYCLE_AUTHORITY_CONFLICT")
    configured_actions = authority.get("allowed_actions")
    allowed_actions = (
        frozenset(configured_actions)
        if isinstance(configured_actions, list)
        and all(isinstance(x, str) for x in configured_actions)
        else frozenset()
    )
    if not permitted <= allowed_actions:
        errors.append("H020_ACTION_OUTSIDE_ROLE_AUTHORITY")
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
        "candidate_class",
        "disposition",
        "canonical_authority",
        "affected_path_state",
        "unaffected_work_state",
    }
    missing = sorted(k for k in required if record.get(k) in (None, "", [], {}))
    errors = [f"G002_MISSING_FIELDS:{','.join(missing)}"] if missing else []
    disposition = record.get("disposition")
    candidate_class = record.get("candidate_class")
    if record.get("gatekeeper") not in {"ROLE-PM", "ROLE-ARCH"}:
        errors.append("G003_INVALID_GATEKEEPER")
    if disposition not in GATEWAY_DISPOSITIONS:
        errors.append("G004_INVALID_DISPOSITION")
    if disposition == "CONFIRMED_FOUNDER_BLOCKER":
        missing_confirmed = sorted(
            field for field in CONFIRMED_BLOCKER_FIELDS if record.get(field) in (None, "", [], {})
        )
        if missing_confirmed:
            errors.append(f"G010_INCOMPLETE_CONFIRMED_PACKET:{','.join(missing_confirmed)}")
        if record.get("affected_path_state") != "stopped":
            errors.append("G011_PROTECTED_PATH_NOT_STOPPED")
        if candidate_class in ROUTINE_CLASSES:
            errors.append("G013_ROUTINE_FAILURE_CANNOT_BE_CONFIRMED")
        if candidate_class not in FOUNDER_ONLY_CLASSES:
            errors.append("G014_UNKNOWN_FOUNDER_ONLY_CLASS")
    if disposition in {"NOT_A_FOUNDER_BLOCKER", "LOCAL_BLOCKER"}:
        if not record.get("continuation_guidance"):
            errors.append("G012_CONTINUATION_GUIDANCE_REQUIRED")
        if candidate_class in FOUNDER_ONLY_CLASSES:
            errors.append("G015_FOUNDER_ONLY_CLASS_CANNOT_BE_DISMISSED")
    if record.get("unaffected_work_state") not in {"continuing", "none_authorized"}:
        errors.append("G016_UNAFFECTED_WORK_MUST_CONTINUE")
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
