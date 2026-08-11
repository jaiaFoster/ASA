"""SPRINT-014 S14-PR-05A: DemandExpansion/UnknownReason -- the generic
expansion result contract a strategy's own pure function returns without
depending on screening/.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from domain import CapabilityDemand, DemandExpansion, UnknownReason
from domain.market_data import MarketCapability
from domain.values import DomainInvariantError

NOW = datetime(2026, 8, 6, 15, 0, tzinfo=UTC)


def _demand(capability: MarketCapability = MarketCapability.REAL_TIME_QUOTE_V1) -> CapabilityDemand:
    return CapabilityDemand(capability, ("last",), NOW, NOW)


class TestUnknownReason:
    def test_code_must_be_normalized(self) -> None:
        with pytest.raises(DomainInvariantError, match="code"):
            UnknownReason(" padded")

    def test_demand_ids_are_deduplicated_and_sorted(self) -> None:
        reason = UnknownReason("no_data", demand_ids=("b", "a", "a"))
        assert reason.demand_ids == ("a", "b")

    def test_defaults_are_valid(self) -> None:
        reason = UnknownReason("no_data")
        assert reason.demand_ids == ()
        assert reason.detail == ""


class TestDemandExpansion:
    def test_defaults_to_empty(self) -> None:
        expansion = DemandExpansion()
        assert expansion.demands == ()
        assert expansion.selections == ()
        assert expansion.unknown_reasons == ()

    def test_duplicate_demand_ids_are_rejected(self) -> None:
        demand = _demand()
        equal_demand = _demand()  # a different object, identical fields -> same demand_id
        assert demand.demand_id == equal_demand.demand_id
        with pytest.raises(DomainInvariantError, match="same demand_id"):
            DemandExpansion(demands=(demand, equal_demand))

    def test_demands_are_sorted_deterministically_regardless_of_construction_order(self) -> None:
        quote = _demand(MarketCapability.REAL_TIME_QUOTE_V1)
        chain = _demand(MarketCapability.OPTION_CHAIN_V1)
        forward = DemandExpansion(demands=(quote, chain))
        backward = DemandExpansion(demands=(chain, quote))
        assert forward.demands == backward.demands

    def test_selections_keys_must_be_unique(self) -> None:
        with pytest.raises(DomainInvariantError, match="unique"):
            DemandExpansion(selections=(("front", "2026-08-21"), ("front", "2026-09-18")))

    def test_selections_keys_must_be_normalized(self) -> None:
        with pytest.raises(DomainInvariantError, match="normalized"):
            DemandExpansion(selections=((" front", "2026-08-21"),))

    def test_selections_are_sorted_deterministically_by_key(self) -> None:
        forward = DemandExpansion(selections=(("back", "2026-09-18"), ("front", "2026-08-21")))
        backward = DemandExpansion(selections=(("front", "2026-08-21"), ("back", "2026-09-18")))
        assert forward.selections == backward.selections

    def test_selections_accept_normalized_scalar_and_nested_tuple_values(self) -> None:
        expansion = DemandExpansion(
            selections=(
                ("front_expiration", "2026-08-21"),
                ("front_dte", 15),
                ("gap_days", 30.5),
                ("legs", (("strike", "190"), ("side", "call"))),
            )
        )
        assert dict(expansion.selections)["front_dte"] == 15

    def test_selections_reject_a_dict_value(self) -> None:
        with pytest.raises(DomainInvariantError, match="selections"):
            DemandExpansion(selections=(("front", {"expiration": "2026-08-21"}),))

    def test_selections_reject_a_list_value(self) -> None:
        with pytest.raises(DomainInvariantError, match="selections"):
            DemandExpansion(selections=(("legs", ["front", "back"]),))

    def test_selections_reject_a_set_value(self) -> None:
        with pytest.raises(DomainInvariantError, match="selections"):
            DemandExpansion(selections=(("tags", {"front", "back"}),))

    def test_selections_reject_a_nested_mutable_value(self) -> None:
        with pytest.raises(DomainInvariantError, match="selections"):
            DemandExpansion(selections=(("legs", (("strike", ["190"]),)),))

    def test_selections_reject_a_non_finite_float(self) -> None:
        with pytest.raises(DomainInvariantError, match="selections"):
            DemandExpansion(selections=(("ratio", float("nan")),))

    def test_selections_reject_infinity(self) -> None:
        with pytest.raises(DomainInvariantError, match="selections"):
            DemandExpansion(selections=(("ratio", float("inf")),))

    def test_selections_reject_a_mutable_custom_object(self) -> None:
        class _Opaque:
            pass

        with pytest.raises(DomainInvariantError, match="selections"):
            DemandExpansion(selections=(("front", _Opaque()),))

    def test_unknown_reasons_pass_through_as_given(self) -> None:
        reason = UnknownReason("no_earnings_date", demand_ids=(_demand().demand_id,))
        expansion = DemandExpansion(unknown_reasons=(reason,))
        assert expansion.unknown_reasons == (reason,)

    def test_carries_no_screening_or_market_data_dependency(self) -> None:
        """The structural guarantee this whole module exists for: a
        strategies/-owned pure function constructing this type never
        needs anything beyond domain/ and stdlib.
        """
        import ast
        from pathlib import Path

        module = Path(__file__).resolve().parents[2] / "domain" / "demand_expansion.py"
        tree = ast.parse(module.read_text())
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        assert roots <= {"__future__", "dataclasses", "domain"}
