from datetime import UTC, date, datetime
from decimal import Decimal

from domain import OptionChain
from strategies.cboe_put_evaluation import PASS, UNKNOWN, PutwriteStrikePolicy, evaluate_cboe_put
from strategies.cboe_puty_manifest import CBOE_PUTY_MANIFEST, STRATEGY_ID
from strategy_runtime.adapters.cboe_puty import CBOE_PUTY_CONTRACT
from strategy_runtime.adapters.cboe_puty_subject_first import (
    build_cboe_puty_subject_preparation_binding,
)
from tests.strategies.test_cboe_put_strategy import _chain, _put


def test_puty_contract_is_manifest_policy_over_shared_put_stack() -> None:
    assert CBOE_PUTY_CONTRACT.strategy_id == STRATEGY_ID
    assert {item.name: item.value for item in CBOE_PUTY_MANIFEST.parameters}[
        "strike_fraction"
    ] == "0.98"
    assert {item.name: item.value for item in CBOE_PUTY_MANIFEST.parameters}[
        "strike_comparator"
    ] == "lt"


POLICY = PutwriteStrikePolicy(
    Decimal("0.98"), "lt", "G_PUTY_STRIKE_EXISTS_UNKNOWN", "CBOE_PUTY_ALL_GATES_PASS"
)


def test_puty_selects_highest_strike_strictly_below_98_percent() -> None:
    chain = _chain(_put(Decimal("4900")), _put(Decimal("4895")))
    decision = evaluate_cboe_put(
        decision_date=date(2026, 10, 16),
        roll_date=date(2026, 10, 16),
        reference_state=PASS,
        quote_value=Decimal("5000"),
        chain=chain,
        strike_policy=POLICY,
    )
    assert decision.verdict == PASS
    assert decision.selected_put is not None
    assert decision.selected_put.strike == Decimal("4895")


def test_puty_equality_without_lower_strike_is_unknown() -> None:
    chain: OptionChain = _chain(_put(Decimal("4900")))
    decision = evaluate_cboe_put(
        decision_date=date(2026, 10, 16),
        roll_date=date(2026, 10, 16),
        reference_state=PASS,
        quote_value=Decimal("5000"),
        chain=chain,
        strike_policy=POLICY,
    )
    assert decision.verdict == UNKNOWN
    assert decision.reason == "G_PUTY_STRIKE_EXISTS_UNKNOWN"


def test_puty_binding_consumes_complete_manifest_strike_policy() -> None:
    binding = build_cboe_puty_subject_preparation_binding(datetime(2026, 10, 16, tzinfo=UTC))
    policy = binding.build_shadow_adapter.keywords["strike_policy"]
    assert policy == POLICY
