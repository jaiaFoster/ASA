"""ASA-ARCH-002 dependency and operational-boundary enforcement."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

from domain.execution import ExecutionPlan, PlannedOrder, PortfolioDelta, RiskDecision

REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTION_CONTRACT = REPO_ROOT / "domain" / "execution.py"


def _import_roots() -> set[str]:
    tree = ast.parse(EXECUTION_CONTRACT.read_text())
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_execution_contracts_depend_only_on_domain_and_standard_library() -> None:
    assert _import_roots() <= {
        "__future__",
        "dataclasses",
        "decimal",
        "domain",
        "enum",
    }


def test_no_operational_or_infrastructure_dependency_is_reachable() -> None:
    prohibited = {
        "backend",
        "brokers",
        "httpx",
        "infrastructure",
        "providers",
        "requests",
        "sqlalchemy",
    }
    assert not _import_roots() & prohibited


def test_execution_contracts_expose_no_callable_behavior() -> None:
    for cls in (PortfolioDelta, RiskDecision, ExecutionPlan, PlannedOrder):
        public = {
            name
            for name, value in vars(cls).items()
            if not name.startswith("_") and callable(value)
        }
        assert public == set()


def test_planned_order_is_not_an_adapter_or_api_payload() -> None:
    names = {field.name for field in dataclasses.fields(PlannedOrder)}
    prohibited = {
        "adapter",
        "api_url",
        "callback",
        "credentials",
        "endpoint",
        "provider_payload",
        "session",
        "token",
    }
    assert not names & prohibited
    assert "execution_plan_id" not in names
