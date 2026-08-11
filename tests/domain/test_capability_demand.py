"""SPRINT-014 S14-PR-05A: CapabilityDemand, the generic subject-demand
contract the new generic planner (screening/subject_planning.py) operates
over.
"""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from domain import CapabilityDemand
from domain.market_data import MarketCapability
from domain.values import DomainInvariantError

REPO_ROOT = Path(__file__).resolve().parents[2]

# Field names owned exclusively by Earnings Calendar's own expiration
# policy (strategies/requirements.py's EarningsCalendarExpirationPolicy) --
# none of these may ever appear on the generic demand contract (Architect
# review finding B1: "The contract must contain no Earnings-specific
# fields such as front_min_dte, back_max_dte, or target_gap_days").
_PROHIBITED_STRATEGY_SPECIFIC_FIELD_NAMES = {
    "front_min_dte",
    "front_max_dte",
    "back_min_dte",
    "back_max_dte",
    "target_gap_days",
    "gap_tolerance_days",
    "strategy_id",
    "manifest_id",
}


def _window(days: int = 0) -> tuple[datetime, datetime]:
    start = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)
    return start, start + timedelta(days=days)


class TestCapabilityDemandContract:
    def test_no_earnings_specific_or_strategy_identity_fields(self) -> None:
        field_names = {field.name for field in CapabilityDemand.__dataclass_fields__.values()}
        assert not (field_names & _PROHIBITED_STRATEGY_SPECIFIC_FIELD_NAMES)

    def test_construction_succeeds_with_minimal_required_fields(self) -> None:
        start, end = _window()
        demand = CapabilityDemand(
            MarketCapability.REAL_TIME_QUOTE_V1, ("last",), start, end
        )
        assert demand.required is True
        assert demand.expiration is None

    def test_required_fields_are_deduplicated_and_sorted(self) -> None:
        start, end = _window()
        demand = CapabilityDemand(
            MarketCapability.OPTION_CHAIN_V1, ("contracts", "contracts", "expirations"), start, end
        )
        assert demand.required_fields == ("contracts", "expirations")

    def test_empty_required_fields_rejected(self) -> None:
        start, end = _window()
        with pytest.raises(DomainInvariantError):
            CapabilityDemand(MarketCapability.REAL_TIME_QUOTE_V1, (), start, end)

    def test_inverted_window_rejected(self) -> None:
        start, end = _window(days=1)
        with pytest.raises(DomainInvariantError):
            CapabilityDemand(MarketCapability.REAL_TIME_QUOTE_V1, ("last",), end, start)

    def test_naive_datetime_rejected(self) -> None:
        start, end = _window()
        with pytest.raises(DomainInvariantError):
            CapabilityDemand(
                MarketCapability.REAL_TIME_QUOTE_V1, ("last",), start.replace(tzinfo=None), end
            )

    def test_negative_freshness_seconds_rejected(self) -> None:
        start, end = _window()
        with pytest.raises(DomainInvariantError):
            CapabilityDemand(
                MarketCapability.REAL_TIME_QUOTE_V1,
                ("last",),
                start,
                end,
                maximum_age_seconds=-1,
            )


class TestCapabilityDemandIdentity:
    def test_identical_demands_from_two_different_call_sites_share_one_identity(self) -> None:
        """The one property the generic planner's own demand-union step
        depends on: two consumers independently constructing what is
        semantically "the same" demand always deduplicate onto one
        provider request, never two.
        """
        start, end = _window()
        first = CapabilityDemand(MarketCapability.REAL_TIME_QUOTE_V1, ("last",), start, end)
        second = CapabilityDemand(MarketCapability.REAL_TIME_QUOTE_V1, ("last",), start, end)
        assert first.demand_id == second.demand_id

    def test_identity_ignores_field_order(self) -> None:
        start, end = _window()
        first = CapabilityDemand(
            MarketCapability.OPTION_CHAIN_V1, ("contracts", "expirations"), start, end
        )
        second = CapabilityDemand(
            MarketCapability.OPTION_CHAIN_V1, ("expirations", "contracts"), start, end
        )
        assert first.demand_id == second.demand_id

    def test_identity_never_depends_on_which_consumer_asks(self) -> None:
        """Stable demand identity is based on the complete request, never
        a strategy/consumer id -- there is no field to vary here at all,
        which is itself the point: CapabilityDemand carries no consumer
        identity for this test to accidentally smuggle in.
        """
        assert "consumer_id" not in CapabilityDemand.__dataclass_fields__
        assert "strategy_id" not in CapabilityDemand.__dataclass_fields__

    @pytest.mark.parametrize(
        "vary",
        [
            {"capability": MarketCapability.OPTION_CHAIN_V1},
            {"required_fields": ("last", "bid")},
            {"required": False},
            {"expiration": date(2026, 2, 20)},
            {"require_open_session": True},
            {"allow_prior_session": False},
            {"maximum_age_seconds": 3600},
        ],
    )
    def test_identity_changes_when_any_field_changes(self, vary: dict[str, object]) -> None:
        start, end = _window()
        base_kwargs: dict[str, object] = {
            "capability": MarketCapability.REAL_TIME_QUOTE_V1,
            "required_fields": ("last",),
            "effective_start": start,
            "effective_end": end,
        }
        baseline = CapabilityDemand(**base_kwargs)  # type: ignore[arg-type]
        varied = CapabilityDemand(**{**base_kwargs, **vary})  # type: ignore[arg-type]
        assert baseline.demand_id != varied.demand_id

    def test_identity_is_a_stable_deterministic_hex_digest(self) -> None:
        start, end = _window()
        demand = CapabilityDemand(MarketCapability.REAL_TIME_QUOTE_V1, ("last",), start, end)
        assert len(demand.demand_id) == 64
        int(demand.demand_id, 16)  # never raises -- pure hex


def _imported_roots(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text())
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


class TestCapabilityDemandBoundaries:
    """domain/'s own documented rule ("Depends on nothing but itself and
    the standard library", domain/__init__.py) had no dedicated test
    before this module existed -- narrowly enforced here rather than left
    to convention, matching the Architect's own S14-PR-05A guidance to
    prefer a narrow, real boundary guard over a broad, unenforced
    exception.
    """

    def test_capability_demand_imports_only_domain_and_stdlib(self) -> None:
        stdlib_allowed = {"__future__", "dataclasses", "datetime", "hashlib", "json"}
        imported = _imported_roots(REPO_ROOT / "domain" / "capability_demand.py")
        assert imported <= ({"domain"} | stdlib_allowed)

    def test_capability_demand_never_imports_market_data_or_screening(self) -> None:
        forbidden = {"market_data", "screening", "strategy_runtime", "strategies", "asa"}
        imported = _imported_roots(REPO_ROOT / "domain" / "capability_demand.py")
        assert not (imported & forbidden)
