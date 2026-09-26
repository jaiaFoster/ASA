"""Advisory evaluator for Research Sprint Delegation (GOV-AMD-001 Amendment 017, Part B).

It answers one mechanical question: may the named delegate merge this
research PR under this research-sprint activation, at this time?

It is advisory, per Amendment 005:
- it never merges;
- it grants no authority;
- `permitted` is necessary evidence, not sufficient evidence;
- the amendment text controls.

Default-deny. Every rule must pass, and malformed input is denied rather
than raised. Two repository facts cannot be checked here:
- whether the activation reached `main` through the Founder's personal merge;
- whether every enumerated ticket has already merged.

The delegate verifies both, as its startup checklist requires.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

AMENDMENT = "GOV-AMD-001-017"
DELEGATE_ROLE = "ROLE-RESEARCH"
RESEARCH_ROOT = "research/"
ACTIVE = "active"
STATUSES = ("proposed", ACTIVE, "completed", "stopped", "revoked")
MAXIMUM_DELEGATED_RISK = 1  # R0-R1 research artifacts only
DATA_SUFFIXES = frozenset({".md", ".yaml", ".yml", ".csv", ".json"})
REQUIRED_EXPIRY = frozenset(
    {"sprint_completes", "sprint_stops", "expires_at_passes", "Founder_revokes_delegation"}
)
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
    "project/",
    "docs/",
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
        # The library contract refers to Amendment 017 A.4; changing it is a
        # governance change, never a delegated research merge.
        "research/README.md",
    }
)


@dataclass(frozen=True)
class Decision:
    permitted: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _normal(path: Any) -> str | None:
    """Reject non-strings and absolute, parent-escaping, empty, or dot segments."""
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path:
        return None
    parts = path.split("/")
    # A trailing slash (directory prefix) yields one empty final part; allow only that.
    inner = parts[:-1] if parts[-1] == "" else parts
    if not inner or any(part in ("..", ".", "") for part in inner):
        return None
    return path


def _is_forbidden(path: str) -> bool:
    return path in FORBIDDEN_FILES or any(path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)


def _ticket_ids(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not value:
        return None
    if not all(isinstance(item, str) and item and item.strip() == item for item in value):
        return None
    return value if len(set(value)) == len(value) else None


def _expiry_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def validate_activation(activation: Any) -> list[str]:
    """Structural validity of a research-sprint activation record."""
    if not isinstance(activation, dict):
        return ["A000 activation must be a mapping"]
    errors: list[str] = []
    if activation.get("governance_amendment") != AMENDMENT:
        errors.append(f"A001 governance_amendment must be {AMENDMENT}")
    if activation.get("sprint_type") != "research":
        errors.append("A002 sprint_type must be 'research'")
    sprint_id = activation.get("sprint_id")
    if not isinstance(sprint_id, str) or not sprint_id.strip() or "/" in sprint_id:
        errors.append("A003 sprint_id must be a non-empty path-safe string")
    if activation.get("founder_authorized") is not True:
        errors.append("A004 founder_authorized must be true")
    delegate = activation.get("delegate")
    if (
        not isinstance(delegate, dict)
        or delegate.get("role") != DELEGATE_ROLE
        or not isinstance(delegate.get("instance"), str)
        or not delegate["instance"].strip()
    ):
        errors.append("A005 delegate must name role ROLE-RESEARCH and an instance")
    if _ticket_ids(activation.get("approved_tickets")) is None:
        errors.append("A006 approved_tickets must be a non-empty list of unique, trimmed strings")
    scope = activation.get("scope")
    allowed = scope.get("allowed_paths") if isinstance(scope, dict) else None
    if not isinstance(allowed, list) or not allowed:
        errors.append("A007 scope.allowed_paths must be a non-empty list")
    else:
        for path in allowed:
            normal = _normal(path)
            if normal is None or not normal.startswith(RESEARCH_ROOT) or _is_forbidden(normal):
                errors.append(f"A008 allowed path outside delegable research scope: {path!r}")
            elif normal.rstrip("/") == RESEARCH_ROOT.rstrip("/"):
                errors.append("A008 allowed path may not be the whole research/ root")
    for key, code in (
        ("out_of_scope", "A009"),
        ("stop_conditions", "A010"),
        ("acceptance_criteria", "A011"),
    ):
        value = activation.get(key)
        if not isinstance(value, list) or not value:
            errors.append(f"{code} {key} must be a non-empty list")
    gates = activation.get("required_validation")
    if not isinstance(gates, list) or not set(map(str, gates)) >= REQUIRED_GATES:
        errors.append(f"A012 required_validation must include {sorted(REQUIRED_GATES)}")
    expiry = activation.get("expires")
    if not isinstance(expiry, list) or not set(map(str, expiry)) >= REQUIRED_EXPIRY:
        errors.append(f"A013 expires must include {sorted(REQUIRED_EXPIRY)}")
    if activation.get("status") not in STATUSES:
        errors.append(f"A014 status must be one of {STATUSES}")
    if _expiry_date(activation.get("expires_at")) is None:
        errors.append("A015 expires_at must be an ISO date")
    return errors


def _risk_number(value: Any) -> int | None:
    text = str(value or "").strip().upper()
    if len(text) == 2 and text[0] == "R" and text[1].isdigit():
        return int(text[1])
    return None


def closure_path(activation: dict[str, Any]) -> str:
    return f"research/sprints/{activation['sprint_id']}/CLOSURE.md"


def evaluate_merge(
    activation: Any,
    pull_request: Any,
    *,
    evaluated_on: date,
    repository_root: Path | None = None,
) -> Decision:
    """May the activation's delegate merge this research PR on `evaluated_on`?

    When `repository_root` (a checkout of current `main`) is given, a merged
    closure record ends the delegation mechanically. Default-deny throughout.
    """
    try:
        return _evaluate(activation, pull_request, evaluated_on, repository_root)
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        return Decision(False, (f"M000 malformed input: {type(error).__name__}",))


def _evaluate(
    activation: Any, pull_request: Any, evaluated_on: date, repository_root: Path | None
) -> Decision:
    reasons = list(validate_activation(activation))
    if not isinstance(pull_request, dict):
        reasons.append("M000 pull request record must be a mapping")
    if reasons:
        return Decision(False, tuple(reasons))
    if activation["status"] != ACTIVE:
        reasons.append(f"M001 delegation not active (status={activation['status']})")
    expires_at = _expiry_date(activation["expires_at"])
    if expires_at is None or evaluated_on > expires_at:
        reasons.append(f"M012 delegation expired on {activation['expires_at']}")
    if repository_root is not None and (repository_root / closure_path(activation)).exists():
        reasons.append("M013 sprint closure record is merged; the delegation has ended")
    delegate = activation["delegate"]
    if (
        pull_request.get("merged_by_role") != delegate["role"]
        or pull_request.get("merged_by_instance") != delegate["instance"]
    ):
        reasons.append("M002 merger is not the named delegate")
    ticket = pull_request.get("ticket")
    if not isinstance(ticket, str) or ticket not in activation["approved_tickets"]:
        reasons.append(f"M003 ticket {ticket!r} is not enumerated")
    allowed = [str(path) for path in activation["scope"]["allowed_paths"]]
    paths = pull_request.get("changed_paths")
    if not isinstance(paths, list) or not paths:
        reasons.append("M004 no changed paths declared")
        paths = []
    for path in paths:
        normal = _normal(path)
        if normal is None or normal.endswith("/"):
            reasons.append(f"M005 invalid path {path!r}")
        elif _is_forbidden(normal) or not normal.startswith(RESEARCH_ROOT):
            reasons.append(f"M006 path outside delegable research scope: {normal}")
        elif not any(
            normal == prefix or normal.startswith(prefix.rstrip("/") + "/") for prefix in allowed
        ):
            reasons.append(f"M007 path outside the sprint's allowed_paths: {normal}")
        elif PurePosixPath(normal).suffix.lower() not in DATA_SUFFIXES:
            reasons.append(f"M011 not a delegable data/document file: {normal}")
    risk = _risk_number(pull_request.get("risk_class"))
    if risk is None or risk > MAXIMUM_DELEGATED_RISK:
        reasons.append(f"M008 risk class {pull_request.get('risk_class')!r} exceeds delegable R1")
    if pull_request.get("self_review_recorded") is not True:
        reasons.append("M009 delegate self-review not recorded")
    gates = pull_request.get("gates")
    gates = gates if isinstance(gates, dict) else {}
    for gate in sorted(set(map(str, activation["required_validation"]))):
        if gates.get(gate) != "pass":
            reasons.append(f"M010 gate {gate} is {gates.get(gate, 'missing')!r}")
    return Decision(not reasons, tuple(reasons))


def main(argv: list[str] | None = None) -> int:
    """`research_delegation.py <sprint.yaml> [--pr <pr.yaml> [--on YYYY-MM-DD]]`.

    With only a sprint file, validate its activation. With `--pr`, evaluate that
    PR record against the activation, as of `--on` (default: today), against the
    current checkout (a merged closure record ends the delegation).
    """
    args = list(argv if argv is not None else sys.argv[1:])
    usage = "usage: research_delegation.py <sprint.yaml> [--pr <pr.yaml> [--on YYYY-MM-DD]]"
    if len(args) not in (1, 3, 5) or (len(args) >= 3 and args[1] != "--pr"):
        print(usage)
        return 2
    if len(args) == 5 and args[3] != "--on":
        print(usage)
        return 2
    data = yaml.safe_load(Path(args[0]).read_text(encoding="utf-8"))
    activation = data.get("activation") if isinstance(data, dict) else None
    errors = validate_activation(activation)
    for error in errors:
        print(error)
    if len(args) >= 3:
        pull_request = yaml.safe_load(Path(args[2]).read_text(encoding="utf-8"))
        on = date.fromisoformat(args[4]) if len(args) == 5 else date.today()
        decision = evaluate_merge(
            activation, pull_request, evaluated_on=on, repository_root=Path.cwd()
        )
        for reason in decision.reasons:
            if reason not in errors:
                print(reason)
        print("PERMITTED: delegated merge gates satisfied" if decision.permitted else "DENIED")
        return 0 if decision.permitted else 1
    print("OK: research sprint activation is structurally valid" if not errors else "FAIL")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
