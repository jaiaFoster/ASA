"""Advisory evaluator for Research Sprint Delegation (GOV-AMD-001 Amendment 017).

It answers one mechanical question: may the named delegate merge this research
PR under this research-sprint activation? The evaluator is advisory, per
Amendment 005. It never merges, it grants no authority, and a `permitted`
result is only necessary evidence, not sufficient evidence. The amendment
text controls.

Default-deny: every rule must pass. Merging is denied when any of these hold:
- the activation is missing, invalid, not Founder-authorized, not active, or
  expired. That the active file reached `main` through a Founder merge is a
  repository fact the delegate verifies; this evaluator cannot;
- the ticket is not enumerated;
- a path lies outside `research/` or inside a forbidden area;
- the risk class is above R1;
- self-review is missing;
- a required gate is not `pass`.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

AMENDMENT = "GOV-AMD-001-017"
DELEGATE_ROLE = "ROLE-RESEARCH"
RESEARCH_ROOT = "research/"
ACTIVE = "active"
STATUSES = ("proposed", ACTIVE, "completed", "stopped", "revoked")
MAXIMUM_DELEGATED_RISK = 1  # R0-R1 research artifacts only
REQUIRED_EXPIRY = frozenset({"sprint_completes", "sprint_stops", "Founder_revokes_delegation"})
REQUIRED_GATES = frozenset(
    {
        "required_ci_checks",
        "pos_validation",
        "research_library_validation",
        "frozen_governance_integrity",
        "scope_check",
        "no_governance_violation",
        "no_unresolved_blocking_issue",
    }
)
# Defense in depth: never delegable, even if an activation lists them.
FORBIDDEN_PREFIXES = (
    "governance/",
    "roles/",
    "project/roles/",
    "project/lean/",
    "docs/sprints/",
    "docs/adr/",
    "architecture/",
    ".github/",
    "asa/",
    "strategies/",
    "strategy_runtime/",
    "screening/",
    "market_data/",
    "domain/",
    "analytics/",
    "migrations/",
    "tools/",
    "tests/",
    "frontend/",
)
FORBIDDEN_FILES = frozenset(
    {
        "AGENTS.md",
        "CURRENT_STATE.md",
        "Dockerfile",
        "railway.json",
        "railway.cron.json",
        "pyproject.toml",
        "alembic.ini",
        # The library contract restates Amendment 017's qualification semantics;
        # changing it is a governance change, never a delegated research merge.
        "research/README.md",
    }
)


@dataclass(frozen=True)
class Decision:
    permitted: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _normal(path: str) -> str | None:
    """Reject absolute, parent-escaping, or empty paths."""
    if not path or path.startswith("/") or "\\" in path:
        return None
    parts = PurePosixPath(path).parts
    if any(part in ("..", "") for part in parts):
        return None
    return PurePosixPath(path).as_posix()


def _is_forbidden(path: str) -> bool:
    return path in FORBIDDEN_FILES or any(path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)


def validate_activation(activation: Any) -> list[str]:
    """Structural validity of a research-sprint activation record."""
    if not isinstance(activation, dict):
        return ["A000 activation must be a mapping"]
    errors: list[str] = []
    if activation.get("governance_amendment") != AMENDMENT:
        errors.append(f"A001 governance_amendment must be {AMENDMENT}")
    if activation.get("sprint_type") != "research":
        errors.append("A002 sprint_type must be 'research'")
    if not str(activation.get("sprint_id") or "").strip():
        errors.append("A003 sprint_id is required")
    if activation.get("founder_authorized") is not True:
        errors.append("A004 founder_authorized must be true")
    delegate = activation.get("delegate") or {}
    if delegate.get("role") != DELEGATE_ROLE or not str(delegate.get("instance") or "").strip():
        errors.append("A005 delegate must name role ROLE-RESEARCH and an instance")
    tickets = activation.get("approved_tickets")
    if not isinstance(tickets, list) or not tickets or len(set(tickets)) != len(tickets):
        errors.append("A006 approved_tickets must be a non-empty list of unique IDs")
    allowed = (activation.get("scope") or {}).get("allowed_paths")
    if not isinstance(allowed, list) or not allowed:
        errors.append("A007 scope.allowed_paths must be a non-empty list")
    else:
        for path in allowed:
            normal = _normal(str(path))
            if normal is None or not normal.startswith(RESEARCH_ROOT) or _is_forbidden(normal):
                errors.append(f"A008 allowed path outside research/: {path!r}")
    for key, code in (
        ("out_of_scope", "A009"),
        ("stop_conditions", "A010"),
        ("acceptance_criteria", "A011"),
    ):
        value = activation.get(key)
        if not isinstance(value, list) or not value:
            errors.append(f"{code} {key} must be a non-empty list")
    gates = set(activation.get("required_validation") or [])
    missing = REQUIRED_GATES - gates
    if missing:
        errors.append(f"A012 required_validation missing: {sorted(missing)}")
    expiry = set(activation.get("expires") or [])
    if not expiry >= REQUIRED_EXPIRY:
        errors.append(f"A013 expires must include {sorted(REQUIRED_EXPIRY)}")
    if activation.get("status") not in STATUSES:
        errors.append(f"A014 status must be one of {STATUSES}")
    return errors


def _risk_number(value: Any) -> int | None:
    text = str(value or "").strip().upper()
    if len(text) == 2 and text[0] == "R" and text[1].isdigit():
        return int(text[1])
    return None


def evaluate_merge(activation: Any, pull_request: dict[str, Any]) -> Decision:
    """May the activation's delegate merge this research PR? Default-deny."""
    reasons = list(validate_activation(activation))
    if not reasons:
        if activation["status"] != ACTIVE:
            reasons.append(f"M001 delegation not active (status={activation['status']})")
        delegate = activation["delegate"]
        if (
            pull_request.get("merged_by_role") != delegate["role"]
            or pull_request.get("merged_by_instance") != delegate["instance"]
        ):
            reasons.append("M002 merger is not the named delegate")
        if pull_request.get("ticket") not in activation["approved_tickets"]:
            reasons.append(f"M003 ticket {pull_request.get('ticket')!r} is not enumerated")
        allowed = [PurePosixPath(p).as_posix() for p in activation["scope"]["allowed_paths"]]
        paths = pull_request.get("changed_paths") or []
        if not paths:
            reasons.append("M004 no changed paths declared")
        for path in paths:
            normal = _normal(str(path))
            if normal is None:
                reasons.append(f"M005 invalid path {path!r}")
            elif _is_forbidden(normal) or not normal.startswith(RESEARCH_ROOT):
                reasons.append(f"M006 path outside delegable research scope: {normal}")
            elif not any(
                normal == prefix or normal.startswith(prefix.rstrip("/") + "/")
                for prefix in allowed
            ):
                reasons.append(f"M007 path outside the sprint's allowed_paths: {normal}")
        risk = _risk_number(pull_request.get("risk_class"))
        if risk is None or risk > MAXIMUM_DELEGATED_RISK:
            reasons.append(
                f"M008 risk class {pull_request.get('risk_class')!r} exceeds delegable R1"
            )
        if pull_request.get("self_review_recorded") is not True:
            reasons.append("M009 delegate self-review not recorded")
        gates = pull_request.get("gates") or {}
        for gate in sorted(set(activation["required_validation"])):
            if gates.get(gate) != "pass":
                reasons.append(f"M010 gate {gate} is {gates.get(gate, 'missing')!r}")
    return Decision(not reasons, tuple(reasons))


def main(argv: list[str] | None = None) -> int:
    """`research_delegation.py <sprint.yaml> [--pr <pr.yaml>]`.

    With only a sprint file, validate its activation. With `--pr`, also
    evaluate that PR record against the activation (default-deny).
    """
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) not in (1, 3) or (len(args) == 3 and args[1] != "--pr"):
        print("usage: research_delegation.py <research-sprint.yaml> [--pr <pr.yaml>]")
        return 2
    data = yaml.safe_load(Path(args[0]).read_text(encoding="utf-8"))
    activation = (data or {}).get("activation")
    errors = validate_activation(activation)
    for error in errors:
        print(error)
    if len(args) == 3:
        pull_request = yaml.safe_load(Path(args[2]).read_text(encoding="utf-8")) or {}
        decision = evaluate_merge(activation, pull_request)
        for reason in decision.reasons:
            if reason not in errors:
                print(reason)
        print("PERMITTED: delegated merge gates satisfied" if decision.permitted else "DENIED")
        return 0 if decision.permitted else 1
    print("OK: research sprint activation is structurally valid" if not errors else "FAIL")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
