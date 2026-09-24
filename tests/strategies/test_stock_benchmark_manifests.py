from __future__ import annotations

from decimal import Decimal

import pytest

from strategies.stock_benchmark_evaluation import evaluate_b001, evaluate_b002
from strategies.stock_benchmark_knowledge import B001Payload, B002Payload
from strategies.stock_benchmark_manifests import B001_MANIFEST, B002_MANIFEST
from strategy_runtime.adapters import (
    B001_CONTRACT,
    B002_CONTRACT,
    build_migrated_signal_catalog,
    build_migrated_strategy_registry,
)
from strategy_runtime.manifest_contract import validate_manifest_contract


def test_benchmark_contracts_are_validated_projections_of_their_manifests() -> None:
    validate_manifest_contract(B001_MANIFEST, B001_CONTRACT)
    validate_manifest_contract(B002_MANIFEST, B002_CONTRACT)
    build_migrated_strategy_registry()

    catalog = {item.signal_id: item for item in build_migrated_signal_catalog()}
    assert catalog["B001"].manifest_id == B001_MANIFEST.manifest_id
    assert catalog["B002"].manifest_id == B002_MANIFEST.manifest_id
    assert all(item.manifest_id != "none" for item in catalog.values())


@pytest.mark.parametrize(
    ("price", "sma", "expected"),
    [
        ("560.26", "560.25", "PASS"),
        ("560.25", "560.25", "FAIL"),
        ("400", "560.25", "FAIL"),
        ("0.01", "0", "PASS"),
    ],
)
def test_graph_verdict_preserves_strictly_above_sma_decision(
    price: str, sma: str, expected: str
) -> None:
    payload = B002Payload(Decimal(price), Decimal(sma))

    assert evaluate_b002(payload) == expected
    # Parity with the pre-manifest rule: PASS iff price > SMA.
    assert (expected == "PASS") is (Decimal(price) > Decimal(sma))


def test_buy_and_hold_graph_always_passes_on_usable_price() -> None:
    assert evaluate_b001(B001Payload(Decimal("768.6"))) == "PASS"
