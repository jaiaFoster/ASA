"""SPRINT-012 semantic-ownership and canonical-authority guards."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from strategies import (
    EARNINGS_CALENDAR_MANIFEST,
    FORWARD_FACTOR_CALENDAR_MANIFEST,
    SKEW_MOMENTUM_VERTICAL_MANIFEST,
)
from strategy_runtime.adapters.earnings_calendar import EARNINGS_CALENDAR_CONTRACT
from strategy_runtime.adapters.forward_factor import FORWARD_FACTOR_CONTRACT
from strategy_runtime.adapters.skew_momentum_vertical import (
    SKEW_MOMENTUM_VERTICAL_CONTRACT,
)
from strategy_runtime.errors import StrategyContractError
from strategy_runtime.manifest_contract import validate_manifest_contract

REPO_ROOT = Path(__file__).resolve().parents[2]

PRODUCTION_DEFINITIONS = (
    (FORWARD_FACTOR_CALENDAR_MANIFEST, FORWARD_FACTOR_CONTRACT),
    (EARNINGS_CALENDAR_MANIFEST, EARNINGS_CALENDAR_CONTRACT),
    (SKEW_MOMENTUM_VERTICAL_MANIFEST, SKEW_MOMENTUM_VERTICAL_CONTRACT),
)

# Existing debt is frozen, not accepted. WS2 removes these names. This exact
# allowlist prevents semantic ownership from expanding while migration occurs.
KNOWN_SCREENING_SEMANTIC_DEBT = frozenset(
    {
        "_outcome_status_for_verdict",
        "_spot_price",
        "_richness_score",
    }
)


def _function_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_every_production_runtime_contract_matches_canonical_manifest() -> None:
    for manifest, contract in PRODUCTION_DEFINITIONS:
        validate_manifest_contract(manifest, contract)


def test_identity_drift_is_rejected_before_registry_construction() -> None:
    manifest, contract = PRODUCTION_DEFINITIONS[0]

    with pytest.raises(StrategyContractError, match="strategy_id"):
        validate_manifest_contract(manifest, replace(contract, strategy_id="drifted"))
    with pytest.raises(StrategyContractError, match="version"):
        validate_manifest_contract(manifest, replace(contract, version="99.0.0"))


def test_capability_drift_is_rejected_before_registry_construction() -> None:
    manifest, contract = PRODUCTION_DEFINITIONS[0]

    with pytest.raises(StrategyContractError, match="capabilities"):
        validate_manifest_contract(
            replace(manifest, required_market_capabilities=()), contract
        )


def test_screening_semantic_debt_cannot_expand_during_migration() -> None:
    names = _function_names(REPO_ROOT / "screening" / "live_adapters.py")
    semantic_names = {
        name
        for name in names
        if any(
            token in name
            for token in ("score", "richness", "verdict", "spot_price")
        )
    }

    assert semantic_names <= KNOWN_SCREENING_SEMANTIC_DEBT


def test_screening_does_not_duplicate_named_analytics_functions() -> None:
    screening_names = set().union(
        *(
            _function_names(path)
            for path in (REPO_ROOT / "screening").glob("*.py")
        )
    )
    analytics_names = set().union(
        *(
            _function_names(path)
            for path in (REPO_ROOT / "analytics").glob("*.py")
        )
    )

    assert not (
        screening_names
        & analytics_names
        & {
            "compute_realized_volatility",
            "compute_trailing_return",
            "select_expiration_pair",
            "rank_expiration_pairs",
        }
    )
